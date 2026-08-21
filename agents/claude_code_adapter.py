"""Adapter for Anthropic's ``claude-code`` CLI.

Claude Code reads MCP servers from a JSON file passed via ``--mcp-config``
and discovers plugins from directories passed via ``--plugin-dir``. We
synthesize both files under the adapter's tmp workspace so every run is
hermetic. ``--verbose`` makes the CLI emit a JSONL stream containing usage
and tool_use events, which we parse in ``extract_token_usage`` and
``count_tool_calls`` (the default base implementations handle the wire
shape).
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agents.base import AdapterContext, BaseAgentAdapter, ExecutionResult

logger = logging.getLogger(__name__)


class _MCPConfig(BaseModel):
    """Minimal MCP config shape Claude Code accepts.

    See ``review/agents/claude-code/cli/`` for the full schema; we only set
    what the launcher needs: a top-level ``mcpServers`` dict whose values
    are stdio transports with ``command`` + ``args`` (+ optional ``env``).
    """

    mcpServers: dict[str, dict[str, Any]]


class ClaudeCodeAdapter(BaseAgentAdapter):
    name = "claude-code"
    cli_binary = "claude"

    # ---- subclass hooks ----

    def _on_setup(
        self,
        ctx: AdapterContext,
        plugins: list[str],
        mcp_servers: list[str],
    ) -> None:
        # Plugin dir: the loader has already materialized one (or more)
        # plugins into ctx.plugin_dir if the run requested any. Claude Code
        # accepts a single --plugin-dir per invocation, so we expect exactly
        # one staging root.
        if plugins and plugins != ["none"] and ctx.plugin_dir is None:
            raise ValueError(
                "plugin loader did not produce a plugin_dir for "
                f"plugins={plugins!r}"
            )

        # MCP config: synthesize the JSON Claude Code consumes.
        if mcp_servers and mcp_servers != ["none"]:
            cfg = _build_mcp_config(ctx, mcp_servers)
            ctx.mcp_config_path = ctx.workspace_dir.parent / "mcp-config.json"
            ctx.mcp_config_path.write_text(cfg.model_dump_json(indent=2))
            logger.debug(
                "wrote mcp-config to %s with servers %s",
                ctx.mcp_config_path,
                list(cfg.mcpServers),
            )

    def _on_execute_task(
        self,
        prompt: str,
        workspace_dir: Path,
        timeout: int,
    ) -> ExecutionResult:
        ctx = self.ctx
        cmd: list[str] = [self.cli_binary]

        if ctx.plugin_dir is not None:
            cmd += ["--plugin-dir", str(ctx.plugin_dir)]
        if ctx.mcp_config_path is not None:
            cmd += ["--mcp-config", str(ctx.mcp_config_path)]
        cmd += ["--verbose", "--print", "--output-format", "json"]

        # ``--`` separates the prompt positional from any earlier flags.
        cmd += ["--", prompt]

        env = self.full_env()
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(workspace_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - start
            return ExecutionResult(
                harness=self.name,
                benchmark="",
                task_id="",
                plugins=list(ctx.plugins),
                mcp_servers=list(ctx.mcp_servers),
                exit_code=-1,
                duration_seconds=duration,
                stdout=exc.stdout or "",
                stderr=(exc.stderr or "") + f"\n[timeout after {timeout}s]",
                error="timeout",
            )
        except FileNotFoundError as exc:
            duration = time.monotonic() - start
            return ExecutionResult(
                harness=self.name,
                benchmark="",
                task_id="",
                plugins=list(ctx.plugins),
                mcp_servers=list(ctx.mcp_servers),
                exit_code=-1,
                duration_seconds=duration,
                stdout="",
                stderr=str(exc),
                error="cli_not_found",
            )
        duration = time.monotonic() - start
        tokens_in, tokens_out = self.extract_token_usage(proc.stdout)
        tool_calls = self.count_tool_calls(proc.stdout)
        return ExecutionResult(
            harness=self.name,
            benchmark="",
            task_id="",
            plugins=list(ctx.plugins),
            mcp_servers=list(ctx.mcp_servers),
            exit_code=proc.returncode,
            duration_seconds=duration,
            stdout=proc.stdout,
            stderr=proc.stderr,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            tokens_total=(
                (tokens_in or 0) + (tokens_out or 0)
                if tokens_in is not None and tokens_out is not None
                else None
            ),
            tool_calls=tool_calls,
        )

    @staticmethod
    def resolve_cli() -> str | None:
        return shutil.which("claude")


# ---- helpers ----


def _build_mcp_config(ctx: AdapterContext, mcp_servers: list[str]) -> _MCPConfig:
    """Read each MCP server's launch spec from the registry passed via env.

    The runner sets ``HARNESS_BENCH_MCP_REGISTRY`` to the absolute path of
    the registry JSON so the adapter is hermetic (no path assumptions about
    cwd). Falls back to ``mcp/mcp_registry.json`` next to the repo root if
    the env var is unset.
    """
    import os
    from pathlib import Path as _P

    registry_path = os.environ.get("HARNESS_BENCH_MCP_REGISTRY")
    if registry_path is None:
        # repo_root / mcp / mcp_registry.json — best-effort fallback
        candidate = _P(__file__).resolve().parents[1] / "mcp" / "mcp_registry.json"
        if candidate.exists():
            registry_path = str(candidate)
    if registry_path is None:
        raise RuntimeError(
            "MCP registry not found; set HARNESS_BENCH_MCP_REGISTRY or "
            "create mcp/mcp_registry.json at repo root"
        )

    registry = json.loads(_P(registry_path).read_text())
    servers: dict[str, dict[str, Any]] = {}
    for name in mcp_servers:
        spec = registry["servers"].get(name)
        if spec is None:
            raise KeyError(f"MCP server {name!r} not in registry {registry_path}")
        env = {
            k: os.path.expandvars(v) if isinstance(v, str) else v
            for k, v in (spec.get("env") or {}).items()
        }
        servers[name] = {
            "command": spec["command"],
            "args": spec.get("args", []),
            "env": env,
            "transport": spec.get("transport", "stdio"),
        }
    return _MCPConfig(mcpServers=servers)