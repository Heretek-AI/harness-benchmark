"""First-class adapter that wraps :mod:`agents.agent_engine` as a harness.

Lets the matrix include the autonomous ReAct loop as a peer of
``claude-code``, ``gemini-cli``, etc. so you can compare its
performance head-to-head against external CLIs.

The same module also serves as the fallback transport: when
``HARNESS_BENCH_FALLBACK_ENGINE=1`` is set and an adapter's CLI is
missing, ``BaseAgentAdapter._execute_with_engine_fallback`` routes the
call through :func:`agents.agent_engine.run_agent_loop_timed`.
"""

from __future__ import annotations

import logging
import os
from collections import Counter
from pathlib import Path

from agents.agent_engine import run_agent_loop_timed
from agents.base import AdapterContext, BaseAgentAdapter, ExecutionResult

logger = logging.getLogger(__name__)


class AgentEngineAdapter(BaseAgentAdapter):
    """Harness adapter for the in-process ReAct agent loop."""

    name = "agent-engine"
    # The adapter never spawns an external CLI; the "binary" is the
    # Python module itself. ``resolve_cli`` returns a sentinel so the
    # base-class ``resolve_cli()`` contract is honored.
    cli_binary = "<inline>"

    # ---- subclass hooks ----

    def _on_setup(
        self,
        ctx: AdapterContext,
        plugins: list[str],
        mcp_servers: list[str],
    ) -> None:
        # Mirror the env-bridge pattern of the real-CLI adapters so the
        # autonomous engine sees a uniform ``LLM_*`` namespace.
        api_base, api_key, model = self.get_llm_config(ctx)
        if api_base:
            ctx.extra_env["LLM_API"] = api_base
            ctx.extra_env["ANTIGRAVITY_API_BASE"] = api_base
        if api_key:
            ctx.extra_env["LLM_KEY"] = api_key
            ctx.extra_env["ANTIGRAVITY_API_KEY"] = api_key
        if model:
            ctx.extra_env["LLM_MODEL"] = model
            ctx.extra_env["ANTIGRAVITY_MODEL"] = model
        # The agent engine doesn't read plugins/MCP from disk, but we
        # accept the parameters so the adapter signature matches the
        # base class. Future work may mount plugin instructions into
        # the system prompt; for now they are tracked in the result.
        ctx.extra_env.setdefault("AGENT_ENGINE_PLUGINS", ",".join(plugins) if plugins else "none")
        ctx.extra_env.setdefault("AGENT_ENGINE_MCP", ",".join(mcp_servers) if mcp_servers else "none")

    def _build_command(
        self,
        prompt: str,
        workspace_dir: Path,
    ) -> list[str]:
        # Not invoked through the standard CLI path; the adapter's
        # _on_execute_task below short-circuits to run_agent_loop_timed.
        return [self.cli_binary, prompt]

    def _on_execute_task(
        self,
        prompt: str,
        workspace_dir: Path,
        timeout: int,
    ) -> ExecutionResult:
        ctx = self._ctx
        api_base, api_key, model = self.get_llm_config(ctx) if ctx else self.get_llm_config(None)
        # Always run the loop with max_turns=8 (matches the original
        # agent_engine.py default); the ``timeout`` parameter applies
        # to the outer subprocess path and is informational here.
        _ = timeout  # silence linters
        try:
            outcome = run_agent_loop_timed(
                api_base=api_base,
                api_key=api_key,
                model=model,
                prompt=prompt,
                workspace_dir=workspace_dir,
            )
        except Exception as exc:
            logger.warning("agent-engine run failed: %s", exc)
            return ExecutionResult(
                harness=self.name,
                benchmark="",
                task_id="",
                exit_code=-1,
                duration_seconds=0.0,
                stdout="",
                stderr=str(exc),
                error=type(exc).__name__,
            )

        # Parse tool-call names out of the final output for telemetry.
        tool_counts: Counter[str] = Counter()
        for block in (
            "<execute_bash>",
            "<write_file>",
            "<read_file>",
        ):
            if block in outcome["final_output"]:
                tool_counts[block.strip("<>")] = outcome["final_output"].count(block)
        tokens_in = outcome["tokens_in"]
        tokens_out = outcome["tokens_out"]
        return ExecutionResult(
            harness=self.name,
            benchmark="",
            task_id="",
            exit_code=0,
            duration_seconds=outcome["duration_seconds"],
            stdout=outcome["final_output"],
            stderr="",
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            tokens_total=(tokens_in or 0) + (tokens_out or 0),
            tool_calls=dict(tool_counts),
            turns_count=1,
        )

    @staticmethod
    def resolve_cli() -> str | None:
        # Always available; there's no external binary to locate.
        return "<inline>"

    # ---- public helpers (used by the fallback transport) ----

    @staticmethod
    def fallback_run(
        prompt: str,
        workspace_dir: Path,
        api_base: str,
        api_key: str,
        model: str,
        timeout: int = 600,
    ) -> ExecutionResult:
        """Run the loop and return an ``ExecutionResult``.

        Used by :meth:`BaseAgentAdapter._execute_with_engine_fallback`
        when the adapter's own CLI is missing and the fallback env var
        is set.
        """
        _ = timeout  # timeout applies to the CLI subprocess path
        try:
            outcome = run_agent_loop_timed(
                api_base=api_base,
                api_key=api_key,
                model=model,
                prompt=prompt,
                workspace_dir=workspace_dir,
            )
        except Exception as exc:
            return ExecutionResult(
                harness="agent-engine-fallback",
                benchmark="",
                task_id="",
                exit_code=-1,
                duration_seconds=0.0,
                stdout="",
                stderr=str(exc),
                error=type(exc).__name__,
            )
        tool_counts: Counter[str] = Counter()
        for block in ("<execute_bash>", "<write_file>", "<read_file>"):
            if block in outcome["final_output"]:
                tool_counts[block.strip("<>")] = outcome["final_output"].count(block)
        tokens_in = outcome["tokens_in"]
        tokens_out = outcome["tokens_out"]
        return ExecutionResult(
            harness="agent-engine-fallback",
            benchmark="",
            task_id="",
            exit_code=0,
            duration_seconds=outcome["duration_seconds"],
            stdout=outcome["final_output"],
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            tokens_total=(tokens_in or 0) + (tokens_out or 0),
            tool_calls=dict(tool_counts),
        )


def fallback_env_enabled() -> bool:
    """True when the ``HARNESS_BENCH_FALLBACK_ENGINE`` env var is on.

    The expected value is ``"1"``; anything truthy works. When this
    returns ``False`` (the default), adapters hard-fail on
    ``FileNotFoundError`` like before.
    """
    return os.environ.get("HARNESS_BENCH_FALLBACK_ENGINE", "").lower() in ("1", "true", "yes", "on")
