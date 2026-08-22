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

    @staticmethod
    def render_divergence_diagram(result_a: ExecutionResult, result_b: ExecutionResult) -> str:
        """Render a side-by-side divergence diagram for two execution results.

        Highlights the steps where the two harnesses diverged:
        - tool-call name disagreements
        - missing tools in one trajectory
        - pass/fail divergence
        - token-cost divergence

        Falls back gracefully when one trajectory is empty.
        """
        lines = ["```text"]
        lines.append("┌─────────────────────────────────────────┬─────────────────────────────────────────┐")
        lines.append(f"│ RUN A: {result_a.harness:<33}│ RUN B: {result_b.harness:<33}│")
        lines.append(f"│ task_id: {result_a.task_id:<30}│ task_id: {result_b.task_id:<30}│")
        lines.append("├─────────────────────────────────────────┼─────────────────────────────────────────┤")

        def _turns(result: ExecutionResult) -> list[tuple[str, str]]:
            """Flatten turns into (label, content) pairs."""
            flat: list[tuple[str, str]] = []
            for idx, turn in enumerate(result.turns, 1):
                flat.append((f"turn {idx}", f"LLM {turn.tokens_input}/{turn.tokens_output}"))
                for tool in turn.tool_calls:
                    flat.append((f"tool {tool.name}", f"exit={tool.exit_code or 0}"))
            if not flat:
                # Fall back to stdout tool-call counting when turns
                # are unavailable.
                for name, count in result.tool_calls.items():
                    flat.append((f"tool {name}", f"count={count}"))
                if not flat:
                    flat.append(("<empty>", ""))
            return flat

        a_flat = _turns(result_a)
        b_flat = _turns(result_b)
        max_len = max(len(a_flat), len(b_flat))
        for i in range(max_len):
            a_label, a_body = a_flat[i] if i < len(a_flat) else ("", "")
            b_label, b_body = b_flat[i] if i < len(b_flat) else ("", "")
            a_line = f"{a_label:<13} {a_body:<26}"
            b_line = f"{b_label:<13} {b_body:<26}"
            div = ""
            if (i < len(a_flat)) != (i < len(b_flat)):
                div = "  ← missing step"
            elif a_label != b_label:
                div = f"  ← DIV: {a_label!r} vs {b_label!r}"
            lines.append(f"│ {a_line[:39]:<39} │ {b_line[:39]:<39} │{div}")

        # Token-cost divergence row.
        a_tok = result_a.tokens_total or 0
        b_tok = result_b.tokens_total or 0
        cost_div = ""
        if a_tok != b_tok:
            delta = b_tok - a_tok
            cost_div = f"  ← DIV: Δ {(delta):+d} tokens"
        lines.append("├─────────────────────────────────────────┼─────────────────────────────────────────┤")
        lines.append(f"│ tokens: {a_tok:<30}│ tokens: {b_tok:<30}│{cost_div}")

        # Pass/fail divergence.
        a_pass = "✅ PASS" if result_a.passed else f"❌ FAIL ({result_a.failure_category})"
        b_pass = "✅ PASS" if result_b.passed else f"❌ FAIL ({result_b.failure_category})"
        pass_div = "  ← DIV: outcomes disagree" if result_a.passed != result_b.passed else ""
        lines.append(f"│ outcome: {a_pass:<29}│ outcome: {b_pass:<29}│{pass_div}")
        lines.append("└─────────────────────────────────────────┴─────────────────────────────────────────┘")
        lines.append("```")
        return "\n".join(lines)
