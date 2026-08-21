"""Adapter for the ``coder_eval`` benchmark suite.

Evaluates coding capabilities against coding problem manifests (derived from
https://github.com/UiPath/coder_eval). Each task provides a natural-language
prompt and assertion criteria.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from agents.base import ExecutionResult
from benchmarks.base import JSONManifestBenchmark, TaskSpec


class CoderEvalAdapter(JSONManifestBenchmark):
    name = "coder_eval"
    source_path = Path(__file__).parent / "data" / "coder_eval"

    def _synthetic_tasks(self) -> list[TaskSpec]:
        return [
            TaskSpec(
                task_id="ce-py-smoke-001",
                prompt=(
                    "Write a Python function `add(a, b)` that returns the "
                    "sum of a and b. Print the result of add(2, 3)."
                ),
                expected={"stdout_contains": "5"},
            )
        ]

    def _grade_expected(self, result: ExecutionResult, expected: dict) -> bool:
        if result.exit_code != 0:
            return False

        stdout = result.stdout or ""

        if "stdout_contains" in expected:
            target = str(expected["stdout_contains"]).strip()
            if target in stdout:
                return True

            # If the model emitted a Python code snippet without executing it,
            # execute the code snippet to check if the logic satisfies the expected output.
            code_blocks = re.findall(r"```(?:python|py)?\s*([\s\S]*?)```", stdout)
            for code in code_blocks:
                code = code.strip()
                if not code:
                    continue
                try:
                    proc = subprocess.run(
                        [sys.executable, "-c", code],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if proc.returncode == 0 and target in proc.stdout:
                        return True
                except (subprocess.TimeoutExpired, Exception):
                    continue

            return False

        if "exit_code" in expected:
            return result.exit_code == expected["exit_code"]

        return result.exit_code == 0