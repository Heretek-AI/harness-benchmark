"""Deterministic Oracle Evaluation Engine for Python & Shell Tasks."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from core.types import ExecutionResult


class OracleEvaluator:
    """Evaluates task executions against deterministic unit test oracles & shell assertions."""

    @staticmethod
    def evaluate_python_asserts(
        result: ExecutionResult,
        test_asserts: str,
        function_name: str | None = None,
        cwd: Path | None = None,
        timeout: int = 5,
    ) -> tuple[bool, str]:
        """Execute test asserts against extracted Python code in an isolated subprocess."""
        if result.exit_code != 0:
            return False, f"Harness exited with non-zero exit code: {result.exit_code}"

        stdout = result.stdout or ""
        candidates: list[str] = []

        # 1. Workspace Python files
        if cwd is not None and cwd.exists():
            for py_file in cwd.glob("**/*.py"):
                try:
                    content = py_file.read_text()
                    if function_name is None or f"def {function_name}" in content:
                        candidates.append(content)
                except Exception:
                    pass

        # 2. Markdown Python code blocks in stdout
        code_blocks = re.findall(r"```(?:python|py)?\s*([\s\S]*?)```", stdout)
        for block in code_blocks:
            b = block.strip()
            if b and (function_name is None or f"def {function_name}" in b):
                candidates.append(b)

        # 3. XML file write content blocks (<content>...</content>)
        xml_blocks = re.findall(r"<content>([\s\S]*?)</content>", stdout)
        for block in xml_blocks:
            b = block.strip()
            if b and (function_name is None or f"def {function_name}" in b):
                candidates.append(b)

        # 4. Raw stdout fallback
        if function_name and f"def {function_name}" in stdout:
            candidates.append(stdout)

        if not candidates:
            return False, "No valid Python function definition found in output or workspace."

        errors: list[str] = []
        for idx, code in enumerate(candidates):
            test_script = f"{code}\n\n{test_asserts}\n"
            try:
                proc = subprocess.run(
                    [sys.executable, "-c", test_script],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=cwd,
                )
                if proc.returncode == 0:
                    return True, "All unit test assertions passed successfully."
                errors.append(f"Candidate #{idx + 1} assertion error:\n{proc.stderr.strip()}")
            except subprocess.TimeoutExpired:
                errors.append(f"Candidate #{idx + 1} timed out after {timeout}s")
            except Exception as e:
                errors.append(f"Candidate #{idx + 1} exception: {e}")

        return False, "\n".join(errors)

    @staticmethod
    def evaluate_shell_verify(
        result: ExecutionResult,
        verify_cmd: str,
        cwd: Path | None = None,
        timeout: int = 30,
    ) -> tuple[bool, str]:
        """Execute deterministic shell verification command in workspace directory."""
        if result.exit_code != 0:
            return False, f"Harness exited with non-zero exit code: {result.exit_code}"

        try:
            proc = subprocess.run(
                verify_cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout,
            )
            if proc.returncode == 0:
                return True, f"Shell verification '{verify_cmd}' succeeded."
            return False, f"Verification command failed (exit code {proc.returncode}):\n{proc.stderr or proc.stdout}"
        except subprocess.TimeoutExpired:
            return False, f"Verification command timed out after {timeout}s: {verify_cmd}"
        except Exception as e:
            return False, f"Verification command execution exception: {e}"

    @staticmethod
    def evaluate_file_state(
        verify_specs: list[dict],
        cwd: Path | None = None,
    ) -> tuple[bool, str]:
        """Check file-system state assertions against the workspace.

        Each spec in ``verify_specs`` is a dict with:
            path: str         — relative path from workspace root
            exists: bool      — file must exist (default True)
            contains: str     — file must contain this string (optional)
            not_contains: str — file must NOT contain this string (optional)
            min_lines: int    — minimum line count (optional)

        Returns (passed, message).
        """
        if cwd is None or not cwd.exists():
            return False, "No workspace directory for file-state verification"

        violations: list[str] = []
        for spec in verify_specs:
            rel_path = spec.get("path", "")
            file_path = cwd / rel_path

            if spec.get("exists", True) and not file_path.exists():
                violations.append(f"{rel_path}: does not exist")
                continue

            if not spec.get("exists", True) and file_path.exists():
                violations.append(f"{rel_path}: should not exist but does")
                continue

            if file_path.exists():
                content = file_path.read_text(errors="replace")

                contains = spec.get("contains")
                if contains and contains not in content:
                    violations.append(f"{rel_path}: does not contain {contains!r}")

                not_contains = spec.get("not_contains")
                if not_contains and not_contains in content:
                    violations.append(f"{rel_path}: contains forbidden {not_contains!r}")

                min_lines = spec.get("min_lines")
                if min_lines is not None:
                    actual = len(content.splitlines())
                    if actual < min_lines:
                        violations.append(f"{rel_path}: has {actual} lines, need >= {min_lines}")

        if violations:
            return False, "File-state violations: " + "; ".join(violations)
        return True, "All file-state checks passed"
