"""Adapter for the ``deepseek-harness`` (and ``DeepSeek-Reasonix``) CLI.

SKELETON — both harnesses are LiteLLM-compatible and read ``OPENAI_API_KEY``
+ ``OPENAI_BASE`` from env. The CLI's real flag set lives in
``review/agents/deepseek-harness`` / ``review/agents/DeepSeek-Reasonix``.
Subprocess spawning + ExecutionResult construction are inherited from
``BaseAgentAdapter``; we only override ``_on_setup`` (env-var mapping) and
``_build_command`` (the ``deepseek --task <prompt>`` argv shape).
"""

from __future__ import annotations

import shutil

from agents.base import AdapterContext, BaseAgentAdapter


class DeepSeekHarnessAdapter(BaseAgentAdapter):
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