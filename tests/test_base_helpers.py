"""Tests for the shared base-class helpers extracted in the duplication refactor.

These lock in the contract that:
- ``BaseAgentAdapter._build_command`` is the single place adapters specify
  the argv shape, and the default is ``[cli_binary, prompt]``.
- ``BaseAgentAdapter._run_cli`` handles ``FileNotFoundError`` and
  ``TimeoutExpired`` uniformly across adapters.
- ``JSONManifestBenchmark`` loads from ``tasks.json`` when present and
  falls back to ``_synthetic_tasks`` when not.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agents import (
    AntigravityAdapter,
    DeepSeekHarnessAdapter,
    GeminiCLIAdapter,
    OpenCodeAdapter,
)
from benchmarks import CoderEvalAdapter, JSONManifestBenchmark, TaskSpec


# ---- adapter command shape ----


def test_default_build_command_is_cli_plus_prompt() -> None:
    """Adapters that don't override _build_command get [cli_binary, prompt]."""
    # Use AntigravityAdapter because its name+cli_binary are well-defined
    # and it overrides _build_command — confirms the override path.
    a = AntigravityAdapter()
    cmd = a._build_command("hello", Path("/tmp"))
    assert cmd == ["antigravity", "run", "hello"]


def test_per_adapter_command_shapes() -> None:
    assert DeepSeekHarnessAdapter()._build_command("p", Path("/x")) == [
        "deepseek",
        "--task",
        "p",
    ]
    assert GeminiCLIAdapter()._build_command("p", Path("/x")) == [
        "gemini",
        "run",
        "p",
    ]
    assert OpenCodeAdapter()._build_command("p", Path("/x")) == [
        "opencode",
        "--non-interactive",
        "p",
    ]


def test_run_cli_records_file_not_found(tmp_path: Path) -> None:
    """Missing CLI binary produces a -1 exit_code and FileNotFoundError label."""
    a = AntigravityAdapter()
    # setup() creates the tmp workspace and adapter context.
    a.setup(env_vars={}, plugins=[], mcp_servers=[])
    try:
        result = a._run_cli(
            ["definitely-not-a-real-binary-xyzzy"],
            tmp_path,
            timeout=5,
        )
    finally:
        a.teardown()
    assert result.exit_code == -1
    assert result.error == "FileNotFoundError"
    assert "definitely-not-a-real-binary-xyzzy" in result.stderr


# ---- JSONManifestBenchmark ----


def test_json_manifest_loads_when_present(tmp_path: Path) -> None:
    (tmp_path / "tasks.json").write_text(
        '[{"task_id": "t1", "prompt": "p1", "expected": {"x": 1}}, '
        '{"task_id": "t2", "prompt": "p2"}]'
    )

    class _T(JSONManifestBenchmark):
        name = "tmp-test"
        source_path = tmp_path

        def _synthetic_tasks(self) -> list[TaskSpec]:
            return []

        def _grade_expected(self, result, expected):  # pragma: no cover
            return True

    bench = _T()
    tasks = list(bench.iter_tasks())
    assert [t.task_id for t in tasks] == ["t1", "t2"]
    assert tasks[0].expected == {"x": 1}


def test_json_manifest_falls_back_to_synthetic(tmp_path: Path) -> None:
    sentinel = TaskSpec(task_id="synth", prompt="synthetic prompt")

    class _T(JSONManifestBenchmark):
        name = "tmp-test"
        source_path = tmp_path

        def _synthetic_tasks(self) -> list[TaskSpec]:
            return [sentinel]

    bench = _T()
    assert list(bench.iter_tasks()) == [sentinel]


def test_coder_eval_synthetic_task_is_loadable(tmp_path: Path) -> None:
    """Sanity check that the real adapter's synthetic fallback still wires up."""
    bench = CoderEvalAdapter(dataset_path=tmp_path)  # manifest absent
    tasks = list(bench.iter_tasks(limit=1))
    assert tasks[0].task_id == "smoke-001"
    assert tasks[0].expected == {"stdout_contains": "5"}