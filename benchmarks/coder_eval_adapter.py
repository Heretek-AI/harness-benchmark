"""Adapter for the ``coder_eval`` benchmark.

``coder_eval`` (https://github.com/UiPath/coder_eval) ships a JSON manifest
of coding tasks keyed by ID. Each task has a natural-language ``prompt``
and an ``expected`` block describing the reference solution (typically a
function signature + a set of test cases). Grading compares the
harness's ``stdout`` against the reference solution's test outcomes.

The real dataset is not committed to this repo (it lives under
``review/benchmarks/coder_eval``). When the manifest is absent we fall
back to a single synthetic task so the runner can still exercise the full
pipeline in a smoke test.
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