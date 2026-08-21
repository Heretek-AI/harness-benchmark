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
        config = {
            "api_base": "${LLM_API}",
            "model": "${LLM_MODEL}",
            "workspace": str(ctx.workspace_dir),
        }
        config_dir = ctx.workspace_dir / ".antigravity"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.json").write_text(json.dumps(config, indent=2))

    def _build_command(self, prompt: str, workspace_dir) -> list[str]:
        return [self.cli_binary, "run", prompt]

    @staticmethod
    def resolve_cli() -> str | None:
        return shutil.which("antigravity") or shutil.which("agy")