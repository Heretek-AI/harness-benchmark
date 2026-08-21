"""Adapter for the ``coder_eval`` benchmark suite.

Evaluates coding capabilities against coding problem manifests (derived from
https://github.com/UiPath/coder_eval). Each task provides a natural-language
prompt and assertion criteria. Supports synthetic fallback tasks for local
smoke testing when external datasets are not mounted.
"""

from __future__ import annotations

from pathlib import Path

from agents.base import ExecutionResult
from benchmarks.base import JSONManifestBenchmark, TaskSpec


class CoderEvalAdapter(JSONManifestBenchmark):
    name = "coder_eval"
    source_path = Path("review/benchmarks/coder_eval")

    def _synthetic_tasks(self) -> list[TaskSpec]:
        return [
            TaskSpec(
                task_id="smoke-001",
                prompt=(
                    "Write a Python function `add(a, b)` that returns the "
                    "sum of a and b. Print the result of add(2, 3)."
                ),
                expected={"stdout_contains": "5"},
            )
        ]

    def _grade_expected(self, result: ExecutionResult, expected: dict) -> bool:
        if "stdout_contains" in expected:
            return expected["stdout_contains"] in (result.stdout or "")
        if "exit_code" in expected:
            return result.exit_code == expected["exit_code"]
        return result.exit_code == 0