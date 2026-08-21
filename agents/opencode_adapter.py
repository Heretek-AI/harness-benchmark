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
        cfg = {
            "provider": {
                "name": "litellm",
                "api_base": "${LLM_API}",
                "api_key": "${LLM_KEY}",
                "model": "${LLM_MODEL}",
            },
            "mcp_servers": list(mcp_servers),
        }
        cfg_path = ctx.workspace_dir / "opencode.json"
        cfg_path.write_text(json.dumps(cfg, indent=2))
        ctx.extra_env["OPENCODE_CONFIG"] = str(cfg_path)

    def _build_command(self, prompt: str, workspace_dir) -> list[str]:
        return [self.cli_binary, "--non-interactive", prompt]

    @staticmethod
    def resolve_cli() -> str | None:
        return shutil.which("opencode")