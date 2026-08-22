"""Tests for pass^k aggregation through BenchmarkRunner."""

from __future__ import annotations

from pathlib import Path

from benchmarks.runner import BenchmarkRunner, RunConfig
from mcp import MCPLauncher
from plugins import PluginLoader


def _make_runner(
    tmp_path: Path,
    plugin_registry: Path,
    mcp_registry: Path,
    repeat_count: int = 1,
) -> BenchmarkRunner:
    config = RunConfig(
        name="unit-passk",
        harness=["stub"],
        benchmark=["coder_eval"],
        plugins=["none"],
        mcp_servers=["none"],
        tasks_limit=1,
        timeout_seconds=30,
        output_format="json",
        output_dir=tmp_path / "runs",
        repeat_count=repeat_count,
    )
    return BenchmarkRunner(
        config,
        PluginLoader(plugin_registry),
        MCPLauncher(mcp_registry),
    )


def test_repeat_count_1_no_pass_at_k(
    tmp_path: Path,
    plugin_registry_path: Path,
    mcp_registry_path: Path,
) -> None:
    runner = _make_runner(tmp_path, plugin_registry_path, mcp_registry_path, repeat_count=1)
    report = runner.run()
    # repeat_count=1 -> exactly one result per task, no pass^k aggregation.
    assert len(report.results) == 1
    s = report.metric_summaries[0]["summary"]
    assert s.get("pass_at_2") is None
    assert s.get("pass_at_3") is None


def test_repeat_count_3_produces_3_results_per_task(
    tmp_path: Path,
    plugin_registry_path: Path,
    mcp_registry_path: Path,
) -> None:
    runner = _make_runner(tmp_path, plugin_registry_path, mcp_registry_path, repeat_count=3)
    report = runner.run()
    assert len(report.results) == 3
    # All three have the same task_id and distinct repeat_index.
    task_ids = {r.task_id for r in report.results}
    assert len(task_ids) == 1
    repeat_indices = sorted(r.repeat_index for r in report.results)
    assert repeat_indices == [0, 1, 2]


def test_repeat_count_3_stamps_pass_at_2_and_pass_at_3(
    tmp_path: Path,
    plugin_registry_path: Path,
    mcp_registry_path: Path,
) -> None:
    runner = _make_runner(tmp_path, plugin_registry_path, mcp_registry_path, repeat_count=3)
    report = runner.run()
    s = report.metric_summaries[0]["summary"]
    # Stub harness always fails (it's the synthetic baseline); pass^k = 0.0
    # for both k=2 and k=3 because no run passes.
    assert s.get("pass_at_2") == 0.0
    assert s.get("pass_at_3") == 0.0


def test_pass_vector_key_groups_runs_of_the_same_task(
    tmp_path: Path,
    plugin_registry_path: Path,
    mcp_registry_path: Path,
) -> None:
    """Each run of the same task shares ``pass_vector_key``."""
    runner = _make_runner(tmp_path, plugin_registry_path, mcp_registry_path, repeat_count=3)
    report = runner.run()
    keys = {r.pass_vector_key for r in report.results}
    assert len(keys) == 1
    assert keys.pop() is not None
