"""Adapter for Harbor Task Standard benchmark directories.

A Harbor task is a directory containing:
    instruction.md    — natural-language task description (required)
    test.sh           — shell verification script (required)
    Dockerfile        — environment specification (optional, for containerized runs)
    oracle_solution.* — reference solution (optional, for baseline comparison)
    verify_files.json — file-system state assertions (optional, Phase 1 addition)

The adapter discovers task directories under a root path, parses each one
into a ``TaskSpec``, and grades results by executing ``test.sh`` against the
harness workspace.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

from agents.base import ExecutionResult
from benchmarks.base import BaseBenchmark, TaskSpec

logger = logging.getLogger(__name__)

# Minimum files that make a valid Harbor task directory.
REQUIRED_FILES = {"instruction.md", "test.sh"}
OPTIONAL_FILES = {"Dockerfile", "verify_files.json"}


class HarborTaskDir:
    """Parsed representation of a single Harbor task directory."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.task_id = path.name
        self.instruction = (path / "instruction.md").read_text().strip()
        self.test_script = (path / "test.sh").read_text().strip()
        self.dockerfile: str | None = None
        if (path / "Dockerfile").exists():
            self.dockerfile = (path / "Dockerfile").read_text().strip()
        self.verify_files: list[dict] | None = None
        verify_path = path / "verify_files.json"
        if verify_path.exists():
            self.verify_files = json.loads(verify_path.read_text())
        self.oracle_solution: str | None = None
        for ext in (".py", ".sh", ".js", ".go", ".rs"):
            oracle = path / f"oracle_solution{ext}"
            if oracle.exists():
                self.oracle_solution = oracle.read_text().strip()
                break

    @classmethod
    def from_directory(cls, path: Path) -> HarborTaskDir | None:
        """Parse a directory into a HarborTaskDir, returning None if invalid."""
        if not path.is_dir():
            return None
        missing = REQUIRED_FILES - {f.name for f in path.iterdir() if f.is_file()}
        if missing:
            logger.debug("Skipping %s: missing %s", path, missing)
            return None
        return cls(path)

    def to_task_spec(self) -> TaskSpec:
        """Convert to the standard TaskSpec used by the runner."""
        return TaskSpec(
            task_id=self.task_id,
            prompt=self.instruction,
            expected={
                "test_script": self.test_script,
                "verify_files": self.verify_files,
                "oracle_solution": self.oracle_solution,
            },
        )


class HarborBenchmark(BaseBenchmark):
    """Load and grade tasks from Harbor Task Standard directories.

    Usage::

        bench = HarborBenchmark("tasks/terminal-ops")
        for task in bench.iter_tasks(limit=5):
            ...

    If ``dataset_path`` points to a single task directory, only that task
    is loaded. If it points to a parent directory, all valid sub-directories
    are discovered as tasks.
    """

    name = "harbor"

    def __init__(self, dataset_path: str | Path) -> None:
        self.dataset_path = Path(dataset_path)

    def iter_tasks(self, limit: int = 0) -> Iterator[TaskSpec]:  # noqa: F821
        """Yield tasks from Harbor directories.

        If the dataset_path itself is a valid task dir, yields just that one.
        Otherwise, scans immediate subdirectories.
        """
        tasks: list[TaskSpec] = []

        # Single task directory
        single = HarborTaskDir.from_directory(self.dataset_path)
        if single is not None:
            tasks.append(single.to_task_spec())
        else:
            # Scan subdirectories
            for child in sorted(self.dataset_path.iterdir()):
                if not child.is_dir():
                    continue
                harbor_task = HarborTaskDir.from_directory(child)
                if harbor_task is not None:
                    tasks.append(harbor_task.to_task_spec())

        logger.info("Harbor: discovered %d tasks from %s", len(tasks), self.dataset_path)

        if limit > 0:
            tasks = tasks[:limit]
        yield from tasks

    def grade(
        self,
        result: ExecutionResult,
        expected: dict,
        cwd: Path | None = None,
    ) -> bool:
        """Grade by executing test.sh and checking file-state assertions."""
        if result.exit_code != 0:
            return False

        test_script = expected.get("test_script")
        if not test_script:
            return True  # No verification script — pass on exit code alone

        # Execute test.sh in the workspace
        verify_passed = self._run_test_script(test_script, cwd)
        if not verify_passed:
            return False

        # Check file-state assertions if present
        verify_files = expected.get("verify_files")
        if verify_files:
            return self._check_file_state(verify_files, cwd)

        return True

    def _run_test_script(self, test_script: str, cwd: Path | None) -> bool:
        """Execute a test.sh script and return True on success."""
        try:
            proc = subprocess.run(
                ["bash", "-c", test_script],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=cwd,
            )
            if proc.returncode != 0:
                logger.warning(
                    "Harbor test.sh failed (rc=%d): %s",
                    proc.returncode,
                    proc.stderr[:500] if proc.stderr else "",
                )
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.warning("Harbor test.sh timed out")
            return False
        except Exception as e:
            logger.warning("Harbor test.sh error: %s", e)
            return False

    def _check_file_state(self, verify_files: list[dict], cwd: Path | None) -> bool:
        """Check file-system state assertions.

        Each entry in verify_files is a dict with:
            path: str       — relative path from workspace root
            exists: bool    — file must exist (default True)
            contains: str   — file must contain this string (optional)
            not_contains: str — file must NOT contain this string (optional)
            min_lines: int  — minimum line count (optional)
        """
        if cwd is None or not cwd.exists():
            logger.warning("No workspace for file-state verification")
            return False

        for spec in verify_files:
            rel_path = spec.get("path", "")
            file_path = cwd / rel_path

            if spec.get("exists", True) and not file_path.exists():
                logger.warning("File-state check failed: %s does not exist", rel_path)
                return False

            if not spec.get("exists", True) and file_path.exists():
                logger.warning("File-state check failed: %s should not exist", rel_path)
                return False

            if file_path.exists():
                content = file_path.read_text(errors="replace")

                contains = spec.get("contains")
                if contains and contains not in content:
                    logger.warning(
                        "File-state check failed: %s does not contain %r",
                        rel_path,
                        contains,
                    )
                    return False

                not_contains = spec.get("not_contains")
                if not_contains and not_contains in content:
                    logger.warning(
                        "File-state check failed: %s contains forbidden %r",
                        rel_path,
                        not_contains,
                    )
                    return False

                min_lines = spec.get("min_lines")
                if min_lines is not None and len(content.splitlines()) < min_lines:
                    logger.warning(
                        "File-state check failed: %s has %d lines, need %d",
                        rel_path,
                        len(content.splitlines()),
                        min_lines,
                    )
                    return False

        return True


# Re-export Iterator for type annotations
from collections.abc import Iterator
