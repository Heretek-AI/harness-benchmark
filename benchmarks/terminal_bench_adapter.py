"""Adapter for the ``terminal-bench`` benchmark suite.

Terminal-bench tasks evaluate CLI and shell capabilities. Each task includes
a natural language goal prompt and a verification command graded automatically.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from agents.base import ExecutionResult
from benchmarks.base import JSONManifestBenchmark, TaskSpec


class TerminalBenchAdapter(JSONManifestBenchmark):
    name = "terminal-bench"
    source_path = Path(__file__).parent / "data" / "terminal_bench"

    def _synthetic_tasks(self) -> list[TaskSpec]:
        return [
            TaskSpec(
                task_id="tb-sh-smoke-001",
                prompt="Create a file marker.txt containing 'antigravity_verified'.",
                expected={"verify_cmd": "test -f marker.txt && grep -q 'antigravity_verified' marker.txt"},
            )
        ]

    def _grade_expected(
        self,
        result: ExecutionResult,
        expected: dict,
        cwd: Path | None = None,
    ) -> bool:
        if result.exit_code != 0:
            return False

        cmd = expected.get("verify_cmd")
        if cmd:
            try:
                proc = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=cwd,
                    timeout=30,
                )
                if proc.returncode == 0:
                    return True
                if cwd is not None and cwd.resolve() != Path.cwd().resolve():
                    proc_root = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        cwd=Path.cwd(),
                        timeout=30,
                    )
                    if proc_root.returncode == 0:
                        return True
                return False
            except subprocess.TimeoutExpired:
                return False
        return True
