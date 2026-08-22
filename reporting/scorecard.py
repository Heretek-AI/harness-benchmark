"""Visual Model Scorecard & Leaderboard Generator for Harness Benchmark 2.0."""

from __future__ import annotations

from core.types import BenchmarkReport


class ScorecardGenerator:
    """Generates human-centric terminal scorecards and markdown tables."""

    @staticmethod
    def render_markdown_leaderboard(report: BenchmarkReport) -> str:
        """Render a high-level markdown leaderboard ranking all evaluated cells."""
        lines = [
            "# 🏆 AI Coding Agent Benchmark Leaderboard",
            "",
            f"**Run ID**: `{report.run_id}` | **Model**: `{report.config.get('llm_model', 'N/A')}`",
            "",
            "| Rank | Harness | Benchmark | Plugins | MCP | Pass@1 | Latency p50 | Tokens (In/Out) | Tool Calls |",
            "|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|",
        ]

        # Sort summaries by Pass@1 (descending), then Latency p50 (ascending)
        sorted_summaries = sorted(
            report.summaries,
            key=lambda s: (s.summary.pass_rate, -s.summary.latency_p50),
            reverse=True,
        )

        for rank, s in enumerate(sorted_summaries, 1):
            sum_d = s.summary
            p_str = ",".join(s.plugins) if s.plugins else "none"
            m_str = ",".join(s.mcp_servers) if s.mcp_servers else "none"
            toks_str = f"{sum_d.tokens_input_total:,} / {sum_d.tokens_output_total:,}"
            medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"

            lines.append(
                f"| {medal} | **`{s.harness}`** | `{s.benchmark}` | `{p_str}` | `{m_str}` | "
                f"**{sum_d.pass_rate * 100:.1f}%** | {sum_d.latency_p50:.2f}s | {toks_str} | {sum_d.tool_calls_total} |"
            )

        return "\n".join(lines)

    @staticmethod
    def render_task_drilldown_table(report: BenchmarkReport) -> str:
        """Render a per-task status drilldown table."""
        lines = [
            "### 📋 Task-by-Task Execution Breakdown",
            "",
            "| Harness | Benchmark | Task ID | Status | Duration | Tokens (In/Out) | Tools | Error / Notes |",
            "|:---|:---|:---|:---:|:---:|:---:|:---:|:---|",
        ]

        for r in report.results:
            status = "✅ PASS" if r.passed else "❌ FAIL"
            toks_str = f"{r.tokens_input or 0} / {r.tokens_output or 0}"
            tool_count = sum(r.tool_calls.values())
            err = r.error or ("Exit code 0" if r.passed else f"Exit code {r.exit_code}")
            lines.append(
                f"| `{r.harness}` | `{r.benchmark}` | `{r.task_id}` | {status} | "
                f"{r.duration_seconds:.2f}s | {toks_str} | {tool_count} | {err} |"
            )

        return "\n".join(lines)
