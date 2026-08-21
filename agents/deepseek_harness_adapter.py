"""Adapter for the ``deepseek-harness`` (and ``DeepSeek-Reasonix``) CLI.

SKELETON — both harnesses are LiteLLM-compatible and read ``OPENAI_API_KEY``
+ ``OPENAI_BASE`` from env. The CLI's real flag set lives in
``review/agents/deepseek-harness`` / ``review/agents/DeepSeek-Reasonix``.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from agents.base import AdapterContext, BaseAgentAdapter, ExecutionResult


class DeepSeekHarnessAdapter(BaseAgentAdapter):
    name = "deepseek-harness"
    cli_binary = "deepseek"

    def _on_setup(
        self,
        ctx: AdapterContext,
        plugins: list[str],
        mcp_servers: list[str],
    ) -> None:
        # DeepSeek harness reads OPENAI_BASE / OPENAI_API_KEY from env; the
        # runner maps LLM_API -> OPENAI_BASE and LLM_KEY -> OPENAI_API_KEY.
        ctx.extra_env.setdefault("OPENAI_BASE", "${LLM_API}")

    def _on_execute_task(
        self,
        prompt: str,
        workspace_dir: Path,
        timeout: int,
    ) -> ExecutionResult:
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [self.cli_binary, "--task", prompt],
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
        return shutil.which("deepseek")