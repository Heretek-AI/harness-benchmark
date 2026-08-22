"""A/B Testing & Comparative Analysis Engine for Extensions."""

from __future__ import annotations

from core.types import ABComparisonResult, CellSummary, ExecutionResult
from evaluation.statistics import (
    bootstrap_ci,
    mcnemar_test,
    wilcoxon_signed_rank,
)


class ABComparator:
    """Computes comparative metrics between baseline and treatment evaluation cells."""

    @staticmethod
    def compare_cells(
        baseline: CellSummary,
        treatment: CellSummary,
        baseline_results: list[ExecutionResult] | None = None,
        treatment_results: list[ExecutionResult] | None = None,
    ) -> ABComparisonResult:
        """Compare a baseline cell with a treatment cell and compute delta metrics.

        ``baseline_results`` / ``treatment_results`` are optional
        per-task ``ExecutionResult`` lists; when supplied the comparator
        runs McNemar's test (binary pass/fail) and Wilcoxon signed-rank
        (continuous latency / token deltas) on the paired observations.
        """
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

        # Statistical significance (Phase A)
        mcnemar_chi2, mcnemar_p = None, None
        wilcoxon_w, wilcoxon_p = None, None
        bootstrap_lo, bootstrap_hi = None, None
        bootstrap_target = "pass_rate"
        if baseline_results and treatment_results:
            baseline_pass = [bool(r.passed) for r in baseline_results]
            treatment_pass = [bool(r.passed) for r in treatment_results]
            mcnemar_chi2, mcnemar_p = mcnemar_test(baseline_pass, treatment_pass)

            lat_deltas: list[float] = []
            tok_deltas: list[float] = []
            min_len = min(len(baseline_results), len(treatment_results))
            for i in range(min_len):
                br = baseline_results[i]
                tr = treatment_results[i]
                if br.task_id != tr.task_id:
                    # Paired by index only when task_ids match. If they
                    # don't, skip Wilcoxon (the CLI is responsible for
                    # producing matching task orderings).
                    continue
                if br.duration_seconds is not None and tr.duration_seconds is not None:
                    lat_deltas.append(tr.duration_seconds - br.duration_seconds)
                b_total = (br.tokens_input or 0) + (br.tokens_output or 0)
                t_total = (tr.tokens_input or 0) + (tr.tokens_output or 0)
                tok_deltas.append(t_total - b_total)
            # Use latency deltas as the headline continuous metric.
            wilcoxon_w, wilcoxon_p = wilcoxon_signed_rank(lat_deltas)

            # Bootstrap CI on the pass-rate delta distribution.
            pass_deltas: list[float] = []
            for i in range(min_len):
                br_p = 1.0 if baseline_results[i].passed else 0.0
                tr_p = 1.0 if treatment_results[i].passed else 0.0
                pass_deltas.append(tr_p - br_p)
            bootstrap_lo, bootstrap_hi = bootstrap_ci(pass_deltas)
            bootstrap_target = "pass_rate_delta"

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
            mcnemar_chi2=mcnemar_chi2,
            mcnemar_p_value=mcnemar_p,
            wilcoxon_w=wilcoxon_w,
            wilcoxon_p_value=wilcoxon_p,
            bootstrap_ci_lower=bootstrap_lo,
            bootstrap_ci_upper=bootstrap_hi,
            bootstrap_target=bootstrap_target,
        )

    @staticmethod
    def render_ab_markdown_table(comparisons: list[ABComparisonResult]) -> str:
        """Render a markdown summary table of A/B test results."""
        if not comparisons:
            return ""

        lines = [
            "### 🔬 A/B Extension Evaluation Deltas",
            "",
            "| Harness | Benchmark | Baseline | Treatment | Δ Pass@1 | Δ Latency | Δ Tokens | Δ Tool Calls | McNemar p | Wilcoxon p | Boot CI | Verdict |",
            "|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|",
        ]

        for c in comparisons:
            b_ext = ",".join(c.baseline_plugins + c.baseline_mcp) or "none"
            t_ext = ",".join(c.treatment_plugins + c.treatment_mcp) or "none"
            pass_sign = "+" if c.delta_pass_rate > 0 else ""
            lat_sign = "+" if c.delta_latency_pct > 0 else ""
            tok_sign = "+" if c.delta_tokens_pct > 0 else ""
            tool_sign = "+" if c.delta_tool_calls_pct > 0 else ""

            mcnemar_p_str = "—" if c.mcnemar_p_value is None else f"{c.mcnemar_p_value:.4f}"
            wilcoxon_p_str = "—" if c.wilcoxon_p_value is None else f"{c.wilcoxon_p_value:.4f}"
            if c.bootstrap_ci_lower is not None and c.bootstrap_ci_upper is not None:
                ci_str = f"[{c.bootstrap_ci_lower:+.2f}, {c.bootstrap_ci_upper:+.2f}]"
            else:
                ci_str = "—"

            lines.append(
                f"| `{c.harness}` | `{c.benchmark}` | `{b_ext}` | `{t_ext}` | "
                f"**{pass_sign}{c.delta_pass_rate:.1f}%** | {lat_sign}{c.delta_latency_pct:.1f}% | "
                f"{tok_sign}{c.delta_tokens_pct:.1f}% | {tool_sign}{c.delta_tool_calls_pct:.1f}% | "
                f"{mcnemar_p_str} | {wilcoxon_p_str} | {ci_str} | {c.narrative_verdict} |"
            )

        return "\n".join(lines)
