"""Leaderboard generator for cross-harness comparison.

Produces ranked tables in Markdown and JSON formats with confidence
intervals, cost-efficiency metrics, and per-dimension breakdowns.

Usage::

    from metrics.leaderboard import LeaderboardGenerator
    from metrics.normalized_score import NormalizedScorer

    scorer = NormalizedScorer()
    harness_scores = scorer.score_run(report)
    gen = LeaderboardGenerator()
    md = gen.render_markdown(harness_scores)
    data = gen.render_json(harness_scores)
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from metrics.normalized_score import HarnessScore

logger = logging.getLogger(__name__)


@dataclass
class LeaderboardEntry:
    """One row in the leaderboard."""

    rank: int
    harness: str
    overall_score: float
    pass_rate: float
    mean_latency: float
    total_tokens: int
    total_cost: float | None
    cost_efficiency: float | None
    speed_efficiency: float | None
    task_count: int
    benchmark_scores: dict[str, float] = field(default_factory=dict)
    confidence_interval: tuple[float, float] | None = None  # (lower, upper)


class LeaderboardGenerator:
    """Generate leaderboards from normalized harness scores."""

    def __init__(self, title: str = "AI Agent Harness Leaderboard") -> None:
        self.title = title

    def build_entries(self, harness_scores: list[HarnessScore]) -> list[LeaderboardEntry]:
        """Build sorted leaderboard entries from harness scores."""
        entries = []
        for rank, hs in enumerate(harness_scores, 1):
            entries.append(LeaderboardEntry(
                rank=rank,
                harness=hs.harness,
                overall_score=hs.overall_score,
                pass_rate=hs.pass_rate,
                mean_latency=hs.mean_latency,
                total_tokens=hs.total_tokens,
                total_cost=hs.total_cost,
                cost_efficiency=hs.cost_efficiency,
                speed_efficiency=hs.speed_efficiency,
                task_count=hs.task_count,
                benchmark_scores=hs.benchmark_scores,
            ))
        return entries

    def render_markdown(
        self,
        harness_scores: list[HarnessScore],
        show_benchmarks: bool = True,
    ) -> str:
        """Render leaderboard as a Markdown table."""
        entries = self.build_entries(harness_scores)
        lines = [
            f"## {self.title}",
            "",
            f"*{len(entries)} harnesses evaluated across "
            f"{sum(e.task_count for e in entries)} total tasks*",
            "",
        ]

        # Main leaderboard table
        lines.append("| Rank | Harness | Score | Pass Rate | Latency p50 | Tokens | Cost | Tasks |")
        lines.append("|---:|---|---:|---:|---:|---:|---:|---:|")

        medals = {1: "🥇", 2: "🥈", 3: "🥉"}

        for e in entries:
            medal = medals.get(e.rank, "")
            cost_str = f"${e.total_cost:.4f}" if e.total_cost else "—"
            ci_str = ""
            if e.confidence_interval:
                lo, hi = e.confidence_interval
                ci_str = f" [{lo:.2f}–{hi:.2f}]"
            lines.append(
                f"| {medal}{e.rank} | **{e.harness}** | "
                f"{e.overall_score:.2%}{ci_str} | "
                f"{e.pass_rate:.1%} | "
                f"{e.mean_latency:.1f}s | "
                f"{e.total_tokens:,} | "
                f"{cost_str} | "
                f"{e.task_count} |"
            )

        # Per-benchmark breakdown
        if show_benchmarks and entries:
            all_benchmarks = set()
            for e in entries:
                all_benchmarks.update(e.benchmark_scores.keys())
            if all_benchmarks:
                lines.extend(["", "### Per-Benchmark Scores", ""])
                bench_sorted = sorted(all_benchmarks)
                header = "| Harness | " + " | ".join(bench_sorted) + " |"
                sep = "|---|" + "|".join(["---:"] * len(bench_sorted)) + "|"
                lines.extend([header, sep])
                for e in entries:
                    row = f"| {e.harness} |"
                    for b in bench_sorted:
                        score = e.benchmark_scores.get(b)
                        row += f" {score:.2%} |" if score is not None else " — |"
                    lines.append(row)

        # Efficiency metrics
        has_efficiency = any(e.cost_efficiency is not None for e in entries)
        if has_efficiency:
            lines.extend(["", "### Efficiency Metrics", ""])
            lines.append("| Harness | Score/Dollar | Score/Second |")
            lines.append("|---|---:|---:|")
            for e in entries:
                cost_eff = f"{e.cost_efficiency:.2f}" if e.cost_efficiency else "—"
                speed_eff = f"{e.speed_efficiency:.4f}" if e.speed_efficiency else "—"
                lines.append(f"| {e.harness} | {cost_eff} | {speed_eff} |")

        lines.append("")
        return "\n".join(lines)

    def render_json(self, harness_scores: list[HarnessScore]) -> dict[str, Any]:
        """Render leaderboard as a JSON-serializable dict."""
        entries = self.build_entries(harness_scores)
        return {
            "title": self.title,
            "harness_count": len(entries),
            "total_tasks": sum(e.task_count for e in entries),
            "entries": [
                {
                    "rank": e.rank,
                    "harness": e.harness,
                    "overall_score": round(e.overall_score, 4),
                    "pass_rate": round(e.pass_rate, 4),
                    "mean_latency": round(e.mean_latency, 2),
                    "total_tokens": e.total_tokens,
                    "total_cost": round(e.total_cost, 6) if e.total_cost else None,
                    "cost_efficiency": round(e.cost_efficiency, 4) if e.cost_efficiency else None,
                    "speed_efficiency": round(e.speed_efficiency, 6) if e.speed_efficiency else None,
                    "task_count": e.task_count,
                    "benchmark_scores": {k: round(v, 4) for k, v in e.benchmark_scores.items()},
                }
                for e in entries
            ],
        }

    def render_comparison_matrix(
        self,
        harness_scores: list[HarnessScore],
    ) -> str:
        """Render a pairwise comparison matrix (harness vs harness)."""
        harnesses = [hs.harness for hs in harness_scores]
        scores = {hs.harness: hs.overall_score for hs in harness_scores}
        n = len(harnesses)

        lines = [
            "### Pairwise Comparison Matrix",
            "",
            "*Cell (A, B) = score_A - score_B. Positive = A outperforms B.*",
            "",
        ]

        header = "| | " + " | ".join(harnesses) + " |"
        sep = "|---|" + "|".join(["---:" ] * n) + "|"
        lines.extend([header, sep])

        for h1 in harnesses:
            row = f"| **{h1}** |"
            for h2 in harnesses:
                if h1 == h2:
                    row += " — |"
                else:
                    diff = scores[h1] - scores[h2]
                    sign = "+" if diff > 0 else ""
                    row += f" {sign}{diff:.2%} |"
            lines.append(row)

        lines.append("")
        return "\n".join(lines)
