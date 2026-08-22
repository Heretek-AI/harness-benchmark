"""Unit tests for the Interaction Swimlane diagram renderer."""

from __future__ import annotations

from core.types import AgentTurn, ExecutionResult, ToolCall
from reporting.swimlane import InteractionSwimlane


def test_interaction_swimlane_rendering() -> None:
    res = ExecutionResult(
        harness="claude-code",
        benchmark="terminal-bench",
        task_id="tb-sh-002",
        exit_code=0,
        duration_seconds=3.4,
        passed=True,
        turns=[
            AgentTurn(
                turn_index=1,
                role="assistant",
                tokens_input=1200,
                tokens_output=150,
                tool_calls=[
                    ToolCall(
                        name="bash", arguments={"command": "mkdir -p src/utils"}, duration_seconds=0.3, exit_code=0
                    )
                ],
            )
        ],
        lsp_diagnostics=["Syntax verified cleanly"],
    )

    diagram = InteractionSwimlane.render_execution_swimlane(res)
    assert "EXECUTION SWIMLANE: tb-sh-002" in diagram
    assert "bash" in diagram
    assert "mkdir -p src/utils" in diagram
    assert "ALL TESTS PASSED" in diagram
