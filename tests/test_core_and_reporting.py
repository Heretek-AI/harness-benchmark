"""Unit and integration tests for Core, Extensions, Evaluation, and Reporting subsystems."""

from __future__ import annotations

from pathlib import Path

from core.logger import BenchmarkLogger
from core.types import (
    BenchmarkReport,
    CellSummary,
    ExecutionResult,
    MetricSummary,
    TaskSpec,
    ToolCall,
)
from evaluation.oracle import OracleEvaluator
from metrics.junit_exporter import export_junit_xml
from reporting.ab_comparator import ABComparator
from reporting.github_issue import GitHubIssuePublisher
from reporting.scorecard import ScorecardGenerator


def test_core_types_serialization() -> None:
    task = TaskSpec(task_id="t1", prompt="echo 'hello'")
    assert task.task_id == "t1"

    tool = ToolCall(name="bash", arguments={"command": "ls -la"}, result="file1.txt")
    assert tool.name == "bash"

    result = ExecutionResult(
        harness="stub",
        benchmark="coder_eval",
        task_id="t1",
        exit_code=0,
        duration_seconds=1.2,
        stdout="def add(a, b):\n    return a + b\n",
        passed=True,
    )
    dumped = result.model_dump()
    assert dumped["harness"] == "stub"
    assert dumped["passed"] is True


def test_logger_methods(capsys) -> None:
    log = BenchmarkLogger(debug=True, quiet=False)
    log.banner("Test Banner")
    log.cell_start("claude-code", "coder_eval", ["caveman"], ["context7"], 5)
    log.task_start("ce-001", "Implement function")
    log.agent_turn(1, "write_file", "path='test.py'")
    log.oracle_check("ce-001", True, "All asserts passed")
    log.task_finish("ce-001", True, 2.5, 100, 50, 1)

    captured = capsys.readouterr().out
    assert "Test Banner" in captured
    assert "claude-code" in captured
    assert "ce-001" in captured


def test_oracle_evaluator_python(tmp_path: Path) -> None:
    res_pass = ExecutionResult(
        harness="stub",
        benchmark="coder_eval",
        task_id="ce-py-001",
        exit_code=0,
        duration_seconds=0.5,
        stdout="```python\ndef multiply(x, y):\n    return x * y\n```",
    )
    passed, log = OracleEvaluator.evaluate_python_asserts(
        res_pass,
        "assert multiply(3, 4) == 12\nassert multiply(0, 5) == 0",
        function_name="multiply",
        cwd=tmp_path,
    )
    assert passed is True
    assert "passed successfully" in log

    res_fail = ExecutionResult(
        harness="stub",
        benchmark="coder_eval",
        task_id="ce-py-001",
        exit_code=0,
        duration_seconds=0.5,
        stdout="```python\ndef multiply(x, y):\n    return x + y\n```",
    )
    passed_f, log_f = OracleEvaluator.evaluate_python_asserts(
        res_fail,
        "assert multiply(3, 4) == 12",
        function_name="multiply",
        cwd=tmp_path,
    )
    assert passed_f is False
    assert "AssertionError" in log_f


def test_oracle_evaluator_shell(tmp_path: Path) -> None:
    res = ExecutionResult(
        harness="stub",
        benchmark="terminal-bench",
        task_id="tb-001",
        exit_code=0,
        duration_seconds=0.5,
    )
    passed, _msg = OracleEvaluator.evaluate_shell_verify(
        res,
        "echo 'success' > /dev/null",
        cwd=tmp_path,
    )
    assert passed is True


def test_ab_comparator() -> None:
    b_sum = MetricSummary(
        count=10,
        passed_count=8,
        failed_count=2,
        pass_rate=0.8,
        latency_p50=10.0,
        tokens_total=10000,
        tool_calls_total=20,
    )
    baseline = CellSummary(
        harness="claude-code",
        benchmark="coder_eval",
        plugins=[],
        mcp_servers=[],
        summary=b_sum,
    )

    t_sum = MetricSummary(
        count=10,
        passed_count=10,
        failed_count=0,
        pass_rate=1.0,
        latency_p50=7.0,
        tokens_total=6000,
        tool_calls_total=12,
    )
    treatment = CellSummary(
        harness="claude-code",
        benchmark="coder_eval",
        plugins=["caveman"],
        mcp_servers=["context7"],
        summary=t_sum,
    )

    diff = ABComparator.compare_cells(baseline, treatment)
    assert round(diff.delta_pass_rate, 2) == 20.0
    assert round(diff.delta_latency_pct, 2) == -30.0
    assert round(diff.delta_tokens_pct, 2) == -40.0
    assert "Strong Improvement" in diff.narrative_verdict

    md_table = ABComparator.render_ab_markdown_table([diff])
    assert "A/B Extension Evaluation Deltas" in md_table
    assert "+20.0%" in md_table


def test_scorecard_and_github_issue_publishing(tmp_path: Path) -> None:
    report = BenchmarkReport(
        run_id="hb-test-run-001",
        name="test-suite",
        config={"llm_model": "MiniMax-M3"},
        summaries=[
            CellSummary(
                harness="claude-code",
                benchmark="coder_eval",
                plugins=[],
                mcp_servers=[],
                summary=MetricSummary(
                    count=5,
                    passed_count=5,
                    pass_rate=1.0,
                    latency_p50=12.5,
                    tokens_input_total=50000,
                    tokens_output_total=1500,
                    tool_calls_total=8,
                ),
            )
        ],
        results=[
            ExecutionResult(
                harness="claude-code",
                benchmark="coder_eval",
                task_id="ce-py-001",
                exit_code=0,
                duration_seconds=12.5,
                tokens_input=10000,
                tokens_output=300,
                passed=True,
            )
        ],
    )

    leaderboard = ScorecardGenerator.render_markdown_leaderboard(report)
    assert "AI Coding Agent Benchmark Leaderboard" in leaderboard
    assert "claude-code" in leaderboard

    title, body, labels = GitHubIssuePublisher.build_issue_content(report, target_date="2026-08-22")
    assert "[Benchmark Report] 2026-08-22" in title
    assert "2026-08-22" in labels
    assert "MiniMax-M3" in body

    junit_file = tmp_path / "junit.xml"
    export_junit_xml(report.results, junit_file, suite_name=report.run_id)
    assert junit_file.exists()
    assert '<testcase name="ce-py-001"' in junit_file.read_text()
