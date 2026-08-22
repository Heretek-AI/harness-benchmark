"""Tests for tool-use scoring."""

from __future__ import annotations

from evaluation.tool_scorer import ToolCall, ToolUseResult, ToolUseScorer


def test_perfect_score() -> None:
    scorer = ToolUseScorer()
    calls = [
        ToolCall(name="bash", args={"command": "ls"}),
        ToolCall(name="write_file", args={"path": "out.txt"}),
    ]
    result = scorer.score(
        calls,
        expected_tools=["bash", "write_file"],
        required_sequence=["bash", "write_file"],
    )
    assert result.score > 0.9
    assert result.passed
    assert result.sequence_correct
    assert result.tools_missed == []


def test_missing_tool() -> None:
    scorer = ToolUseScorer()
    calls = [ToolCall(name="bash")]
    result = scorer.score(calls, expected_tools=["bash", "write_file"])
    assert "write_file" in result.tools_missed
    assert result.score < 0.9


def test_extra_tools() -> None:
    scorer = ToolUseScorer()
    calls = [
        ToolCall(name="bash"),
        ToolCall(name="write_file"),
        ToolCall(name="network_request"),
    ]
    result = scorer.score(calls, expected_tools=["bash"])
    assert "write_file" in result.tools_extra
    assert "network_request" in result.tools_extra


def test_forbidden_tool_penalty() -> None:
    scorer = ToolUseScorer()
    calls = [ToolCall(name="bash"), ToolCall(name="network_request")]
    result = scorer.score(
        calls,
        expected_tools=["bash"],
        forbidden_tools=["network_request"],
    )
    # Forbidden tool used → coverage halved → score penalized
    assert result.score < 0.9


def test_sequence_incorrect() -> None:
    scorer = ToolUseScorer()
    calls = [
        ToolCall(name="write_file"),
        ToolCall(name="bash"),
    ]
    result = scorer.score(
        calls,
        expected_tools=["bash", "write_file"],
        required_sequence=["bash", "write_file"],
    )
    assert not result.sequence_correct
    assert result.score < 0.9


def test_empty_calls() -> None:
    scorer = ToolUseScorer()
    result = scorer.score([], expected_tools=["bash"])
    assert result.score < 0.7
    assert "bash" in result.tools_missed


def test_no_expectations() -> None:
    scorer = ToolUseScorer()
    calls = [ToolCall(name="bash")]
    result = scorer.score(calls)
    assert result.score > 0.5
    assert result.passed
