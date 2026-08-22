"""Tests for baseline regression detection."""

from __future__ import annotations

from pathlib import Path

from metrics.normalized_score import HarnessScore
from metrics.regression import RegressionDetector, RegressionReport


def _make_harness_scores() -> list[HarnessScore]:
    return [
        HarnessScore(
            harness="claude-code",
            cell_count=2,
            task_count=10,
            overall_score=0.8,
            pass_rate=0.8,
            mean_latency=10.0,
            total_tokens=5000,
            total_cost=0.05,
            benchmark_scores={"coder_eval": 0.9, "terminal-bench": 0.7},
        ),
        HarnessScore(
            harness="gemini-cli",
            cell_count=1,
            task_count=5,
            overall_score=0.6,
            pass_rate=0.6,
            mean_latency=8.0,
            total_tokens=3000,
            total_cost=0.03,
            benchmark_scores={"coder_eval": 0.6},
        ),
    ]


def test_save_and_load_baseline(tmp_path: Path) -> None:
    detector = RegressionDetector(baseline_dir=tmp_path)
    scores = _make_harness_scores()
    path = detector.save_baseline(scores, label="test")
    assert path.exists()

    baseline = detector.load_baseline("test")
    assert len(baseline) == 3  # claude-code x2 + gemini-cli x1
    assert baseline[0].harness == "claude-code"
    assert baseline[0].score == 0.9


def test_no_regressions(tmp_path: Path) -> None:
    detector = RegressionDetector(baseline_dir=tmp_path)
    scores = _make_harness_scores()
    detector.save_baseline(scores, label="baseline")

    # Same scores → no regressions
    report = detector.compare(scores, baseline_label="baseline")
    assert report.has_regressions is False
    assert report.regression_count == 0


def test_detects_regression(tmp_path: Path) -> None:
    detector = RegressionDetector(baseline_dir=tmp_path)
    baseline_scores = _make_harness_scores()
    detector.save_baseline(baseline_scores, label="baseline")

    # Current scores dropped significantly
    current_scores = [
        HarnessScore(
            harness="claude-code",
            cell_count=2,
            task_count=10,
            overall_score=0.5,
            pass_rate=0.5,
            mean_latency=10.0,
            total_tokens=5000,
            total_cost=0.05,
            benchmark_scores={"coder_eval": 0.5, "terminal-bench": 0.5},
        ),
    ]
    report = detector.compare(current_scores, baseline_label="baseline")
    assert report.has_regressions is True
    assert report.regression_count >= 1
    # coder_eval dropped from 0.9 to 0.5 = -44%
    coder_regressions = [r for r in report.regressions if r.benchmark == "coder_eval"]
    assert len(coder_regressions) == 1
    assert coder_regressions[0].delta < 0


def test_detects_improvement(tmp_path: Path) -> None:
    detector = RegressionDetector(baseline_dir=tmp_path)
    baseline_scores = [
        HarnessScore(
            harness="claude-code",
            cell_count=1,
            task_count=5,
            overall_score=0.5,
            pass_rate=0.5,
            mean_latency=10.0,
            total_tokens=5000,
            total_cost=0.05,
            benchmark_scores={"coder_eval": 0.5},
        ),
    ]
    detector.save_baseline(baseline_scores, label="baseline")

    current_scores = [
        HarnessScore(
            harness="claude-code",
            cell_count=1,
            task_count=5,
            overall_score=0.9,
            pass_rate=0.9,
            mean_latency=10.0,
            total_tokens=5000,
            total_cost=0.05,
            benchmark_scores={"coder_eval": 0.9},
        ),
    ]
    report = detector.compare(current_scores, baseline_label="baseline")
    assert report.improvement_count == 1
    assert report.improvements[0].delta > 0


def test_missing_baseline(tmp_path: Path) -> None:
    detector = RegressionDetector(baseline_dir=tmp_path)
    scores = _make_harness_scores()
    report = detector.compare(scores, baseline_label="nonexistent")
    assert report.regression_count == 0
    assert report.harnesses_compared == 0


def test_render_report_md(tmp_path: Path) -> None:
    detector = RegressionDetector(baseline_dir=tmp_path)
    scores = _make_harness_scores()
    detector.save_baseline(scores, label="baseline")

    current_scores = [
        HarnessScore(
            harness="claude-code",
            cell_count=2,
            task_count=10,
            overall_score=0.4,
            pass_rate=0.4,
            mean_latency=10.0,
            total_tokens=5000,
            total_cost=0.05,
            benchmark_scores={"coder_eval": 0.4, "terminal-bench": 0.4},
        ),
    ]
    report = detector.compare(current_scores, baseline_label="baseline")
    md = detector.render_report_md(report)
    assert "Regression Report" in md
    assert "claude-code" in md
    assert "coder_eval" in md
