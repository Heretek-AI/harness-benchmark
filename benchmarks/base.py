"""Common benchmark adapter interface.

A benchmark yields ``(task_id, prompt, expected)`` triples from
``iter_tasks`` and grades an ``ExecutionResult`` against the expected
output in ``grade``. The runner drives both methods per task.
"""

from __future__ import annotations

import abc
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from agents.base import ExecutionResult
from pydantic import BaseModel


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

    def pre_setup(self, workspace_dir: Path) -> None:
        """Hook: copy dataset fixtures into ``workspace_dir`` before run."""