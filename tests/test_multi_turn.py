"""Tests for multi-turn task spec and conversation replay."""

from __future__ import annotations

from pathlib import Path

from benchmarks.base import MultiTurnTask, TurnSpec
from agents.base import ConversationReplayAdapter, MultiTurnResult
from agents.stub_adapter import StubAdapter


def _make_task() -> MultiTurnTask:
    return MultiTurnTask(
        task_id="multi-1",
        name="Two-turn task",
        turns=[
            TurnSpec(role="user", content="Create hello.py"),
            TurnSpec(role="assistant", content=""),
            TurnSpec(role="user", content="Run it"),
            TurnSpec(role="assistant", content=""),
        ],
    )


def test_multi_turn_task_user_turns() -> None:
    task = _make_task()
    assert len(task.user_turns) == 2
    assert task.user_turns[0].content == "Create hello.py"


def test_multi_turn_task_assistant_turns() -> None:
    task = _make_task()
    assert len(task.assistant_turns) == 2


def test_multi_turn_task_to_yaml() -> None:
    task = _make_task()
    yaml_str = task.to_yaml()
    assert "task_id: multi-1" in yaml_str
    assert "Create hello.py" in yaml_str
    assert "role: user" in yaml_str
    assert "role: assistant" in yaml_str


def test_turn_spec_tool_calls() -> None:
    turn = TurnSpec(
        role="assistant",
        content="",
        tool_calls_expected=["bash", "write_file"],
    )
    assert turn.tool_calls_expected == ["bash", "write_file"]


def test_conversation_replay_basic() -> None:
    task = _make_task()
    adapter = StubAdapter()
    replay = ConversationReplayAdapter(adapter)
    result = replay.run(task, workspace_dir=Path("/tmp"))
    assert isinstance(result, MultiTurnResult)
    assert result.task_id == "multi-1"
    assert result.total_turns >= 1


def test_conversation_replay_score() -> None:
    task = _make_task()
    adapter = StubAdapter()
    replay = ConversationReplayAdapter(adapter)
    result = replay.run(task, workspace_dir=Path("/tmp"))
    assert 0.0 <= result.score <= 1.0


def test_multi_turn_result_properties() -> None:
    result = MultiTurnResult(
        task_id="test",
        harness="stub",
        turn_results=[],
        total_turns=0,
        all_turns_passed=True,
    )
    assert result.score == 0.0
    assert result.total_tokens == 0
