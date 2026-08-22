"""Unit tests for the Multi-Tier Ablation Engine."""

from __future__ import annotations

from core.types import AblationTier, CellSummary, MetricSummary
from evaluation.ablation import AblationEngine


def test_ablation_engine_multi_tier_computation() -> None:
    # 1. Tier 0 (Bare Baseline)
    t0_sum = MetricSummary(
        tier=AblationTier.TIER_0_BARE.value,
        count=10,
        passed_count=5,
        failed_count=5,
        pass_rate=0.50,
        latency_p50=15.0,
        turns_mean=3.0,
        tokens_total=50000,
        cost_usd_total=0.20,
    )
    c0 = CellSummary(harness="claude-code", benchmark="coder_eval", plugins=[], mcp_servers=[], summary=t0_sum)

    # 2. Tier 1 (+ LSP)
    t1_sum = MetricSummary(
        tier=AblationTier.TIER_1_LSP.value,
        count=10,
        passed_count=7,
        failed_count=3,
        pass_rate=0.70,
        latency_p50=12.0,
        turns_mean=2.2,
        tokens_total=40000,
        cost_usd_total=0.16,
    )
    c1 = CellSummary(harness="claude-code", benchmark="coder_eval", plugins=[], mcp_servers=[], summary=t1_sum)

    # 3. Tier 2 (+ Skills)
    t2_sum = MetricSummary(
        tier=AblationTier.TIER_2_SKILLS.value,
        count=10,
        passed_count=7,
        failed_count=3,
        pass_rate=0.70,
        latency_p50=11.0,
        turns_mean=2.0,
        tokens_total=35000,
        cost_usd_total=0.14,
    )
    c2 = CellSummary(harness="claude-code", benchmark="coder_eval", plugins=["caveman"], mcp_servers=[], summary=t2_sum)

    # 4. Tier 3 (+ MCP)
    t3_sum = MetricSummary(
        tier=AblationTier.TIER_3_MCP.value,
        count=10,
        passed_count=8,
        failed_count=2,
        pass_rate=0.80,
        latency_p50=10.0,
        turns_mean=1.8,
        tokens_total=30000,
        cost_usd_total=0.12,
    )
    c3 = CellSummary(harness="claude-code", benchmark="coder_eval", plugins=[], mcp_servers=["repomix"], summary=t3_sum)

    # 5. Tier 4 (Full Stack)
    t4_sum = MetricSummary(
        tier=AblationTier.TIER_4_FULL_STACK.value,
        count=10,
        passed_count=10,
        failed_count=0,
        pass_rate=1.00,
        latency_p50=7.5,
        turns_mean=1.2,
        tokens_total=20000,
        cost_usd_total=0.08,
    )
    c4 = CellSummary(
        harness="claude-code",
        benchmark="coder_eval",
        plugins=["caveman"],
        mcp_servers=["repomix"],
        summary=t4_sum,
    )

    report = AblationEngine.compute_ablation_report(
        harness="claude-code",
        benchmark="coder_eval",
        model="MiniMax-M3",
        cell_summaries=[c0, c1, c2, c3, c4],
    )

    assert report.full_stack_improvement_pct == 50.0  # (1.00 - 0.50) * 100
    assert report.lsp_improvement_pct == 20.0
    assert report.mcp_improvement_pct == 30.0

    t4_delta = report.tier_deltas[AblationTier.TIER_4_FULL_STACK.value]
    assert t4_delta.delta_tokens_pct == -60.0  # (2000 - 5000) / 5000 * 100
    assert t4_delta.delta_latency_pct == -50.0  # (7.5 - 15.0) / 15.0 * 100

    md = AblationEngine.render_ablation_markdown(report)
    assert "5-Tier Ablation Proof Matrix" in md
    assert "+50.0% Pass@1" in md
