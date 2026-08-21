"""Metrics collector + report rendering."""

from __future__ import annotations

from agents.base import ExecutionResult
from metrics import MetricCollector, render_markdown


def _r(passed: bool, dur: float, tin: int = 100, tout: int = 50) -> ExecutionResult:
    return ExecutionResult(
        harness="stub",
        benchmark="coder_eval",
        task_id=f"t-{dur}",
        exit_code=0,
        duration_seconds=dur,
        passed=passed,
        tokens_input=tin,
        tokens_output=tout,
        tokens_total=tin + tout,
        cost_usd=0.001,
        tool_calls={"Read": 1},
    )


def test_summarize_pass_rate_and_latency() -> None:
    collector = MetricCollector()
    for ok, dur in [(True, 0.1), (False, 0.2), (True, 0.3)]:
        collector.record(_r(ok, dur))
    s = collector.summarize()
    assert s["count"] == 3
    assert s["pass_rate"] == 2 / 3
    assert s["latency_p50"] > 0
    assert s["cost_usd_total"] == 0.003


def test_render_markdown_contains_table_rows() -> None:
    collector = MetricCollector()
    collector.record(_r(True, 0.1))
    summary = {
        "harness": "stub",
        "benchmark": "coder_eval",
        "plugins": ["none"],
        "mcp_servers": ["none"],
        "summary": collector.summarize(),
    }

    class _FakeReport:
        config = type("C", (), {"name": "x"})()
        run_id = "x"
        started_at = 0.0
        finished_at = 0.0
        results = []
        metric_summaries = [summary]

    md = render_markdown(_FakeReport())
    assert "| Harness | Benchmark |" in md
    assert "stub" in md
    assert "coder_eval" in md