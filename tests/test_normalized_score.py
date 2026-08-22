"""Tests for normalized scoring and leaderboard generation."""

from __future__ import annotations

from core.types import BenchmarkReport, CellSummary, ExecutionResult, MetricSummary
from metrics.leaderboard import LeaderboardGenerator
from metrics.normalized_score import CellScore, HarnessScore, NormalizedScorer, TaskScore


def _make_report() -> BenchmarkReport:
    """Create a synthetic report with 2 harnesses, 2 benchmarks."""
    return BenchmarkReport(
        run_id="test-run",
        name="test",
        config={},
        summaries=[
            CellSummary(
                harness="claude-code",
                benchmark="coder_eval",
                plugins=[],
                mcp_servers=[],
                summary=MetricSummary(
                    count=5,
                    passed_count=4,
                    pass_rate=0.8,
                    latency_p50=10.0,
                    tokens_input_total=5000,
                    tokens_output_total=1000,
                    cost_usd_total=0.05,
                ),
            ),
            CellSummary(
                harness="gemini-cli",
                benchmark="coder_eval",
                plugins=[],
                mcp_servers=[],
                summary=MetricSummary(
                    count=5,
                    passed_count=3,
                    pass_rate=0.6,
                    latency_p50=8.0,
                    tokens_input_total=4000,
                    tokens_output_total=800,
                    cost_usd_total=0.03,
                ),
            ),
            CellSummary(
                harness="claude-code",
                benchmark="terminal-bench",
                plugins=[],
                mcp_servers=[],
                summary=MetricSummary(
                    count=3,
                    passed_count=2,
                    pass_rate=0.667,
                    latency_p50=15.0,
                    tokens_input_total=3000,
                    tokens_output_total=600,
                    cost_usd_total=0.04,
                ),
            ),
        ],
        results=[],
    )


def test_score_cells_returns_sorted_harnesses() -> None:
    report = _make_report()
    scorer = NormalizedScorer()
    scores = scorer.score_cells(report.summaries)
    assert len(scores) == 2
    # claude-code should be first (higher score)
    assert scores[0].harness == "claude-code"
    assert scores[1].harness == "gemini-cli"


def test_overall_score_is_weighted() -> None:
    report = _make_report()
    scorer = NormalizedScorer()
    scores = scorer.score_cells(report.summaries)
    claude = scores[0]
    # claude-code: (0.8*5 + 0.667*3) / (5+3) = (4.0 + 2.0) / 8 = 0.75
    assert abs(claude.overall_score - 0.75) < 0.01
    assert claude.task_count == 8


def test_benchmark_scores() -> None:
    report = _make_report()
    scorer = NormalizedScorer()
    scores = scorer.score_cells(report.summaries)
    claude = scores[0]
    assert "coder_eval" in claude.benchmark_scores
    assert "terminal-bench" in claude.benchmark_scores
    assert abs(claude.benchmark_scores["coder_eval"] - 0.8) < 0.01


def test_cost_efficiency() -> None:
    report = _make_report()
    scorer = NormalizedScorer()
    scores = scorer.score_cells(report.summaries)
    claude = scores[0]
    # cost = 0.05 + 0.04 = 0.09
    assert claude.total_cost is not None
    assert claude.cost_efficiency is not None
    assert claude.cost_efficiency > 0


def test_leaderboard_markdown() -> None:
    report = _make_report()
    scorer = NormalizedScorer()
    scores = scorer.score_cells(report.summaries)
    gen = LeaderboardGenerator()
    md = gen.render_markdown(scores)
    assert "claude-code" in md
    assert "gemini-cli" in md
    assert "Leaderboard" in md
    assert "Rank" in md


def test_leaderboard_json() -> None:
    report = _make_report()
    scorer = NormalizedScorer()
    scores = scorer.score_cells(report.summaries)
    gen = LeaderboardGenerator()
    data = gen.render_json(scores)
    assert data["harness_count"] == 2
    assert len(data["entries"]) == 2
    assert data["entries"][0]["harness"] == "claude-code"
    assert "overall_score" in data["entries"][0]


def test_comparison_matrix() -> None:
    report = _make_report()
    scorer = NormalizedScorer()
    scores = scorer.score_cells(report.summaries)
    gen = LeaderboardGenerator()
    matrix = gen.render_comparison_matrix(scores)
    assert "claude-code" in matrix
    assert "gemini-cli" in matrix
    assert "Pairwise" in matrix


def test_empty_report() -> None:
    report = BenchmarkReport(
        run_id="empty",
        name="empty",
        config={},
        summaries=[],
        results=[],
    )
    scorer = NormalizedScorer()
    scores = scorer.score_cells(report.summaries)
    assert len(scores) == 0


def test_dimension_computation() -> None:
    report = _make_report()
    scorer = NormalizedScorer()
    scores = scorer.score_cells(report.summaries)
    dims = scorer.compute_dimensions(scores)
    assert "coder_eval" in dims
    assert "terminal-bench" in dims
    assert "claude-code" in dims["coder_eval"]


def test_dimension_with_custom_map() -> None:
    report = _make_report()
    scorer = NormalizedScorer(dimension_map={
        "coding": ["coder_eval", "terminal-bench"],
    })
    scores = scorer.score_cells(report.summaries)
    dims = scorer.compute_dimensions(scores)
    assert "coding" in dims
    assert "claude-code" in dims["coding"]


def test_leaderboard_empty() -> None:
    gen = LeaderboardGenerator()
    md = gen.render_markdown([])
    assert "0 harnesses" in md


def test_entry_properties() -> None:
    hs = HarnessScore(
        harness="test",
        cell_count=1,
        task_count=10,
        overall_score=0.85,
        pass_rate=0.9,
        mean_latency=5.0,
        total_tokens=1000,
        total_cost=0.01,
    )
    assert hs.cost_efficiency == 85.0
    assert abs(hs.speed_efficiency - 0.17) < 0.001
