"""Auto-file GitHub Issues for detected performance regressions.

Usage::

    from reporting.regression_issue import RegressionIssueReporter
    from metrics.regression import RegressionDetector

    reporter = RegressionIssueReporter(owner="Heretek-AI", repo="harness-benchmark")
    detector = RegressionDetector()
    report = detector.compare(current_scores)

    if report.has_regressions:
        issue_url = reporter.create_issue(report)
        print(f"Filed regression issue: {issue_url}")
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from metrics.regression import RegressionReport

logger = logging.getLogger(__name__)


class RegressionIssueReporter:
    """Create GitHub Issues for performance regressions."""

    def __init__(
        self,
        owner: str = "Heretek-AI",
        repo: str = "harness-benchmark",
        dry_run: bool = False,
    ) -> None:
        self.owner = owner
        self.repo = repo
        self.dry_run = dry_run

    def create_issue(
        self,
        report: RegressionReport,
        run_url: str | None = None,
        commit_sha: str | None = None,
    ) -> str | None:
        """Create a GitHub Issue for detected regressions.

        Returns:
            Issue URL if created, None if dry_run or no regressions.
        """
        if not report.has_regressions:
            return None

        title = self._build_title(report)
        body = self._build_body(report, run_url=run_url, commit_sha=commit_sha)
        labels = self._build_labels(report)

        if self.dry_run:
            logger.info("DRY RUN — would create issue:\n%s\n\nLabels: %s", title, labels)
            return None

        try:
            import subprocess
            result = subprocess.run(
                [
                    "gh", "issue", "create",
                    "--repo", f"{self.owner}/{self.repo}",
                    "--title", title,
                    "--body", body,
                    "--label", ",".join(labels),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                logger.info("Created regression issue: %s", url)
                return url
            else:
                logger.error("Failed to create issue: %s", result.stderr)
                return None
        except Exception as e:
            logger.error("Error creating issue: %s", e)
            return None

    def _build_title(self, report: RegressionReport) -> str:
        """Build issue title."""
        worst = report.regressions[0]
        return (
            f"⚠️ Performance Regression: {worst.harness}/{worst.benchmark} "
            f"dropped {abs(worst.delta_pct):.1f}%"
        )

    def _build_body(
        self,
        report: RegressionReport,
        run_url: str | None = None,
        commit_sha: str | None = None,
    ) -> str:
        """Build issue body in Markdown."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        lines = [
            "## ⚠️ Performance Regression Detected",
            "",
            f"**Detected**: {now}",
            f"**Baseline**: `{report.baseline_label}`",
            f"**Harnesses compared**: {report.harnesses_compared}",
            f"**Benchmarks compared**: {report.benchmarks_compared}",
            "",
        ]

        if run_url:
            lines.append(f"**CI Run**: {run_url}")
        if commit_sha:
            lines.append(f"**Commit**: `{commit_sha}`")
        lines.append("")

        # Regression table
        lines.append("### Regressions")
        lines.append("")
        lines.append("| Harness | Benchmark | Baseline | Current | Delta | Change |")
        lines.append("|---|---|---:|---:|---:|---:|")
        for r in report.regressions:
            lines.append(
                f"| {r.harness} | {r.benchmark} | "
                f"{r.baseline_score:.2%} | {r.current_score:.2%} | "
                f"{r.delta:+.2%} | {r.delta_pct:+.1f}% |"
            )
        lines.append("")

        # Improvements
        if report.improvements:
            lines.append("### Improvements")
            lines.append("")
            lines.append("| Harness | Benchmark | Baseline | Current | Delta | Change |")
            lines.append("|---|---|---:|---:|---:|---:|")
            for r in report.improvements:
                lines.append(
                    f"| {r.harness} | {r.benchmark} | "
                    f"{r.baseline_score:.2%} | {r.current_score:.2%} | "
                    f"{r.delta:+.2%} | {r.delta_pct:+.1f}% |"
                )
            lines.append("")

        # Action items
        lines.extend([
            "### Action Items",
            "",
            "- [ ] Investigate root cause of regression",
            "- [ ] Check if model version changed",
            "- [ ] Verify task dataset hasn't shifted",
            "- [ ] Run ablation to isolate component",
            "- [ ] Update baseline if regression is expected",
            "",
            "---",
            "*Auto-generated by harness-benchmark CI*",
        ])

        return "\n".join(lines)

    def _build_labels(self, report: RegressionReport) -> list[str]:
        """Build issue labels."""
        labels = ["regression", "automated"]

        # Add severity based on worst regression
        worst_delta = min(r.delta_pct for r in report.regressions)
        if worst_delta < -30:
            labels.append("severity/critical")
        elif worst_delta < -20:
            labels.append("severity/high")
        elif worst_delta < -10:
            labels.append("severity/medium")

        # Add harness-specific labels
        harnesses = {r.harness for r in report.regressions}
        for h in harnesses:
            labels.append(f"harness/{h}")

        return labels
