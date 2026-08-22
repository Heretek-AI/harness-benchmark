"""End-to-end runner smoke test against the stub adapter."""

from __future__ import annotations

import json
from pathlib import Path

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
    assert r.task_id == "ce-py-001"
    assert r.exit_code == 0
    assert r.tokens_total == 192

    # result.json should be on disk.
    run_dirs = list((tmp_path / "runs").iterdir())
    assert run_dirs, "expected at least one run dir"
    result_path = run_dirs[0] / "result.json"
    assert result_path.exists()
    blob = json.loads(result_path.read_text())
    assert blob["run_id"] == report.run_id


def test_runner_markdown_output_format(
    tmp_path: Path,
    plugin_registry_path: Path,
    mcp_registry_path: Path,
) -> None:
    config = RunConfig(
        name="unit-markdown",
        harness=["stub"],
        benchmark=["coder_eval", "terminal-bench"],
        plugins=["none"],
        mcp_servers=["none"],
        tasks_limit=1,
        timeout_seconds=30,
        output_format="markdown",
        output_dir=tmp_path / "runs",
    )
    runner = BenchmarkRunner(
        config,
        PluginLoader(plugin_registry_path),
        MCPLauncher(mcp_registry_path),
    )
    report = runner.run()
    assert len(report.results) == 2
    run_dir = tmp_path / "runs" / report.run_id
    report_md = run_dir / "REPORT.md"
    assert report_md.exists()
    content = report_md.read_text()
    assert "Benchmark Report:" in content or "# Benchmark run:" in content
    assert "coder_eval" in content
    assert "terminal-bench" in content


def test_cli_main_invocation(tmp_path: Path) -> None:
    from run_benchmark import main

    rc = main(
        [
            "--harness",
            "stub",
            "--benchmark",
            "coder_eval",
            "--plugins",
            "none",
            "--mcp",
            "none",
            "--tasks-limit",
            "1",
            "--output-format",
            "json",
            "--output-dir",
            str(tmp_path / "cli_runs"),
        ]
    )
    assert rc == 0
    run_dirs = list((tmp_path / "cli_runs").iterdir())
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "result.json").exists()


def test_cli_main_junit_and_score_floor(tmp_path: Path) -> None:
    from run_benchmark import main

    junit_file = tmp_path / "test_junit.xml"
    rc = main(
        [
            "--harness",
            "stub",
            "--benchmark",
            "coder_eval",
            "--plugins",
            "none",
            "--mcp",
            "none",
            "--tasks-limit",
            "1",
            "--junit-xml",
            str(junit_file),
            "--minimum-task-score",
            "0.0",
            "--output-dir",
            str(tmp_path / "cli_runs_junit"),
        ]
    )
    assert rc == 0
    assert junit_file.exists()
    assert "<testsuite" in junit_file.read_text()

    # Test failure when floor is above stub's pass rate (0.0 < 0.5)
    rc_fail = main(
        [
            "--harness",
            "stub",
            "--benchmark",
            "coder_eval",
            "--plugins",
            "none",
            "--mcp",
            "none",
            "--tasks-limit",
            "1",
            "--minimum-task-score",
            "0.5",
            "--output-dir",
            str(tmp_path / "cli_runs_fail"),
        ]
    )
    assert rc_fail == 1
