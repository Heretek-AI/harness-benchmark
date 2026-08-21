"""Adapter for the Google ``gemini-cli`` harness.

Gemini CLI discovers MCP servers from ``gemini-extension.json`` files located in
the workspace. The adapter synthesizes this extension file when MCP servers
are requested and invokes ``gemini run <prompt>``.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path as _P

from agents.base import AdapterContext, BaseAgentAdapter


class GeminiCLIAdapter(BaseAgentAdapter):
    """Harness adapter for Google Gemini CLI."""

    name = "gemini-cli"
    cli_binary = "gemini"

    def _on_setup(
        self,
        ctx: AdapterContext,
        plugins: list[str],
        mcp_servers: list[str],
    ) -> None:
        api_base, api_key, model = self.get_llm_config(ctx)

        # Bridge environment variables
        if api_key:
            ctx.extra_env["GEMINI_API_KEY"] = api_key
            ctx.extra_env["GOOGLE_API_KEY"] = api_key
        if api_base:
            ctx.extra_env["GEMINI_API_BASE"] = api_base
            ctx.extra_env["GOOGLE_GENAI_BASE_URL"] = api_base
            ctx.extra_env["GOOGLE_GEMINI_BASE_URL"] = api_base
        if model:
            ctx.extra_env["GEMINI_MODEL"] = model
        ctx.extra_env["GEMINI_CLI_TRUST_WORKSPACE"] = "true"

        # Materialize .gemini/settings.json
        gemini_dir = ctx.workspace_dir / ".gemini"
        gemini_dir.mkdir(parents=True, exist_ok=True)
        settings = {
            "model": {
                "name": model or "gemini-2.5-pro",
            },
            "general": {
                "defaultApprovalMode": "auto_edit",
            },
            "output": {
                "format": "json",
            },
            "security": {
                "folderTrust": {
                    "enabled": False,
                },
            },
        }
        (gemini_dir / "settings.json").write_text(json.dumps(settings, indent=2))

        # MCP extensions
        if mcp_servers and mcp_servers != ["none"]:
            ext: dict = {"name": "harness-bench", "mcpServers": {}}
            for name in mcp_servers:
                registry_path = os.environ.get("HARNESS_BENCH_MCP_REGISTRY")
                if registry_path is None:
                    candidate = (
                        _P(__file__).resolve().parents[1]
                        / "mcp"
                        / "mcp_registry.json"
                    )
                    registry_path = (
                        str(candidate) if candidate.exists() else None
                    )
                if registry_path is None:
                    raise RuntimeError("MCP registry not found")
                registry = json.loads(_P(registry_path).read_text())
                spec = registry["servers"][name]
                ext["mcpServers"][name] = {
                    "command": spec["command"],
                    "args": spec.get("args", []),
                    "env": spec.get("env", {}),
                }
            (ctx.workspace_dir / "gemini-extension.json").write_text(
                json.dumps(ext, indent=2)
            )

    def _build_command(self, prompt: str, workspace_dir) -> list[str]:
        return [self.cli_binary, "-p", prompt, "--yolo", "--output-format", "json"]

    @staticmethod
    def resolve_cli() -> str | None:
        return shutil.which("gemini")