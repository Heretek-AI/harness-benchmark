"""Adapter for the ``opencode`` harness.

SKELETON — OpenCode reads its config from ``~/.config/opencode/config.json``
or the path in ``OPENCODE_CONFIG``. See ``review/agents/opencode/`` for the
real schema.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from agents.base import AdapterContext, BaseAgentAdapter, ExecutionResult


class OpenCodeAdapter(BaseAgentAdapter):
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

    def _on_execute_task(
        self,
        prompt: str,
        workspace_dir: Path,
        timeout: int,
    ) -> ExecutionResult:
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [self.cli_binary, "--non-interactive", prompt],
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
        return shutil.which("opencode")