"""Base interface every harness adapter must implement.

The runner calls ``setup -> execute_task -> teardown`` once per (harness x
benchmark task x plugin set x mcp set) combination. Adapters are responsible
for translating the harness-agnostic inputs (env vars, plugin names, MCP
server names) into whatever config file or CLI flag the underlying CLI
expects, and for translating the CLI's output into an ``ExecutionResult``.

Adapters must emit an ``ExecutionResult`` even on non-zero exit so the
runner can record partial / failed runs.
"""

from __future__ import annotations

import abc
import logging
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ExecutionResult(BaseModel):
    """Captured outcome of a single harness invocation.

    The runner serializes this directly into the per-task JSON artifact, so
    every field must be JSON-serializable and stable across schema versions.
    """

    harness: str
    benchmark: str
    task_id: str
    plugins: list[str] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list)
    exit_code: int
    duration_seconds: float
    stdout: str = ""
    stderr: str = ""
    passed: bool | None = None  # None = no grader attached
    tokens_input: int | None = None
    tokens_output: int | None = None
    tokens_total: int | None = None
    cost_usd: float | None = None
    tool_calls: dict[str, int] = Field(default_factory=dict)
    error: str | None = None


@dataclass
class AdapterContext:
    """Per-run scratch state passed to every adapter method."""

    workspace_dir: Path
    plugin_dir: Path | None = None  # synthesized plugin root, if any
    mcp_config_path: Path | None = None  # synthesized mcp-config file, if any
    extra_env: dict[str, str] = field(default_factory=dict)
    child_pids: list[int] = field(default_factory=list)


class BaseAgentAdapter(abc.ABC):
    """Abstract base for harness adapters.

    Subclasses set ``name`` (the registry key, e.g. ``claude-code``) and
    ``cli_binary`` (the on-PATH executable). The base class owns the temp
    workspace lifecycle; subclasses implement the three hook methods.
    """

    name: str = ""
    cli_binary: str = ""

    def __init__(self) -> None:
        self._ctx: AdapterContext | None = None
        self._tmp_root: Path | None = None

    # ---- public lifecycle ----

    def setup(
        self,
        env_vars: dict[str, str],
        plugins: list[str],
        mcp_servers: list[str],
    ) -> AdapterContext:
        """Prepare a fresh workspace + child-process tracking.

        ``env_vars`` must always include ``LLM_API``, ``LLM_KEY``,
        ``LLM_MODEL`` (the runner copies these from the controlling shell).
        ``plugins`` and ``mcp_servers`` are catalog names; the runner
        resolves them via ``PluginLoader``/``MCPLauncher`` and passes the
        synthesized directories back through ``ctx.plugin_dir`` /
        ``ctx.mcp_config_path``.
        """
        self._tmp_root = Path(tempfile.mkdtemp(prefix=f"hb-{self.name}-"))
        workspace = self._tmp_root / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)

        self._ctx = AdapterContext(workspace_dir=workspace)
        self._ctx.extra_env.update(env_vars)

        try:
            self._on_setup(self._ctx, plugins, mcp_servers)
        except Exception:
            self.teardown()
            raise
        return self._ctx

    def execute_task(
        self,
        prompt: str,
        workspace_dir: str | Path,
        timeout: int,
    ) -> ExecutionResult:
        """Run the harness against ``prompt`` inside ``workspace_dir``."""
        if self._ctx is None:
            raise RuntimeError("setup() must be called before execute_task()")
        return self._on_execute_task(prompt, Path(workspace_dir), timeout)

    def teardown(self) -> None:
        """Kill child processes and remove the temp workspace."""
        ctx = self._ctx
        if ctx is not None:
            for pid in ctx.child_pids:
                try:
                    os.kill(pid, 9)
                except ProcessLookupError:
                    pass
                except OSError as exc:  # pragma: no cover - defensive
                    logger.warning("failed to kill pid %s: %s", pid, exc)
        if self._tmp_root is not None and self._tmp_root.exists():
            shutil.rmtree(self._tmp_root, ignore_errors=True)
        self._ctx = None
        self._tmp_root = None

    # ---- subclass hooks ----

    @abc.abstractmethod
    def _on_setup(
        self,
        ctx: AdapterContext,
        plugins: list[str],
        mcp_servers: list[str],
    ) -> None:
        """Materialize harness-specific config (files, plugin mounts, mcp-config)."""

    def _build_command(
        self,
        prompt: str,
        workspace_dir: Path,
    ) -> list[str]:
        """Return the argv for the harness subprocess.

        Default: ``[cli_binary, prompt]``. Override per harness to insert
        flags like ``run``, ``--task``, ``--non-interactive``, ``--plugin-dir``,
        ``--mcp-config``, ``--verbose``, etc.
        """
        return [self.cli_binary, prompt]

    def _on_execute_task(
        self,
        prompt: str,
        workspace_dir: Path,
        timeout: int,
    ) -> ExecutionResult:
        """Spawn the harness subprocess and capture its output.

        Default impl runs ``self._build_command(prompt, workspace_dir)``
        through ``self._run_cli``, which handles timing, error capture,
        and ``ExecutionResult`` construction. Override only when you need
        non-default behaviour (e.g., Claude Code parses ``--verbose`` JSONL
        after the subprocess completes).
        """
        return self._run_cli(
            self._build_command(prompt, workspace_dir), workspace_dir, timeout
        )

    def _run_cli(
        self,
        cmd: list[str],
        workspace_dir: Path,
        timeout: int,
    ) -> ExecutionResult:
        """Spawn ``cmd`` and translate its outcome into an ``ExecutionResult``.

        Always returns a result, even on ``FileNotFoundError`` (CLI missing
        on PATH) or ``TimeoutExpired`` — the runner records these as failed
        rather than crashing the whole sweep.
        """
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
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
            exit_code=proc.returncode,
            duration_seconds=time.monotonic() - start,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    # ---- helpers for subclasses ----

    @property
    def ctx(self) -> AdapterContext:
        if self._ctx is None:
            raise RuntimeError("adapter not initialised; call setup() first")
        return self._ctx

    def full_env(self) -> dict[str, str]:
        """Return process env merged with adapter extras (extras win)."""
        return {**os.environ, **self.ctx.extra_env}

    @staticmethod
    def resolve_cli() -> str | None:
        """Return the on-PATH path of this adapter's CLI binary, or None."""
        raise NotImplementedError

    # ---- parsing hooks (default impls, subclasses override) ----

    def extract_token_usage(self, stdout: str) -> tuple[int | None, int | None]:
        """Parse harness stdout for token counts.

        Default impl scans for the JSONL ``{"type":"usage",...}`` line shape
        Claude Code emits under ``--verbose``; other harnesses override.
        """
        import json

        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "usage":
                inp = obj.get("input_tokens")
                out = obj.get("output_tokens")
                if isinstance(inp, int) and isinstance(out, int):
                    return inp, out
        return None, None

    def count_tool_calls(self, stdout: str) -> dict[str, int]:
        """Count tool invocations by name from the harness's verbose log."""
        import json
        from collections import Counter

        counts: Counter[str] = Counter()
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "tool_use" and isinstance(obj.get("name"), str):
                counts[obj["name"]] += 1
        return dict(counts)

    @staticmethod
    def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float | None:
        """Return USD cost for a run, or None if the model isn't priced."""
        from metrics.cost_table import cost_for

        return cost_for(model, tokens_in, tokens_out)