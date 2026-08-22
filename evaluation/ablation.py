"""Multi-Tier Ablation Engine for empirical proof of augmentation ROI."""

from __future__ import annotations

from core.types import AblationTier, CellSummary, MultiTierAblationReport, TierDelta


class AblationEngine:
    """Calculates empirical ablation proof matrices across 5 deterministic tiers."""

    @staticmethod
    def compute_ablation_report(
        harness: str,
        benchmark: str,
        model: str,
        cell_summaries: list[CellSummary],
    ) -> MultiTierAblationReport:
        """Compute full 5-tier ablation comparison against baseline Tier 0."""
        # Find cell for each tier
        tier_cells: dict[str, CellSummary] = {}
        for c in cell_summaries:
            if c.harness == harness and c.benchmark == benchmark:
                tier = c.summary.tier or AblationTier.TIER_0_BARE.value
                tier_cells[tier] = c

        # Baseline (Tier 0) fallback if not explicitly tagged
        b_cell = tier_cells.get(AblationTier.TIER_0_BARE.value)
        if not b_cell:
            # Fallback to the cell with no plugins and no mcp
            for c in cell_summaries:
                if c.harness == harness and c.benchmark == benchmark and not c.plugins and not c.mcp_servers:
                    b_cell = c
                    break

        b_pass = b_cell.summary.pass_rate if b_cell and b_cell.summary.pass_rate is not None else 0.0
        b_toks = (
            (b_cell.summary.tokens_total // b_cell.summary.count)
            if b_cell and b_cell.summary.count > 0 and b_cell.summary.tokens_total
            else 0
        )
        b_lat = b_cell.summary.latency_p50 if b_cell and b_cell.summary.latency_p50 is not None else 0.0
        b_turns = b_cell.summary.turns_mean if b_cell else 1.0
        b_cost = b_cell.summary.cost_usd_total if b_cell else 0.0

        deltas: dict[str, TierDelta] = {}

        for tier_enum in AblationTier:
            t_name = tier_enum.value
            c = tier_cells.get(t_name)
            if not c:
                continue

            s = c.summary
            p_rate = s.pass_rate if s.pass_rate is not None else 0.0
            d_pass = round((p_rate - b_pass) * 100.0, 2)

            toks_per_task = (s.tokens_total // s.count) if s.count > 0 and s.tokens_total else 0
            d_toks_pct = round(((toks_per_task - b_toks) / b_toks * 100.0), 2) if b_toks > 0 else 0.0

            lat_p50 = s.latency_p50 if s.latency_p50 is not None else 0.0
            d_lat_pct = round(((lat_p50 - b_lat) / b_lat * 100.0), 2) if b_lat > 0 else 0.0

            turns_m = s.turns_mean
            d_turns_pct = round(((turns_m - b_turns) / b_turns * 100.0), 2) if b_turns > 0 else 0.0

            cost_tot = s.cost_usd_total
            d_cost_pct = round(((cost_tot - b_cost) / b_cost * 100.0), 2) if b_cost > 0 else 0.0

            deltas[t_name] = TierDelta(
                tier_name=t_name,
                pass_rate=p_rate,
                delta_pass_rate=d_pass,
                tokens_per_task=toks_per_task,
                delta_tokens_pct=d_toks_pct,
                latency_p50=lat_p50,
                delta_latency_pct=d_lat_pct,
                turns_mean=turns_m,
                delta_turns_pct=d_turns_pct,
                cost_total=cost_tot,
                delta_cost_pct=d_cost_pct,
            )

        # Calculate specific augmentation improvements
        lsp_imp = deltas.get(
            AblationTier.TIER_1_LSP.value,
            TierDelta(
                tier_name="",
                pass_rate=0.0,
                delta_pass_rate=0.0,
                tokens_per_task=0,
                delta_tokens_pct=0.0,
                latency_p50=0.0,
                delta_latency_pct=0.0,
                turns_mean=0.0,
                delta_turns_pct=0.0,
                cost_total=0.0,
                delta_cost_pct=0.0,
            ),
        ).delta_pass_rate

        skills_imp = deltas.get(
            AblationTier.TIER_2_SKILLS.value,
            TierDelta(
                tier_name="",
                pass_rate=0.0,
                delta_pass_rate=0.0,
                tokens_per_task=0,
                delta_tokens_pct=0.0,
                latency_p50=0.0,
                delta_latency_pct=0.0,
                turns_mean=0.0,
                delta_turns_pct=0.0,
                cost_total=0.0,
                delta_cost_pct=0.0,
            ),
        ).delta_pass_rate

        mcp_imp = deltas.get(
            AblationTier.TIER_3_MCP.value,
            TierDelta(
                tier_name="",
                pass_rate=0.0,
                delta_pass_rate=0.0,
                tokens_per_task=0,
                delta_tokens_pct=0.0,
                latency_p50=0.0,
                delta_latency_pct=0.0,
                turns_mean=0.0,
                delta_turns_pct=0.0,
                cost_total=0.0,
                delta_cost_pct=0.0,
            ),
        ).delta_pass_rate

        full_imp = deltas.get(
            AblationTier.TIER_4_FULL_STACK.value,
            TierDelta(
                tier_name="",
                pass_rate=0.0,
                delta_pass_rate=0.0,
                tokens_per_task=0,
                delta_tokens_pct=0.0,
                latency_p50=0.0,
                delta_latency_pct=0.0,
                turns_mean=0.0,
                delta_turns_pct=0.0,
                cost_total=0.0,
                delta_cost_pct=0.0,
            ),
        ).delta_pass_rate

        verdict = f"Augmenting {harness} with Full Stack (LSP+Skills+MCP) yields a {full_imp:+.1f}% Pass@1 delta."

        return MultiTierAblationReport(
            harness=harness,
            benchmark=benchmark,
            model=model,
            tier_deltas=deltas,
            lsp_improvement_pct=lsp_imp,
            skills_improvement_pct=skills_imp,
            mcp_improvement_pct=mcp_imp,
            full_stack_improvement_pct=full_imp,
            summary_verdict=verdict,
        )

    @staticmethod
    def render_ablation_markdown(report: MultiTierAblationReport) -> str:
        """Render standard Markdown delta matrix across all 5 tiers."""
        lines = [
            f"### 🔬 5-Tier Ablation Proof Matrix (`{report.harness}` on `{report.benchmark}`)",
            "",
            f"**Evaluated Model**: `{report.model}` | **Full Stack Net Gain**: **`{report.full_stack_improvement_pct:+.1f}% Pass@1`**",
            "",
            "| Ablation Tier | Description | Pass@1 | Δ Pass Rate | Tokens / Task | Δ Token Cost | Latency p50 | Avg Turns |",
            "|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|",
        ]

        tier_descriptions = {
            AblationTier.TIER_0_BARE.value: "Raw Model Reasoning",
            AblationTier.TIER_1_LSP.value: "+ LSP AST Diagnostic Loop",
            AblationTier.TIER_2_SKILLS.value: "+ Skills & Rule Harnesses",
            AblationTier.TIER_3_MCP.value: "+ Model Context Protocol (MCP)",
            AblationTier.TIER_4_FULL_STACK.value: "Full Stack (LSP + Skills + MCP)",
        }

        for tier_enum in AblationTier:
            t_name = tier_enum.value
            delta = report.tier_deltas.get(t_name)
            desc = tier_descriptions.get(t_name, t_name)
            if not delta:
                lines.append(f"| `{t_name}` | {desc} | - | - | - | - | - | - |")
                continue

            p_sign = "+" if delta.delta_pass_rate > 0 else ""
            tok_sign = "+" if delta.delta_tokens_pct > 0 else ""

            lines.append(
                f"| `{t_name}` | {desc} | **{delta.pass_rate * 100:.1f}%** | "
                f"**{p_sign}{delta.delta_pass_rate:.1f}%** | {delta.tokens_per_task:,} | "
                f"{tok_sign}{delta.delta_tokens_pct:.1f}% | {delta.latency_p50:.2f}s | {delta.turns_mean:.1f} |"
            )

        lines.extend(["", f"> **Empirical Conclusion**: {report.summary_verdict}", ""])
        return "\n".join(lines)
