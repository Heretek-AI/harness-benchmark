"""Adapter for the ``terminal-bench`` benchmark.

Terminal-bench tasks are shell-driven: each task has a working directory,
a goal prompt, and a verification command. Grading runs the verification
command and checks its exit code (or expected file diff).

This first-cut adapter uses exit-code grading only; richer assertion
support (file diffs, multi-step verifications) lands in a follow-up.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from agents.base import ExecutionResult
from benchmarks.base import JSONManifestBenchmark, TaskSpec


class TerminalBenchAdapter(JSONManifestBenchmark):
    name = "terminal-bench"
    source_path = Path("review/benchmarks/harbor")

    def _synthetic_tasks(self) -> list[TaskSpec]:
        return [
            TaskSpec(
                task_id="smoke-shell-001",
                prompt="Create a file /tmp/hb-marker.txt containing 'ok'.",
                expected={"verify_cmd": "test \"$(cat /tmp/hb-marker.txt 2>/dev/null)\" = ok"},
            )
        ]

    def _grade_expected(self, result: ExecutionResult, expected: dict) -> bool:
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