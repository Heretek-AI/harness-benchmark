"""Adapter for the ``antigravity-cli`` harness.

SKELETON — the CLI's real flag set lives in ``review/agents/antigravity-cli``
and should be filled in once we wire that harness for real. For now this
adapter writes a stub config file so the runner exercises the full
setup/execute/teardown path.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

from agents.base import AdapterContext, BaseAgentAdapter, ExecutionResult


class AntigravityAdapter(BaseAgentAdapter):
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
        return shutil.which("antigravity")