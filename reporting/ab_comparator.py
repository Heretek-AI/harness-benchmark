"""A/B Testing & Comparative Analysis Engine for Extensions."""

from __future__ import annotations

from core.types import ABComparisonResult, CellSummary


class ABComparator:
    """Computes comparative metrics between baseline and treatment evaluation cells."""

    @staticmethod
    def compare_cells(baseline: CellSummary, treatment: CellSummary) -> ABComparisonResult:
        """Compare a baseline cell with a treatment cell and compute delta metrics."""
        b_sum = baseline.summary
        t_sum = treatment.summary

        # Pass Rate Delta
        delta_pass = (t_sum.pass_rate - b_sum.pass_rate) * 100.0

        # Latency Delta % (negative is faster / good)
        if b_sum.latency_p50 > 0:
            delta_latency_pct = ((t_sum.latency_p50 - b_sum.latency_p50) / b_sum.latency_p50) * 100.0
        else:
            delta_latency_pct = 0.0

        # Tokens Delta % (negative is token savings / good)
        if b_sum.tokens_total > 0:
            delta_tokens_pct = ((t_sum.tokens_total - b_sum.tokens_total) / b_sum.tokens_total) * 100.0
        else:
            delta_tokens_pct = 0.0

        # Tool Calls Delta %
        if b_sum.tool_calls_total > 0:
            delta_tools_pct = ((t_sum.tool_calls_total - b_sum.tool_calls_total) / b_sum.tool_calls_total) * 100.0
        else:
            delta_tools_pct = 0.0

        # Narrative Verdict
        if delta_pass > 0 and delta_tokens_pct <= 0:
            verdict = "🟢 Strong Improvement: Higher pass rate with reduced token overhead."
        elif delta_pass > 0:
            verdict = f"🟢 Improved Accuracy: +{delta_pass:.1f}% pass rate gain."
        elif delta_pass == 0 and delta_tokens_pct < -10:
            verdict = f"🟢 High Efficiency: Identical accuracy with {abs(delta_tokens_pct):.1f}% token savings."
        elif delta_pass == 0:
            verdict = "⚪ Neutral: Comparable performance across metrics."
        else:
            verdict = f"🔴 Regression: {delta_pass:.1f}% drop in pass rate."

        return ABComparisonResult(
            harness=treatment.harness,
            benchmark=treatment.benchmark,
            baseline_plugins=baseline.plugins,
            baseline_mcp=baseline.mcp_servers,
            treatment_plugins=treatment.plugins,
            treatment_mcp=treatment.mcp_servers,
            baseline_pass_rate=b_sum.pass_rate,
            treatment_pass_rate=t_sum.pass_rate,
            delta_pass_rate=delta_pass,
            baseline_latency_p50=b_sum.latency_p50,
            treatment_latency_p50=t_sum.latency_p50,
            delta_latency_pct=delta_latency_pct,
            baseline_tokens_total=b_sum.tokens_total,
            treatment_tokens_total=t_sum.tokens_total,
            delta_tokens_pct=delta_tokens_pct,
            baseline_tool_calls=b_sum.tool_calls_total,
            treatment_tool_calls=t_sum.tool_calls_total,
            delta_tool_calls_pct=delta_tools_pct,
            narrative_verdict=verdict,
        )

    @staticmethod
    def render_ab_markdown_table(comparisons: list[ABComparisonResult]) -> str:
        """Render a markdown summary table of A/B test results."""
        if not comparisons:
            return ""

        lines = [
            "### 🔬 A/B Extension Evaluation Deltas",
            "",
            "| Harness | Benchmark | Baseline | Treatment | Δ Pass@1 | Δ Latency | Δ Tokens | Δ Tool Calls | Verdict |",
            "|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|",
        ]

        for c in comparisons:
            b_ext = ",".join(c.baseline_plugins + c.baseline_mcp) or "none"
            t_ext = ",".join(c.treatment_plugins + c.treatment_mcp) or "none"
            pass_sign = "+" if c.delta_pass_rate > 0 else ""
            lat_sign = "+" if c.delta_latency_pct > 0 else ""
            tok_sign = "+" if c.delta_tokens_pct > 0 else ""
            tool_sign = "+" if c.delta_tool_calls_pct > 0 else ""

            lines.append(
                f"| `{c.harness}` | `{c.benchmark}` | `{b_ext}` | `{t_ext}` | "
                f"**{pass_sign}{c.delta_pass_rate:.1f}%** | {lat_sign}{c.delta_latency_pct:.1f}% | "
                f"{tok_sign}{c.delta_tokens_pct:.1f}% | {tool_sign}{c.delta_tool_calls_pct:.1f}% | {c.narrative_verdict} |"
            )

        return "\n".join(lines)
