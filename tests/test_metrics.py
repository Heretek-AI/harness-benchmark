"""Metrics collector + report rendering."""

from __future__ import annotations

from pathlib import Path

from agents.base import ExecutionResult
from core.types import AblationTier
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


def test_export_junit_xml(tmp_path: Path) -> None:
    from metrics.junit_exporter import export_junit_xml

    results = [
        _r(True, 0.1),
        _r(False, 0.2),
    ]
    xml_file = tmp_path / "junit.xml"
    export_junit_xml(results, xml_file, suite_name="test-suite")
    assert xml_file.exists()
    content = xml_file.read_text()
    assert '<testsuite name="test-suite" tests="2" failures="1"' in content
    assert '<testcase name="t-0.1"' in content
    assert '<testcase name="t-0.2"' in content
    assert "<failure message=" in content


def test_infer_tier_uses_lsp_enabled_field_not_diagnostics() -> None:
    """LSP-enabled is an explicit boolean, not a proxy from diagnostics.

    Regression test for the bug where an empty ``lsp_diagnostics`` list
    silently demoted a Tier 1 ablation cell to Tier 0.
    """
    collector = MetricCollector()
    # Empty diagnostics + lsp_enabled=True -> must read as Tier 1.
    r = _r(True, 0.1)
    r.lsp_enabled = True
    r.lsp_diagnostics = []  # explicitly empty
    collector.record(r)
    s = collector.summarize()
    assert s["tier"] == AblationTier.TIER_1_LSP.value

    # lsp_enabled=False + non-empty diagnostics -> must read as Tier 0.
    collector2 = MetricCollector()
    r2 = _r(True, 0.1)
    r2.lsp_enabled = False
    r2.lsp_diagnostics = ["LSP SyntaxError: foo"]
    collector2.record(r2)
    assert collector2.summarize()["tier"] == AblationTier.TIER_0_BARE.value


def test_infer_tier_full_stack_requires_all_three() -> None:
    """Tier 4 (full stack) requires lsp + plugins + mcp."""
    assert (
        MetricCollector.infer_tier(["caveman"], ["repomix"], lsp_enabled=True) == AblationTier.TIER_4_FULL_STACK.value
    )
    assert MetricCollector.infer_tier(["caveman"], ["repomix"], lsp_enabled=False) == AblationTier.TIER_3_MCP.value
    assert MetricCollector.infer_tier(["caveman"], [], lsp_enabled=True) == AblationTier.TIER_2_SKILLS.value
    assert MetricCollector.infer_tier([], ["repomix"], lsp_enabled=True) == AblationTier.TIER_3_MCP.value
    assert MetricCollector.infer_tier([], [], lsp_enabled=True) == AblationTier.TIER_1_LSP.value
    assert MetricCollector.infer_tier([], [], lsp_enabled=False) == AblationTier.TIER_0_BARE.value
