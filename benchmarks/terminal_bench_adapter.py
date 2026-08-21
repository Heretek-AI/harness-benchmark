"""Adapter for the ``terminal-bench`` benchmark.

Terminal-bench tasks are shell-driven: each task has a working directory,
a goal prompt, and a verification command. Grading runs the verification
command and checks its exit code (or expected file diff).

This first-cut adapter uses exit-code grading only; richer assertion
support (file diffs, multi-step verifications) lands in a follow-up.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Iterator
from pathlib import Path

from benchmarks.base import BaseBenchmark, TaskSpec
from agents.base import ExecutionResult

logger = logging.getLogger(__name__)


class TerminalBenchAdapter(BaseBenchmark):
    name = "terminal-bench"
    source_path = Path("review/benchmarks/harbor")

    def __init__(self, dataset_path: str | Path | None = None) -> None:
        self.dataset_path = Path(dataset_path) if dataset_path else self.source_path
        self._tasks: list[TaskSpec] | None = None

    def _load(self) -> list[TaskSpec]:
        manifest = self.dataset_path / "tasks.json"
        if manifest.exists():
            data = json.loads(manifest.read_text())
            return [
                TaskSpec(
                    task_id=item["task_id"],
                    prompt=item["prompt"],
                    expected=item.get("expected"),
                )
                for item in data
            ]
        logger.warning(
            "terminal-bench dataset not found at %s; using synthetic task",
            self.dataset_path,
        )
        return [
            TaskSpec(
                task_id="smoke-shell-001",
                prompt="Create a file /tmp/hb-marker.txt containing 'ok'.",
                expected={"verify_cmd": "test \"$(cat /tmp/hb-marker.txt 2>/dev/null)\" = ok"},
            )
        ]

    def iter_tasks(self, limit: int = 0) -> Iterator[TaskSpec]:
        if self._tasks is None:
            self._tasks = self._load()
        tasks = self._tasks
        if limit > 0:
            tasks = tasks[:limit]
        yield from tasks

    def grade(self, result: ExecutionResult, expected: dict | None) -> bool:
        if expected is None:
            return result.exit_code == 0
        cmd = expected.get("verify_cmd")
        if cmd:
            try:
                proc = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=30
                )
                return proc.returncode == 0
            except subprocess.TimeoutExpired:
                return False
        return result.exit_code == 0