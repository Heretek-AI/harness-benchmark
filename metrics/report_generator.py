"""Markdown and GitHub-summary report rendering for Harness Benchmark 2.0."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from benchmarks.runner import RunReport


def _fmt(value: Any, spec: str = "") -> str:
    if value is None:
        return "-"
    if spec == "pct":
        return f"{value * 100:.1f}%"
    if spec == "usd":
        return f"${value:.4f}"
    if spec == "ms":
        return f"{value * 1000:.0f} ms"
    if spec == "sec":
        return f"{value:.2f}s"
    if spec == "int":
        return f"{value:,}"
    return str(value)


def render_json(report: RunReport) -> str:
    """Return the JSON-serialised report (helper for the CLI)."""
    import json

    return json.dumps(report.to_dict(), indent=2, default=str)


def render_markdown(report: RunReport) -> str:
    """Render a comprehensive Markdown report with multi-tier comparison and tool analytics."""
    lines: list[str] = []
    lines.append(f"# 📊 AI Coding Agent Benchmark Report: `{report.config.name}`")
    lines.append("")
    lines.append(f"- **Run ID**: `{report.run_id}`")
    lines.append(f"- **Started**: `{report.started_at}`")
    if report.finished_at:
        lines.append(f"- **Finished**: `{report.finished_at}`")
    lines.append("")

    # 1. Executive Summary / Leaderboard Table
    lines.append("## 🏆 Multi-Harness Leaderboard")
    lines.append("")
    lines.append(
        "| Harness | Benchmark | Tier | Plugins | MCP | Pass@1 | Latency p50 | Avg Turns | Tokens (in/out) | Cost | Tasks |"
    )
    lines.append("|:---|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|")
    for cell in report.metric_summaries:
        s = cell["summary"]
        tier = s.get("tier", "tier_0_bare")
        plugins = ",".join(cell["plugins"]) or "none"
        mcp = ",".join(cell["mcp_servers"]) or "none"
        tokens = f"{_fmt(s['tokens_input_total'], 'int')}/{_fmt(s['tokens_output_total'], 'int')}"
        turns_str = f"{s.get('turns_mean', 1.0):.1f}"
        lines.append(
            f"| **`{cell['harness']}`** | `{cell['benchmark']}` | `{tier}` | `{plugins}` | `{mcp}` | "
            f"**{_fmt(s['pass_rate'], 'pct')}** | {_fmt(s['latency_p50'], 'sec')} | {turns_str} | {tokens} | "
            f"{_fmt(s['cost_usd_total'], 'usd')} | {_fmt(s['count'], 'int')} |"
        )

    # 2. Tool-Call Breakdown Table
    lines.append("")
    lines.append("## ⚙️  Tool Call Frequency & Telemetry")
    lines.append("")
    lines.append("| Harness | Benchmark | Plugin | MCP | Tool | Count |")
    lines.append("|---|---|---|---|---|---:|")
    for cell in report.metric_summaries:
        for tool, count in cell["summary"]["tool_calls_by_name"].items():
            plugins = ",".join(cell["plugins"]) or "none"
            mcp = ",".join(cell["mcp_servers"]) or "none"
            lines.append(
                f"| `{cell['harness']}` | `{cell['benchmark']}` | `{plugins}` | `{mcp}` | `{tool}` | {count} |"
            )

    # 3. Failure Breakdown (if any)
    has_failures = any(cell["summary"].get("failure_breakdown") for cell in report.metric_summaries)
    if has_failures:
        lines.append("")
        lines.append("## ❌ Failure Classification Analysis")
        lines.append("")
        lines.append("| Harness | Benchmark | Failure Category | Count |")
        lines.append("|---|---|---|---:|")
        for cell in report.metric_summaries:
            for cat, count in cell["summary"].get("failure_breakdown", {}).items():
                lines.append(f"| `{cell['harness']}` | `{cell['benchmark']}` | `{cat}` | {count} |")

    return "\n".join(lines) + "\n"


def render_github_summary(report: RunReport) -> str:
    """Render full markdown with prominent GitHub Step Summary banner."""
    banner = (
        f"## 🤖 Harness Benchmark 2.0 — `{report.config.name}`\n\n"
        f"Run `{report.run_id}`: Evaluated **{len(report.results)} task(s)** across "
        f"**{len(report.metric_summaries)} matrix cell(s)**.\n\n"
    )
    return banner + render_markdown(report)
