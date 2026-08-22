"""Cross-harness normalized scoring system.

Converts raw execution results into 0-1 normalized scores that enable
fair comparison across harnesses, benchmarks, and task dimensions.

Scoring methodology:
    1. Per-task score: 1.0 if passed, 0.0 if failed (binary).
       For tasks with partial credit (rubric/judge), use the actual score.
    2. Per-cell aggregation: mean score across tasks for each
       (harness × benchmark × plugin × mcp) cell.
    3. Per-dimension aggregation: mean score across all cells for a
       given task dimension (e.g., "code_generation", "reasoning").
    4. Overall: weighted mean across dimensions.

Usage::

    from metrics.normalized_score import NormalizedScorer, HarnessScore

    scorer = NormalizedScorer()
    harness_scores = scorer.score_run(report)
    for hs in harness_scores:
        print(f"{hs.harness}: {hs.overall_score:.2f}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from core.types import BenchmarkReport, CellSummary, ExecutionResult, MetricSummary

logger = logging.getLogger(__name__)


@dataclass
class TaskScore:
    """Score for a single task execution."""

    task_id: str
    harness: str
    benchmark: str
    score: float  # 0.0 to 1.0
    passed: bool
    duration_seconds: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float | None = None
    plugins: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)


@dataclass
class CellScore:
    """Aggregated score for a single (harness × benchmark × plugin × mcp) cell."""

    harness: str
    benchmark: str
    plugins: list[str]
    mcp_servers: list[str]
    task_count: int
    mean_score: float
    pass_rate: float
    mean_latency: float
    total_tokens: int
    total_cost: float | None
    task_scores: list[TaskScore] = field(default_factory=list)


@dataclass
class HarnessScore:
    """Aggregated score for a single harness across all benchmarks."""

    harness: str
    cell_count: int
    task_count: int
    overall_score: float
    pass_rate: float
    mean_latency: float
    total_tokens: int
    total_cost: float | None
    benchmark_scores: dict[str, float] = field(default_factory=dict)
    cells: list[CellScore] = field(default_factory=list)

    @property
    def cost_efficiency(self) -> float | None:
        """Score per dollar of API cost."""
        if self.total_cost is None or self.total_cost <= 0:
            return None
        return self.overall_score / self.total_cost

    @property
    def speed_efficiency(self) -> float | None:
        """Score per second of wall-clock time."""
        if self.mean_latency <= 0:
            return None
        return self.overall_score / self.mean_latency


class NormalizedScorer:
    """Score and normalize results for cross-harness comparison."""

    def __init__(self, dimension_map: dict[str, list[str]] | None = None) -> None:
        """
        Args:
            dimension_map: Maps dimension names to benchmark names.
                If None, each benchmark is its own dimension.
        """
        self.dimension_map = dimension_map

    def score_run(self, report: BenchmarkReport) -> list[HarnessScore]:
        """Score all cells in a run report and return per-harness aggregates."""
        # 1. Extract per-task scores
        task_scores = self._extract_task_scores(report)

        # 2. Group by cell (harness × benchmark × plugin × mcp)
        cells = self._aggregate_cells(task_scores)

        # 3. Group by harness
        harness_scores = self._aggregate_harnesses(cells)

        return harness_scores

    def score_cells(self, summaries: list[CellSummary]) -> list[HarnessScore]:
        """Score from pre-aggregated cell summaries (faster, no per-task data)."""
        cells = []
        for s in summaries:
            ms = s.summary
            cells.append(CellScore(
                harness=s.harness,
                benchmark=s.benchmark,
                plugins=s.plugins,
                mcp_servers=s.mcp_servers,
                task_count=ms.count,
                mean_score=ms.pass_rate,  # pass_rate IS the normalized score
                pass_rate=ms.pass_rate or 0.0,
                mean_latency=ms.latency_p50 or 0.0,
                total_tokens=(ms.tokens_input_total or 0) + (ms.tokens_output_total or 0),
                total_cost=ms.cost_usd_total if ms.cost_usd_total else None,
            ))
        return self._aggregate_harnesses(cells)

    def _extract_task_scores(self, report: BenchmarkReport) -> list[TaskScore]:
        """Extract individual task scores from execution results."""
        scores = []
        for r in report.results:
            # Determine score from passed flag or any partial credit
            score = 1.0 if r.passed else 0.0
            scores.append(TaskScore(
                task_id=r.task_id,
                harness=r.harness,
                benchmark=r.benchmark,
                score=score,
                passed=bool(r.passed),
                duration_seconds=r.duration_seconds or 0.0,
                tokens_in=r.tokens_input or 0,
                tokens_out=r.tokens_output or 0,
                cost_usd=r.cost_usd,
            ))
        return scores

    def _aggregate_cells(self, task_scores: list[TaskScore]) -> list[CellScore]:
        """Group task scores by cell and compute cell-level aggregates."""
        from collections import defaultdict

        cell_groups: dict[tuple, list[TaskScore]] = defaultdict(list)
        for ts in task_scores:
            key = (ts.harness, ts.benchmark, tuple(ts.plugins), tuple(ts.mcp_servers))
            cell_groups[key].append(ts)

        cells = []
        for (harness, benchmark, plugins, mcp), tasks in cell_groups.items():
            n = len(tasks)
            if n == 0:
                continue
            mean_score = sum(t.score for t in tasks) / n
            pass_rate = sum(1 for t in tasks if t.passed) / n
            mean_lat = sum(t.duration_seconds for t in tasks) / n
            total_tok = sum(t.tokens_in + t.tokens_out for t in tasks)
            costs = [t.cost_usd for t in tasks if t.cost_usd is not None]
            total_cost = sum(costs) if costs else None

            cells.append(CellScore(
                harness=harness,
                benchmark=benchmark,
                plugins=list(plugins),
                mcp_servers=list(mcp),
                task_count=n,
                mean_score=mean_score,
                pass_rate=pass_rate,
                mean_latency=mean_lat,
                total_tokens=total_tok,
                total_cost=total_cost,
                task_scores=tasks,
            ))

        return cells

    def _aggregate_harnesses(self, cells: list[CellScore]) -> list[HarnessScore]:
        """Group cells by harness and compute harness-level aggregates."""
        from collections import defaultdict

        harness_groups: dict[str, list[CellScore]] = defaultdict(list)
        for c in cells:
            harness_groups[c.harness].append(c)

        harness_scores = []
        for harness, hcells in sorted(harness_groups.items()):
            total_tasks = sum(c.task_count for c in hcells)
            if total_tasks == 0:
                continue

            # Weighted mean score (weighted by task count)
            overall_score = sum(c.mean_score * c.task_count for c in hcells) / total_tasks
            pass_rate = sum(c.pass_rate * c.task_count for c in hcells) / total_tasks
            mean_latency = sum(c.mean_latency * c.task_count for c in hcells) / total_tasks
            total_tokens = sum(c.total_tokens for c in hcells)
            costs = [c.total_cost for c in hcells if c.total_cost is not None]
            total_cost = sum(costs) if costs else None

            # Per-benchmark scores
            bench_scores: dict[str, float] = {}
            for c in hcells:
                if c.benchmark not in bench_scores:
                    bench_scores[c.benchmark] = c.mean_score
                else:
                    # Average if multiple cells for same benchmark
                    bench_scores[c.benchmark] = (bench_scores[c.benchmark] + c.mean_score) / 2

            harness_scores.append(HarnessScore(
                harness=harness,
                cell_count=len(hcells),
                task_count=total_tasks,
                overall_score=overall_score,
                pass_rate=pass_rate,
                mean_latency=mean_latency,
                total_tokens=total_tokens,
                total_cost=total_cost,
                benchmark_scores=bench_scores,
                cells=hcells,
            ))

        # Sort by overall score descending
        harness_scores.sort(key=lambda h: h.overall_score, reverse=True)
        return harness_scores

    def compute_dimensions(
        self, harness_scores: list[HarnessScore]
    ) -> dict[str, dict[str, float]]:
        """Compute per-dimension scores for each harness.

        Returns:
            {dimension_name: {harness_name: score}}
        """
        if not self.dimension_map:
            # Each benchmark is its own dimension
            dimensions: dict[str, dict[str, float]] = {}
            for hs in harness_scores:
                for bench, score in hs.benchmark_scores.items():
                    if bench not in dimensions:
                        dimensions[bench] = {}
                    dimensions[bench][hs.harness] = score
            return dimensions

        dimensions = {}
        for dim_name, benchmarks in self.dimension_map.items():
            dim_scores: dict[str, float] = {}
            for hs in harness_scores:
                scores = [hs.benchmark_scores.get(b, 0.0) for b in benchmarks]
                if scores:
                    dim_scores[hs.harness] = sum(scores) / len(scores)
            dimensions[dim_name] = dim_scores

        return dimensions
