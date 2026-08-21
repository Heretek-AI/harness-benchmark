"""Adapter for the ``coder_eval`` benchmark.

``coder_eval`` (https://github.com/UiPath/coder_eval) ships a JSON manifest
of coding tasks keyed by ID. Each task has a natural-language ``prompt``
and an ``expected`` block describing the reference solution (typically a
function signature + a set of test cases). Grading compares the
harness's ``stdout`` against the reference solution's test outcomes.

The real dataset is not committed to this repo (it lives under
``review/benchmarks/coder_eval``). This adapter loads from that path when
present, otherwise falls back to a small synthetic task list so the
runner can still exercise the full pipeline in a smoke test.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path

from benchmarks.base import BaseBenchmark, TaskSpec
from agents.base import ExecutionResult

logger = logging.getLogger(__name__)


class CoderEvalAdapter(BaseBenchmark):
    name = "coder_eval"
    source_path = Path("review/benchmarks/coder_eval")

    def __init__(self, dataset_path: str | Path | None = None) -> None:
        self.dataset_path = Path(dataset_path) if dataset_path else self.source_path
        self._tasks: list[TaskSpec] | None = None

    # ---- task enumeration ----

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
        # Synthetic fallback so the pipeline is end-to-end runnable without
        # the upstream dataset checked out.
        logger.warning(
            "coder_eval dataset not found at %s; using synthetic single task",
            self.dataset_path,
        )
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

    def iter_tasks(self, limit: int = 0) -> Iterator[TaskSpec]:
        if self._tasks is None:
            self._tasks = self._load()
        tasks = self._tasks
        if limit > 0:
            tasks = tasks[:limit]
        yield from tasks

    # ---- grading ----

    def grade(self, result: ExecutionResult, expected: dict | None) -> bool:
        if expected is None:
            # No reference solution attached — pass iff exit_code was 0.
            return result.exit_code == 0
        if "stdout_contains" in expected:
            return expected["stdout_contains"] in (result.stdout or "")
        if "exit_code" in expected:
            return result.exit_code == expected["exit_code"]
        return result.exit_code == 0