"""Stub harness used only by the test suite.

Returns canned ``ExecutionResult``s without spawning a subprocess so the
runner and metrics pipeline can be verified end-to-end on a developer
laptop with no API keys.
"""

from __future__ import annotations

from pathlib import Path

from agents.base import AdapterContext, BaseAgentAdapter, ExecutionResult


class StubAdapter(BaseAgentAdapter):
    name = "stub"
    cli_binary = "/bin/echo"  # not actually invoked

    def _on_setup(
        self,
        ctx: AdapterContext,
        plugins: list[str],
        mcp_servers: list[str],
    ) -> None:
        # No filesystem layout to materialize.
        return

    def _on_execute_task(
        self,
        prompt: str,
        workspace_dir: Path,
        timeout: int,
    ) -> ExecutionResult:
        # Pretend we used a handful of tokens and one tool call so the
        # metrics pipeline has realistic numbers to summarise. We always
        # emit "5" so the coder_eval smoke task's stdout_contains grader
        # accepts our output without needing a real model.
        return ExecutionResult(
            harness=self.name,
            benchmark="",
            task_id="",
            plugins=[],
            mcp_servers=[],
            exit_code=0,
            duration_seconds=0.05,
            stdout=f"stub-ran: {prompt[:40]}\n5\n",
            stderr="",
            tokens_input=128,
            tokens_output=64,
            tokens_total=192,
            tool_calls={"Read": 1, "Edit": 1},
        )