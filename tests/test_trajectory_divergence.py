"""Tests for the trajectory divergence diagram."""

from __future__ import annotations

from agents.base import ExecutionResult
from core.types import AgentTurn, ToolCall
from reporting.swimlane import InteractionSwimlane


def _r(
    harness: str,
    tool_calls: list[tuple[str, int]],
    passed: bool = True,
    tokens_total: int = 1000,
    failure_category: str = "none",
) -> ExecutionResult:
    turns = [
        AgentTurn(
            turn_index=1,
            role="assistant",
            content="",
            tool_calls=[ToolCall(name=name, exit_code=exit_code) for name, exit_code in tool_calls],
            tokens_input=500,
            tokens_output=200,
        )
    ]
    tool_counts: dict[str, int] = {}
    for name, _ in tool_calls:
        tool_counts[name] = tool_counts.get(name, 0) + 1
    return ExecutionResult(
        harness=harness,
        benchmark="coder_eval",
        task_id="t-1",
        exit_code=0,
        duration_seconds=2.5,
        passed=passed,
        tokens_total=tokens_total,
        tool_calls=tool_counts,
        turns=turns,
        failure_category=failure_category,
    )


def test_divergence_diagram_no_divergence_for_identical_runs() -> None:
    a = _r("claude-code", [("write_file", 0), ("read_file", 0)])
    b = _r("claude-code", [("write_file", 0), ("read_file", 0)])
    diagram = InteractionSwimlane.render_divergence_diagram(a, b)
    assert "DIV" not in diagram
    assert "missing step" not in diagram


def test_divergence_diagram_marks_tool_choice_difference() -> None:
    a = _r("claude-code", [("write_file", 0)])
    b = _r("gemini-cli", [("execute_bash", 0)])
    diagram = InteractionSwimlane.render_divergence_diagram(a, b)
    assert "DIV" in diagram
    assert "write_file" in diagram
    assert "execute_bash" in diagram


def test_divergence_diagram_marks_outcome_difference() -> None:
    a = _r("claude-code", [("write_file", 0)], passed=True)
    b = _r("claude-code", [("write_file", 0)], passed=False, failure_category="assertion_failure")
    diagram = InteractionSwimlane.render_divergence_diagram(a, b)
    assert "outcomes disagree" in diagram


def test_divergence_diagram_handles_empty_trajectory() -> None:
    a = ExecutionResult(
        harness="h1",
        benchmark="b",
        task_id="t",
        exit_code=0,
        duration_seconds=1.0,
    )
    b = _r("h2", [("write_file", 0)])
    diagram = InteractionSwimlane.render_divergence_diagram(a, b)
    # No crash; empty side renders <empty>.
    assert "<empty>" in diagram


def test_divergence_diagram_marks_token_delta() -> None:
    a = _r("h1", [("read", 0)], tokens_total=500)
    b = _r("h2", [("read", 0)], tokens_total=800)
    diagram = InteractionSwimlane.render_divergence_diagram(a, b)
    assert "Δ" in diagram
    assert "tokens" in diagram


def test_divergence_diagram_returns_string() -> None:
    a = _r("h1", [("read", 0)])
    b = _r("h2", [("read", 0)])
    out = InteractionSwimlane.render_divergence_diagram(a, b)
    assert isinstance(out, str)
    assert out.startswith("```text")
    assert out.endswith("```")
