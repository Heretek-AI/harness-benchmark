"""Adapter for the ``gemini-cli`` harness.

SKELETON — Gemini reads MCP servers from ``gemini-extension.json`` files in
the workspace. See ``review/agents/gemini-cli/gemini-extension.json`` for
the real schema; we write a minimal one when MCPs are requested.
Subprocess spawning + ExecutionResult construction are inherited from
``BaseAgentAdapter``; we only override ``_on_setup`` (extension-file
materialisation) and ``_build_command`` (the ``gemini run <prompt>`` argv
shape).
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path as _P

from agents.base import AdapterContext, BaseAgentAdapter


class GeminiCLIAdapter(BaseAgentAdapter):
    name = "gemini-cli"
    cli_binary = "gemini"

    def _on_setup(
        self,
        ctx: AdapterContext,
        plugins: list[str],
        mcp_servers: list[str],
    ) -> None:
        if mcp_servers and mcp_servers != ["none"]:
            ext: dict = {"name": "harness-bench", "mcpServers": {}}
            for name in mcp_servers:
                # The runner passes the registry path via env; we read it
                # here to mirror Claude Code's approach.
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
        return [self.cli_binary, "run", prompt]

    @staticmethod
    def resolve_cli() -> str | None:
        return shutil.which("gemini")