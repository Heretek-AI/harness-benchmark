"""Markdown and GitHub-summary report rendering.

Both renderers are pure-stdlib: no ``tabulate`` or ``markdown`` deps. The
table is intentionally narrow so it stays readable in a step summary,
which renders inside a narrow viewport on mobile and embedded views.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from benchmarks.runner import RunReport


def _fmt(value, spec: str = "") -> str:
    if value is None:
        return "-"
    if spec == "pct":
        return f"{value * 100:.1f}%"
    if spec == "usd":
        return f"${value:.4f}"
    if spec == "ms":
        return f"{value * 1000:.0f} ms"
    if spec == "int":
        return f"{value:,}"
    return str(value)


def render_json(report: RunReport) -> str:
    """Return the JSON-serialised report (helper for the CLI)."""
    import json

    return json.dumps(report.to_dict(), indent=2, default=str)


def render_markdown(report: RunReport) -> str:
    """Render a single ``RunReport`` as a Markdown comparison table."""
    lines: list[str] = []
    lines.append(f"# Benchmark run: `{report.config.name}`")
    lines.append("")
    lines.append(f"- **Run ID**: `{report.run_id}`")
    lines.append(f"- **Started**: `{report.started_at}`")
    if report.finished_at:
        lines.append(f"- **Finished**: `{report.finished_at}`")
    lines.append("")
    lines.append(
        "| Harness | Benchmark | Plugins | MCP | Pass@1 | Latency p50 | Latency p95 | Tokens (in/out) | Cost | Tasks |"
    )
    lines.append("|---|---|---|---|---:|---:|---:|---:|---:|---:|")
    for cell in report.metric_summaries:
        s = cell["summary"]
        plugins = ",".join(cell["plugins"]) or "none"
        mcp = ",".join(cell["mcp_servers"]) or "none"
        tokens = f"{_fmt(s['tokens_input_total'], 'int')}/{_fmt(s['tokens_output_total'], 'int')}"
        lines.append(
            "| {h} | {b} | {p} | {m} | {pass_} | {p50} | {p95} | {tok} | {cost} | {n} |".format(
                h=cell["harness"],
                b=cell["benchmark"],
                p=plugins,
                m=mcp,
                pass_=_fmt(s["pass_rate"], "pct"),
                p50=_fmt(s["latency_p50"], "ms"),
                p95=_fmt(s["latency_p95"], "ms"),
                tok=tokens,
                cost=_fmt(s["cost_usd_total"], "usd"),
                n=_fmt(s["count"], "int"),
            )
        )

    # Tool-call breakdown table.
    lines.append("")
    lines.append("## Tool call totals")
    lines.append("")
    lines.append("| Harness | Benchmark | Plugin | MCP | Tool | Count |")
    lines.append("|---|---|---|---|---|---:|")
    for cell in report.metric_summaries:
        for tool, count in cell["summary"]["tool_calls_by_name"].items():
            plugins = ",".join(cell["plugins"]) or "none"
            mcp = ",".join(cell["mcp_servers"]) or "none"
            lines.append(f"| {cell['harness']} | {cell['benchmark']} | {plugins} | {mcp} | {tool} | {count} |")
    return "\n".join(lines) + "\n"


def render_github_summary(report: RunReport) -> str:
    """Same as ``render_markdown`` with a run-header banner prepended."""
    banner = (
        f"## 🤖 Harness Benchmark — `{report.config.name}`\n\n"
        f"Run `{report.run_id}` "
        f"({len(report.results)} task(s) across "
        f"{len(report.metric_summaries)} cell(s))\n\n"
    )
    return banner + render_markdown(report)
