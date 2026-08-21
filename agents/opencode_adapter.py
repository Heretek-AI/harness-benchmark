"""Adapter for the ``opencode`` harness.

OpenCode reads its configuration from the file pointed to by ``OPENCODE_CONFIG``
or ``~/.config/opencode/config.json``. The adapter synthesizes an ``opencode.json``
file specifying LiteLLM provider details and registered MCP servers, then
invokes ``opencode --non-interactive <prompt>``.
"""

from __future__ import annotations

import json
import shutil

from agents.base import AdapterContext, BaseAgentAdapter


class OpenCodeAdapter(BaseAgentAdapter):
    """Harness adapter for OpenCode CLI."""

    name = "opencode"
    cli_binary = "opencode"

    def _on_setup(
        self,
        ctx: AdapterContext,
        plugins: list[str],
        mcp_servers: list[str],
    ) -> None:
        api_base, api_key, model = self.get_llm_config(ctx)
        target_model = model or "default"

        # Bridge environment variables
        if api_base:
            ctx.extra_env["OPENAI_API_BASE"] = api_base
            ctx.extra_env["OPENAI_BASE_URL"] = api_base
            ctx.extra_env["LITELLM_URL"] = api_base
        if api_key:
            ctx.extra_env["OPENAI_API_KEY"] = api_key
            ctx.extra_env["LITELLM_KEY"] = api_key

        cfg = {
            "$schema": "https://opencode.ai/config.json",
            "model": f"litellm/{target_model}",
            "provider": {
                "litellm": {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": "LiteLLM",
                    "options": {
                        "baseURL": api_base or "http://localhost:4000/v1",
                        "apiKey": api_key,
                    },
                    "models": {
                        target_model: {"name": target_model}
                    },
                }
            },
            "mcp_servers": list(mcp_servers),
        }
        cfg_path = ctx.workspace_dir / "opencode.json"
        cfg_path.write_text(json.dumps(cfg, indent=2))
        ctx.extra_env["OPENCODE_CONFIG"] = str(cfg_path)

    def _build_command(self, prompt: str, workspace_dir) -> list[str]:
        return [self.cli_binary, "run", "--auto", "--format", "json", prompt]

    @staticmethod
    def resolve_cli() -> str | None:
        return shutil.which("opencode")