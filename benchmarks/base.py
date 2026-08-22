"""Common benchmark adapter interface.

A benchmark yields ``(task_id, prompt, expected)`` triples from
``iter_tasks`` and grades an ``ExecutionResult`` against the expected
output in ``grade``. The runner drives both methods per task.

``JSONManifestBenchmark`` is the shared base used by every benchmark whose
dataset ships as a ``tasks.json`` file inside a directory: subclasses
only override ``_synthetic_tasks`` (single-task fallback when the manifest
is absent) and ``grade``.
"""

from __future__ import annotations

import abc
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agents.base import ExecutionResult

logger = logging.getLogger(__name__)


class TaskSpec(BaseModel):
    task_id: str
    prompt: str
    expected: Any = None  # benchmark-specific
    workspace_subdir: str | None = None  # optional cwd override per task


class BaseBenchmark(abc.ABC):
    name: str = ""
    source_path: Path  # repo-rooted path to the benchmark dataset

    @abc.abstractmethod
    def iter_tasks(self, limit: int = 0) -> Iterator[TaskSpec]:
        """Yield tasks. ``limit=0`` means "all"."""

    @abc.abstractmethod
    def grade(self, result: ExecutionResult, expected: Any) -> bool:
        """Return True if the harness output satisfies the task."""

    def pre_setup(self, workspace_dir: Path) -> None:  # noqa: B027
        """Hook: copy dataset fixtures into ``workspace_dir`` before run."""
        pass


class JSONManifestBenchmark(BaseBenchmark):
    """Benchmark whose dataset is a ``tasks.json`` manifest + a synthetic fallback.

    Subclasses set ``source_path`` and override ``_synthetic_tasks`` to
    provide the single-task fallback used when the manifest is absent.
    ``_task_from_manifest`` is overridable for benchmarks whose manifest
    shape differs from the default ``{task_id, prompt, expected}``.
    """

    manifest_filename: str = "tasks.json"

    def __init__(self, dataset_path: str | Path | None = None) -> None:
        self.dataset_path = Path(dataset_path) if dataset_path else self.source_path
        self._tasks: list[TaskSpec] | None = None

    # ---- task enumeration ----

    def _task_from_manifest(self, item: dict) -> TaskSpec:
        return TaskSpec(
            task_id=item["task_id"],
            prompt=item["prompt"],
            expected=item.get("expected"),
        )

    def _synthetic_tasks(self) -> list[TaskSpec]:
        """Override to return a single fallback task when no manifest exists."""
        return []

    def _load(self) -> list[TaskSpec]:
        manifest = self.dataset_path / self.manifest_filename
        if manifest.exists():
            return [self._task_from_manifest(item) for item in json.loads(manifest.read_text())]
        synthetic = self._synthetic_tasks()
        if not synthetic:
            return []
        logger.warning(
            "%s dataset not found at %s; using synthetic fallback",
            self.name,
            self.dataset_path,
        )
        return synthetic

    def iter_tasks(self, limit: int = 0) -> Iterator[TaskSpec]:
        if self._tasks is None:
            self._tasks = self._load()
        tasks = self._tasks if limit <= 0 else self._tasks[:limit]
        yield from tasks

    # ---- default grading ----

    def grade(
        self,
        result: ExecutionResult,
        expected: Any,
        cwd: Path | None = None,
    ) -> bool:
        """Default grader: pass iff exit_code == 0 when no expected is attached.

        Subclasses override for benchmark-specific checks (stdout
        contains, file diff, shell verification, ...).
        """
        if expected is None:
            return result.exit_code == 0
        return self._grade_expected(result, expected, cwd=cwd)

    def _grade_expected(
        self,
        result: ExecutionResult,
        expected: Any,
        cwd: Path | None = None,
    ) -> bool:
        """Hook for subclass-specific grading when ``expected`` is set."""
        return expected is not None and result.exit_code == 0
