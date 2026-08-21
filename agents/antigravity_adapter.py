"""Adapter for the Google Antigravity CLI (``antigravity-cli``) harness.

Translates benchmark tasks and configuration into Antigravity workspace
settings (``.antigravity/config.json``) and drives the ``antigravity run``
command lifecycle.
"""

from __future__ import annotations

import json
import shutil

from agents.base import AdapterContext, BaseAgentAdapter


class AntigravityAdapter(BaseAgentAdapter):
    """Harness adapter for Antigravity CLI."""

    name = "antigravity-cli"
    cli_binary = "antigravity"

    def _on_setup(
        self,
        ctx: AdapterContext,
        plugins: list[str],
        mcp_servers: list[str],
    ) -> None:
        api_base, api_key, model = self.get_llm_config(ctx)

        # Bridge environment variables
        if api_base:
            ctx.extra_env["ANTIGRAVITY_API_BASE"] = api_base
            ctx.extra_env["LLM_API"] = api_base
        if api_key:
            ctx.extra_env["ANTIGRAVITY_API_KEY"] = api_key
            ctx.extra_env["LLM_KEY"] = api_key
        if model:
            ctx.extra_env["ANTIGRAVITY_MODEL"] = model
            ctx.extra_env["LLM_MODEL"] = model

        config = {
            "api_base": api_base,
            "api_key": api_key,
            "model": model,
            "workspace": str(ctx.workspace_dir),
        }
        config_dir = ctx.workspace_dir / ".antigravity"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.json").write_text(json.dumps(config, indent=2))

    def _build_command(self, prompt: str, workspace_dir) -> list[str]:
        return [
            self.cli_binary,
            "-p",
            prompt,
            "--dangerously-skip-permissions",
            "--output-format",
            "json",
        ]

    @staticmethod
    def resolve_cli() -> str | None:
        return shutil.which("agy") or shutil.which("antigravity")