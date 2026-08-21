"""Adapter for the ``gemini-cli`` harness.

SKELETON — Gemini reads MCP servers from ``gemini-extension.json`` files in
the workspace. See ``review/agents/gemini-cli/gemini-extension.json`` for
the real schema; we write a minimal one when MCPs are requested.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from agents.base import AdapterContext, BaseAgentAdapter, ExecutionResult


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
            ext: dict[str, Any] = {"name": "harness-bench", "mcpServers": {}}
            for name in mcp_servers:
                # The runner passes the registry path via env; we read it
                # here to mirror Claude Code's approach.
                import os
                from pathlib import Path as _P

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

    def _on_execute_task(
        self,
        prompt: str,
        workspace_dir: Path,
        timeout: int,
    ) -> ExecutionResult:
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [self.cli_binary, "run", prompt],
                cwd=str(workspace_dir),
                env=self.full_env(),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return ExecutionResult(
                harness=self.name,
                benchmark="",
                task_id="",
                plugins=[],
                mcp_servers=[],
                exit_code=-1,
                duration_seconds=time.monotonic() - start,
                stdout="",
                stderr=str(exc),
                error=type(exc).__name__,
            )
        return ExecutionResult(
            harness=self.name,
            benchmark="",
            task_id="",
            plugins=[],
            mcp_servers=[],
            exit_code=proc.returncode,
            duration_seconds=time.monotonic() - start,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    @staticmethod
    def resolve_cli() -> str | None:
        return shutil.which("gemini")