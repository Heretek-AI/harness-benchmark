"""Baseline regression detection for benchmark results.

Compares a new run's scores against stored baselines and flags
regressions where performance dropped significantly.

Usage::

    from metrics.regression import RegressionDetector, detect_regressions

    detector = RegressionDetector(baseline_dir=Path("results/baseline"))
    regressions = detector.compare(current_scores)

    # Or save/load baselines
    detector.save_baseline(harness_scores, label="main-2026-08-22")
    baseline = detector.load_baseline("main-2026-08-22")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from metrics.normalized_score import HarnessScore

logger = logging.getLogger(__name__)


@dataclass
class Regression:
    """A detected regression for a single harness × benchmark pair."""

    harness: str
    benchmark: str
    baseline_score: float
    current_score: float
    delta: float  # negative = regression
    delta_pct: float  # percentage change
    baseline_tasks: int = 0
    current_tasks: int = 0


@dataclass
class RegressionReport:
    """Full regression report comparing current run against baseline."""

    baseline_label: str
    regressions: list[Regression]
    improvements: list[Regression]
    harnesses_compared: int
    benchmarks_compared: int

    @property
    def has_regressions(self) -> bool:
        return len(self.regressions) > 0

    @property
    def regression_count(self) -> int:
        return len(self.regressions)

    @property
    def improvement_count(self) -> int:
        return len(self.improvements)


@dataclass
class BaselineEntry:
    """A single baseline score entry."""

    harness: str
    benchmark: str
    score: float
    pass_rate: float
    task_count: int
    timestamp: str = ""


class RegressionDetector:
    """Detect performance regressions by comparing against baselines."""

    def __init__(
        self,
        baseline_dir: Path | None = None,
        regression_threshold: float = -0.10,
    ) -> None:
        """
        Args:
            baseline_dir: Directory containing baseline JSON files.
            regression_threshold: Minimum drop to flag as regression
                (default -0.10 = 10% drop).
        """
        self.baseline_dir = baseline_dir or Path("results/baseline")
        self.regression_threshold = regression_threshold

    def save_baseline(
        self,
        harness_scores: list[HarnessScore],
        label: str = "latest",
    ) -> Path:
        """Save current scores as a baseline."""
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        data = []
        for hs in harness_scores:
            for bench, score in hs.benchmark_scores.items():
                data.append({
                    "harness": hs.harness,
                    "benchmark": bench,
                    "score": round(score, 4),
                    "pass_rate": round(hs.pass_rate, 4),
                    "task_count": hs.task_count,
                })
        path = self.baseline_dir / f"{label}.json"
        path.write_text(json.dumps(data, indent=2))
        logger.info("Saved baseline with %d entries to %s", len(data), path)
        return path

    def load_baseline(self, label: str = "latest") -> list[BaselineEntry]:
        """Load a baseline from disk."""
        path = self.baseline_dir / f"{label}.json"
        if not path.exists():
            logger.warning("Baseline not found: %s", path)
            return []
        data = json.loads(path.read_text())
        return [
            BaselineEntry(
                harness=e["harness"],
                benchmark=e["benchmark"],
                score=e["score"],
                pass_rate=e.get("pass_rate", 0.0),
                task_count=e.get("task_count", 0),
            )
            for e in data
        ]

    def compare(
        self,
        current_scores: list[HarnessScore],
        baseline_label: str = "latest",
    ) -> RegressionReport:
        """Compare current scores against a stored baseline."""
        baseline = self.load_baseline(baseline_label)
        if not baseline:
            return RegressionReport(
                baseline_label=baseline_label,
                regressions=[],
                improvements=[],
                harnesses_compared=0,
                benchmarks_compared=0,
            )

        # Index baseline by (harness, benchmark)
        baseline_map: dict[tuple[str, str], BaselineEntry] = {}
        for b in baseline:
            baseline_map[(b.harness, b.benchmark)] = b

        regressions: list[Regression] = []
        improvements: list[Regression] = []
        harnesses_compared: set[str] = set()
        benchmarks_compared: set[str] = set()

        for hs in current_scores:
            for bench, current_score in hs.benchmark_scores.items():
                key = (hs.harness, bench)
                base = baseline_map.get(key)
                if base is None:
                    continue

                harnesses_compared.add(hs.harness)
                benchmarks_compared.add(bench)

                delta = current_score - base.score
                delta_pct = (delta / base.score * 100) if base.score > 0 else 0.0

                reg = Regression(
                    harness=hs.harness,
                    benchmark=bench,
                    baseline_score=base.score,
                    current_score=current_score,
                    delta=delta,
                    delta_pct=delta_pct,
                    baseline_tasks=base.task_count,
                    current_tasks=hs.task_count,
                )

                if delta < self.regression_threshold:
                    regressions.append(reg)
                elif delta > abs(self.regression_threshold):
                    improvements.append(reg)

        regressions.sort(key=lambda r: r.delta)

        return RegressionReport(
            baseline_label=baseline_label,
            regressions=regressions,
            improvements=improvements,
            harnesses_compared=len(harnesses_compared),
            benchmarks_compared=len(benchmarks_compared),
        )

    def render_report_md(self, report: RegressionReport) -> str:
        """Render a regression report as Markdown."""
        lines = [
            "## Regression Report",
            "",
            f"Baseline: `{report.baseline_label}` | "
            f"Harnesses: {report.harnesses_compared} | "
            f"Benchmarks: {report.benchmarks_compared}",
            "",
        ]

        if not report.has_regressions:
            lines.append("✅ **No regressions detected.**")
        else:
            lines.append(f"⚠️ **{report.regression_count} regression(s) detected:**")
            lines.append("")
            lines.append("| Harness | Benchmark | Baseline | Current | Delta | Change |")
            lines.append("|---|---|---:|---:|---:|---:|")
            for r in report.regressions:
                lines.append(
                    f"| {r.harness} | {r.benchmark} | "
                    f"{r.baseline_score:.2%} | {r.current_score:.2%} | "
                    f"{r.delta:+.2%} | {r.delta_pct:+.1f}% |"
                )

        if report.improvements:
            lines.extend(["", f"📈 **{report.improvement_count} improvement(s):**", ""])
            lines.append("| Harness | Benchmark | Baseline | Current | Delta | Change |")
            lines.append("|---|---|---:|---:|---:|---:|")
            for r in report.improvements:
                lines.append(
                    f"| {r.harness} | {r.benchmark} | "
                    f"{r.baseline_score:.2%} | {r.current_score:.2%} | "
                    f"{r.delta:+.2%} | {r.delta_pct:+.1f}% |"
                )

        lines.append("")
        return "\n".join(lines)
