"""Adapter for the ``deepseek-harness`` and ``DeepSeek-Reasonix`` CLI.

Both harnesses support OpenAI-compatible and LiteLLM endpoints, routing
``LLM_API`` to ``OPENAI_BASE`` and ``LLM_KEY`` to ``OPENAI_API_KEY``.
Subprocess invocation executes ``deepseek --task <prompt>``.
"""

from __future__ import annotations

import shutil

from agents.base import AdapterContext, BaseAgentAdapter


class DeepSeekHarnessAdapter(BaseAgentAdapter):
    """Harness adapter for DeepSeek CLI harness."""

    name = "deepseek-harness"
    cli_binary = "deepseek"

    def _on_setup(
        self,
        ctx: AdapterContext,
        plugins: list[str],
        mcp_servers: list[str],
    ) -> None:
        # DeepSeek harness reads OPENAI_BASE / OPENAI_API_KEY from env; the
        # runner maps LLM_API -> OPENAI_BASE and LLM_KEY -> OPENAI_API_KEY.
        ctx.extra_env.setdefault("OPENAI_BASE", "${LLM_API}")

    def _build_command(self, prompt: str, workspace_dir) -> list[str]:
        return [self.cli_binary, "--task", prompt]

    @staticmethod
    def resolve_cli() -> str | None:
        return shutil.which("deepseek")


class DeepSeekReasonixAdapter(DeepSeekHarnessAdapter):
    """Specialized adapter for DeepSeek-Reasonix harness variant."""

    name = "DeepSeek-Reasonix"
    cli_binary = "deepseek"