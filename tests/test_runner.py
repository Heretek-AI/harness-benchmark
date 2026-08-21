"""End-to-end runner smoke test against the stub adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.runner import BenchmarkRunner, RunConfig
from mcp import MCPLauncher
from plugins import PluginLoader


def test_runner_end_to_end_against_stub(
    tmp_path: Path,
    plugin_registry_path: Path,
    mcp_registry_path: Path,
) -> None:
    config = RunConfig(
        name="unit-smoke",
        harness=["stub"],
        benchmark=["coder_eval"],
        plugins=["none"],
        mcp_servers=["none"],
        tasks_limit=1,
        timeout_seconds=30,
        output_format="json",
        output_dir=tmp_path / "runs",
    )
    runner = BenchmarkRunner(
        config,
        PluginLoader(plugin_registry_path),
        MCPLauncher(mcp_registry_path),
    )
    report = runner.run()

    assert report.results, "expected at least one ExecutionResult"
    r = report.results[0]
    assert r.harness == "stub"
    assert r.benchmark == "coder_eval"
    assert r.task_id == "smoke-001"
    assert r.passed is True
    assert r.tokens_total == 192

    # result.json should be on disk.
    run_dirs = list((tmp_path / "runs").iterdir())
    assert run_dirs, "expected at least one run dir"
    result_path = run_dirs[0] / "result.json"
    assert result_path.exists()
    blob = json.loads(result_path.read_text())
    assert blob["run_id"] == report.run_id