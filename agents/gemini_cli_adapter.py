"""Adapter for the Google ``gemini-cli`` harness.

Gemini CLI discovers MCP servers from ``gemini-extension.json`` files located in
the workspace. The adapter synthesizes this extension file when MCP servers
are requested and invokes ``gemini run <prompt>``.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
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

        # Launch background translation bridge for custom endpoints
        import socket
        import subprocess

        s = socket.socket()
        s.bind(("", 0))
        port = s.getsockname()[1]
        s.close()

        bridge_script = _P(__file__).parent / "gemini_bridge.py"
        if bridge_script.exists():
            bridge_env = os.environ.copy()
            if api_base:
                bridge_env["LLM_API"] = api_base
            if api_key:
                bridge_env["LLM_KEY"] = api_key
            if model:
                bridge_env["LLM_MODEL"] = model

            proc = subprocess.Popen(
                [sys.executable, str(bridge_script), "--port", str(port)],
                env=bridge_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            ctx.child_pids.append(proc.pid)
            bridge_url = f"http://127.0.0.1:{port}"
            ctx.extra_env["GOOGLE_GEMINI_BASE_URL"] = bridge_url
            ctx.extra_env["GEMINI_API_BASE"] = bridge_url

        if api_key:
            ctx.extra_env["GEMINI_API_KEY"] = api_key
            ctx.extra_env["GOOGLE_API_KEY"] = api_key
        else:
            ctx.extra_env["GEMINI_API_KEY"] = "gemini-api-key"
            ctx.extra_env["GOOGLE_API_KEY"] = "gemini-api-key"

        if model:
            ctx.extra_env["GEMINI_MODEL"] = model
        ctx.extra_env["GEMINI_CLI_TRUST_WORKSPACE"] = "true"
        ctx.extra_env["CI"] = "1"
        ctx.extra_env["NO_COLOR"] = "1"

        # Materialize .gemini/settings.json
        gemini_dir = ctx.workspace_dir / ".gemini"
        gemini_dir.mkdir(parents=True, exist_ok=True)
        settings = {
            "baseUrl": bridge_url,
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
                "auth": {
                    "selectedType": "gemini-api-key",
                },
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
                    candidate = _P(__file__).resolve().parents[1] / "mcp" / "mcp_registry.json"
                    registry_path = str(candidate) if candidate.exists() else None
                if registry_path is None:
                    raise RuntimeError("MCP registry not found")
                registry = json.loads(_P(registry_path).read_text())
                spec = registry["servers"][name]
                ext["mcpServers"][name] = {
                    "command": spec["command"],
                    "args": spec.get("args", []),
                    "env": spec.get("env", {}),
                }
            (ctx.workspace_dir / "gemini-extension.json").write_text(json.dumps(ext, indent=2))

    def _build_command(self, prompt: str, workspace_dir) -> list[str]:
        return [self.cli_binary, "-p", prompt, "--output-format", "json"]

    @staticmethod
    def resolve_cli() -> str | None:
        return shutil.which("gemini")
