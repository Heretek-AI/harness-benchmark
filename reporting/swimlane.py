"""ASCII & Markdown Swimlane Visualization for Agent Tool & LSP Interactions."""

from __future__ import annotations

from core.types import ExecutionResult


class InteractionSwimlane:
    """Renders visual ASCII/Markdown swimlane diagrams of agent execution steps."""

    @staticmethod
    def render_execution_swimlane(result: ExecutionResult) -> str:
        """Render a turn-by-turn swimlane diagram for an execution result."""
        lines = [
            "```text",
            f"┌{'─' * 68}┐",
            f"│ EXECUTION SWIMLANE: {result.task_id:<46} │",
            f"├{'─' * 68}┤",
            "│ [0.00s] 👤 USER       ▶ Prompt Dispatched                                 │",
        ]

        t_offset = 0.5
        for idx, turn in enumerate(result.turns, 1):
            lines.append(
                f"│ [{t_offset:05.2f}s] 🤖 AGENT      ▶ Turn {idx}: LLM Reasoning ({turn.tokens_input}/{turn.tokens_output} toks)        │"
            )
            t_offset += 0.8
            for tool in turn.tool_calls:
                args_summary = ", ".join(f"{k}={v}" for k, v in tool.arguments.items())
                if len(args_summary) > 45:
                    args_summary = args_summary[:42] + "..."
                lines.append(
                    f"│ [{t_offset:05.2f}s] ⚙️  TOOL       ▶ {tool.name}({args_summary}) -> exit={tool.exit_code or 0:<2}   │"
                )
                t_offset += max(tool.duration_seconds, 0.2)

        for lsp_diag in result.lsp_diagnostics:
            diag_str = lsp_diag[:40]
            lines.append(f"│ [{t_offset:05.2f}s] 🔍 LSP/AST    ▶ Diagnostic: {diag_str:<37} │")
            t_offset += 0.1

        status_tag = "✅ ALL TESTS PASSED" if result.passed else f"❌ FAILED ({result.failure_category})"
        lines.append(f"│ [{result.duration_seconds:05.2f}s] ⚖️  ORACLE     ▶ {status_tag:<49} │")
        lines.append(f"└{'─' * 68}┘")
        lines.append("```")
        return "\n".join(lines)
