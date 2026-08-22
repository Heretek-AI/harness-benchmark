"""Tests for regression GitHub Issue reporter."""

from __future__ import annotations

from metrics.normalized_score import HarnessScore
from metrics.regression import RegressionDetector
from reporting.regression_issue import RegressionIssueReporter


def _make_report_with_regressions():
    detector = RegressionDetector()
    baseline = [
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
    detector.save_baseline(baseline, label="test-baseline")

    current = [
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
    return detector.compare(current, baseline_label="test-baseline")


def test_reporter_title() -> None:
    reporter = RegressionIssueReporter(dry_run=True)
    report = _make_report_with_regressions()
    title = reporter._build_title(report)
    assert "claude-code" in title
    assert "coder_eval" in title
    assert "⚠️" in title


def test_reporter_body() -> None:
    reporter = RegressionIssueReporter(dry_run=True)
    report = _make_report_with_regressions()
    body = reporter._build_body(report, run_url="https://example.com/run/123")
    assert "Performance Regression" in body
    assert "claude-code" in body
    assert "coder_eval" in body
    assert "https://example.com/run/123" in body


def test_reporter_labels() -> None:
    reporter = RegressionIssueReporter(dry_run=True)
    report = _make_report_with_regressions()
    labels = reporter._build_labels(report)
    assert "regression" in labels
    assert "automated" in labels
    assert "severity/critical" in labels  # >30% drop
    assert "harness/claude-code" in labels


def test_reporter_dry_run() -> None:
    reporter = RegressionIssueReporter(dry_run=True)
    report = _make_report_with_regressions()
    result = reporter.create_issue(report)
    assert result is None  # dry run returns None


def test_reporter_no_regressions() -> None:
    reporter = RegressionIssueReporter(dry_run=True)
    report = type("R", (), {"has_regressions": False, "regressions": []})()
    result = reporter.create_issue(report)
    assert result is None
