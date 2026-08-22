"""Execution tracer capturing turn-by-turn agent trajectories."""

from __future__ import annotations

from core.types import ExecutionResult


class ExecutionTracer:
    """Utilities for formatting and tracing agent execution trajectories."""

    @staticmethod
    def format_trajectory_markdown(result: ExecutionResult) -> str:
        """Render a readable markdown summary of an agent's execution trajectory."""
        lines = [
            f"### Task Execution: `{result.task_id}`",
            f"- **Harness**: `{result.harness}`",
            f"- **Status**: {'✅ PASSED' if result.passed else '❌ FAILED'}",
            f"- **Duration**: `{result.duration_seconds:.2f}s`",
            f"- **Tokens**: `{result.tokens_input or 0}` In / `{result.tokens_output or 0}` Out",
            f"- **Tool Calls Total**: `{sum(result.tool_calls.values())}`",
        ]

        if result.oracle_log:
            lines.extend(
                [
                    "",
                    "#### Oracle Evaluation Log",
                    f"```text\n{result.oracle_log}\n```",
                ]
            )

        if result.stderr and result.exit_code != 0:
            lines.extend(
                [
                    "",
                    "#### Standard Error",
                    f"```text\n{result.stderr}\n```",
                ]
            )

        return "\n".join(lines)
