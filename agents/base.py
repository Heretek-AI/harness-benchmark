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

from core.types import ExecutionResult

logger = logging.getLogger(__name__)


@dataclass
class AdapterContext:
    """Per-run scratch state passed to every adapter method."""

    workspace_dir: Path
    plugin_dir: Path | None = None  # synthesized plugin root, if any
    mcp_config_path: Path | None = None  # synthesized mcp-config file, if any
    plugins: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)
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

        self._ctx = AdapterContext(
            workspace_dir=workspace,
            plugins=list(plugins),
            mcp_servers=list(mcp_servers),
        )
        self._ctx.extra_env.update(env_vars)

        try:
            self._on_setup(self._ctx, plugins, mcp_servers)
        except Exception:
            self.teardown()
            raise
        return self._ctx

    def setup_env(self, env_vars: dict[str, str]) -> None:
        """Merge environment variables into adapter context."""
        if self._ctx:
            self._ctx.extra_env.update(env_vars)

    def attach_lsp(self, workspace_dir: Path) -> list[str]:
        """Run AST / LSP diagnostics on the workspace and return any syntax/type errors."""
        from core.lsp import LSPDiagnosticsEngine

        return LSPDiagnosticsEngine.check_workspace(workspace_dir)

    def get_llm_config(self, ctx: AdapterContext | None = None) -> tuple[str, str, str]:
        """Resolve (api_base, api_key, model) from adapter context or ambient environment."""
        target_ctx = ctx or self._ctx
        env = target_ctx.extra_env if target_ctx else {}
        api_base = env.get("LLM_API") or os.environ.get("LLM_API", "")
        api_key = env.get("LLM_KEY") or os.environ.get("LLM_KEY", "")
        model = env.get("LLM_MODEL") or os.environ.get("LLM_MODEL", "")
        return api_base, api_key, model

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
        return self._execute_with_engine_fallback(prompt, workspace_dir, timeout)

    def _should_fallback_to_engine(self) -> bool:
        """True when this adapter's CLI is missing AND fallback is enabled.

        The fallback transport is opt-in via ``HARNESS_BENCH_FALLBACK_ENGINE=1``
        so existing behaviour (hard-fail on missing CLI) is preserved by
        default. Adapters that are themselves always-available
        (``agent-engine``, ``stub``) never return True.
        """
        from agents.agent_engine_adapter import fallback_env_enabled

        if self.name in ("agent-engine", "stub"):
            return False
        if not fallback_env_enabled():
            return False
        try:
            cli = self.resolve_cli()
        except Exception:
            cli = None
        return cli is None

    def _execute_with_engine_fallback(
        self,
        prompt: str,
        workspace_dir: Path,
        timeout: int,
    ) -> ExecutionResult:
        """Run via the CLI; if the CLI is missing and fallback is enabled,
        delegate to ``agents.agent_engine`` instead of failing.
        """
        if self._should_fallback_to_engine():
            from agents.agent_engine_adapter import AgentEngineAdapter

            api_base, api_key, model = self.get_llm_config()
            logger.info("%s: CLI not on PATH; falling back to agent-engine", self.name)
            return AgentEngineAdapter.fallback_run(
                prompt=prompt,
                workspace_dir=workspace_dir,
                api_base=api_base,
                api_key=api_key,
                model=model,
                timeout=timeout,
            )
        return self._run_cli(self._build_command(prompt, workspace_dir), workspace_dir, timeout)

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
        plugins = list(self.ctx.plugins) if self._ctx else []
        mcp_servers = list(self.ctx.mcp_servers) if self._ctx else []
        wrapped_cmd = self._wrap_with_bwrap(cmd, workspace_dir)
        try:
            proc = subprocess.run(
                wrapped_cmd,
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
                plugins=plugins,
                mcp_servers=mcp_servers,
                exit_code=-1,
                duration_seconds=time.monotonic() - start,
                stdout="",
                stderr=str(exc),
                error=type(exc).__name__,
            )
        self._materialize_tool_artifacts(proc.stdout, self.ctx.workspace_dir)
        tokens_in, tokens_out = self.extract_token_usage(proc.stdout)
        tool_calls = self.count_tool_calls(proc.stdout)
        return ExecutionResult(
            harness=self.name,
            benchmark="",
            task_id="",
            plugins=plugins,
            mcp_servers=mcp_servers,
            exit_code=proc.returncode,
            duration_seconds=time.monotonic() - start,
            stdout=proc.stdout,
            stderr=proc.stderr,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            tokens_total=(
                (tokens_in or 0) + (tokens_out or 0) if tokens_in is not None and tokens_out is not None else None
            ),
            tool_calls=tool_calls,
        )

    def _wrap_with_bwrap(
        self,
        cmd: list[str],
        workspace_dir: Path,
    ) -> list[str]:
        """Optionally wrap ``cmd`` in a bubblewrap sandbox.

        Opt-in via ``HARNESS_BENCH_USE_BWRAP=1``; defaults to returning
        ``cmd`` unchanged so existing behaviour is preserved. When the
        toggle is on but ``bwrap`` is missing on PATH we log a debug
        message and pass through.

        Environment toggles:
            ``HARNESS_BENCH_USE_BWRAP=1``       — enable sandbox
            ``HARNESS_BENCH_NETWORK_ISOLATION=1`` — add ``--unshare-net``
        """
        if not os.environ.get("HARNESS_BENCH_USE_BWRAP"):
            return cmd
        bwrap = shutil.which("bwrap")
        if bwrap is None:
            logger.debug("bwrap not on PATH; running %s without sandbox", cmd[0] if cmd else "<empty>")
            return cmd
        flags = [
            bwrap,
            "--ro-bind",
            "/",
            "/",
            "--bind",
            str(workspace_dir),
            str(workspace_dir),
            "--tmpfs",
            "/tmp",
            "--dev",
            "/dev",
            "--proc",
            "/proc",
            "--unshare-pid",
            "--die-with-parent",
        ]
        if os.environ.get("HARNESS_BENCH_NETWORK_ISOLATION"):
            flags.append("--unshare-net")
        return [*flags, "--", *cmd]

    def _materialize_tool_artifacts(self, stdout: str, workspace_dir: Path) -> None:
        """Execute filesystem and shell actions emitted in structured tags if any."""
        import json
        import re
        import subprocess

        # 1. <write_file><file_path>...</file_path><content>...</content></write_file>
        for block in re.finditer(
            r"<(?:write_file|file_write)>\s*<(?:file_path|path)>(.*?)</(?:file_path|path)>\s*<content>([\s\S]*?)</content>\s*</(?:write_file|file_write)>",
            stdout,
            re.IGNORECASE,
        ):
            rel_path = block.group(1).strip()
            content = block.group(2)
            if rel_path.startswith("/tmp/") and "workspace" in rel_path:
                rel_path = rel_path.split("workspace/")[-1]
            elif rel_path.startswith("/"):
                rel_path = rel_path.lstrip("/")
            target = workspace_dir / rel_path
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            except Exception:
                pass

        # 2. <tool_call>{"name": "run_shell_command", "arguments": {"command": "..."}}</tool_call>
        for block in re.finditer(r"<tool_call>\s*(\{[\s\S]*?\})\s*</tool_call>", stdout, re.IGNORECASE):
            try:
                data = json.loads(block.group(1))
                name = data.get("name")
                args = data.get("arguments", {})
                if name in ("run_shell_command", "bash", "execute_bash") and isinstance(args, dict):
                    cmd = args.get("command") or args.get("cmd")
                    if cmd and isinstance(cmd, str):
                        subprocess.run(cmd, shell=True, cwd=workspace_dir, timeout=10, capture_output=True)
            except Exception:
                pass

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

    def _iter_json_objects(self, stdout: str):
        """Yield parsed JSON objects from JSON array or JSONL lines."""
        import json

        text = stdout.strip()
        if not text:
            return

        if text.startswith("[") and text.endswith("]"):
            try:
                arr = json.loads(text)
                if isinstance(arr, list):
                    for item in arr:
                        if isinstance(item, dict):
                            yield item
                    return
            except json.JSONDecodeError:
                pass

        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    yield obj
                elif isinstance(obj, list):
                    for item in obj:
                        if isinstance(item, dict):
                            yield item
            except json.JSONDecodeError:
                continue

    def extract_token_usage(self, stdout: str) -> tuple[int | None, int | None]:
        """Parse harness stdout for token counts."""
        total_inp: int | None = None
        total_out: int | None = None

        for obj in self._iter_json_objects(stdout):
            # Check type == "result" with usage dict (Claude Code / Agent Engine JSON output)
            if obj.get("type") == "result" and isinstance(obj.get("usage"), dict):
                u = obj["usage"]
                inp = u.get("input_tokens")
                out = u.get("output_tokens")
                if isinstance(inp, int):
                    total_inp = inp
                if isinstance(out, int):
                    total_out = out

            # OpenCode step_finish: {"type": "step_finish", "part": {"tokens": {"input": 8377, "output": 76}}}
            part = obj.get("part") if isinstance(obj.get("part"), dict) else None
            if part and isinstance(part.get("tokens"), dict):
                toks = part["tokens"]
                inp = toks.get("input") or toks.get("input_tokens")
                out = toks.get("output") or toks.get("output_tokens")
                if isinstance(inp, int):
                    total_inp = max(total_inp or 0, inp)
                if isinstance(out, int):
                    total_out = max(total_out or 0, out)

            # Check type == "usage"
            elif obj.get("type") == "usage":
                inp = obj.get("input_tokens")
                out = obj.get("output_tokens")
                if isinstance(inp, int):
                    total_inp = (total_inp or 0) + inp
                if isinstance(out, int):
                    total_out = (total_out or 0) + out

            # Generic token usage dicts
            elif isinstance(obj.get("token_usage"), dict):
                u = obj["token_usage"]
                inp = u.get("input") or u.get("prompt_tokens")
                out = u.get("output") or u.get("completion_tokens")
                if isinstance(inp, int):
                    total_inp = inp
                if isinstance(out, int):
                    total_out = out

            # Gemini CLI stats.models.<model>.tokens
            if isinstance(obj.get("stats"), dict):
                models = obj["stats"].get("models", {})
                if isinstance(models, dict):
                    for m_info in models.values():
                        if isinstance(m_info, dict) and isinstance(m_info.get("tokens"), dict):
                            toks = m_info["tokens"]
                            inp = toks.get("input") or toks.get("prompt")
                            out = toks.get("candidates") or toks.get("output")
                            if isinstance(inp, int):
                                total_inp = (total_inp or 0) + inp
                            if isinstance(out, int):
                                total_out = (total_out or 0) + out

        return total_inp, total_out

    def count_tool_calls(self, stdout: str) -> dict[str, int]:
        """Count tool invocations by name from the harness's verbose log."""
        from collections import Counter

        counts: Counter[str] = Counter()
        for obj in self._iter_json_objects(stdout):
            # Direct tool_use event
            if obj.get("type") == "tool_use":
                if isinstance(obj.get("name"), str):
                    counts[obj["name"]] += 1
                part = obj.get("part") if isinstance(obj.get("part"), dict) else None
                if part:
                    tool_name = part.get("tool") or part.get("name")
                    if isinstance(tool_name, str):
                        counts[tool_name] += 1
            # Nested message content tool_use (Claude Code)
            elif obj.get("type") == "assistant" and isinstance(obj.get("message"), dict):
                content = obj["message"].get("content")
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "tool_use":
                            name = item.get("name")
                            if isinstance(name, str):
                                counts[name] += 1
            # Function/tool calls list
            elif isinstance(obj.get("tool_calls"), list):
                for item in obj["tool_calls"]:
                    if isinstance(item, dict) and isinstance(item.get("name"), str):
                        counts[item["name"]] += 1
            # Gemini CLI stats.tools.byName
            elif isinstance(obj.get("stats"), dict):
                tools_info = obj["stats"].get("tools", {})
                if isinstance(tools_info, dict):
                    by_name = tools_info.get("byName", {})
                    if isinstance(by_name, dict):
                        for name, count in by_name.items():
                            if isinstance(count, int):
                                counts[str(name)] += count

        # Count XML-style tool calls in raw stdout (e.g. from Gemini, Reasonix, Antigravity)
        import re

        xml_tool_patterns = [
            (r"<write_file\b|<file_write\b", "write_file"),
            (r"<read_file\b|<file_read\b", "read_file"),
            (r"<execute_bash\b|<bash\b|<shell_command\b", "execute_bash"),
            (r"<str_replace_editor\b|<edit_file\b", "str_replace_editor"),
        ]
        for pattern, tool_name in xml_tool_patterns:
            matches = len(re.findall(pattern, stdout, re.IGNORECASE))
            if matches > 0 and tool_name not in counts:
                counts[tool_name] += matches

        # Named <tool_call>{"name": "xyz"}
        for match in re.finditer(r'<tool_call>\s*\{\s*"name"\s*:\s*"([^"]+)"', stdout):
            t_name = match.group(1)
            counts[t_name] += 1

        return dict(counts)

    @staticmethod
    def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float | None:
        """Return USD cost for a run, or None if the model isn't priced."""
        from metrics.cost_table import cost_for

        return cost_for(model, tokens_in, tokens_out)


# ── Multi-turn conversation replay adapter ─────────────────────────────


class ConversationReplayAdapter:
    """Drive a multi-turn conversation through a BaseAgentAdapter.

    Takes a MultiTurnTask and replays it turn-by-turn through any
    harness adapter. Collects per-turn results including tool calls,
    token usage, and latency.

    Usage::

        from benchmarks.base import MultiTurnTask, TurnSpec
        from agents.base import ConversationReplayAdapter, StubAdapter

        task = MultiTurnTask(
            task_id="demo",
            name="Demo",
            turns=[
                TurnSpec(role="user", content="Create a file called hello.py"),
                TurnSpec(role="assistant", content=""),  # agent generates
                TurnSpec(role="user", content="Now run it"),
                TurnSpec(role="assistant", content=""),
            ],
        )

        adapter = StubAdapter()
        replay = ConversationReplayAdapter(adapter)
        result = replay.run(task, workspace_dir=Path("/tmp/demo"))
    """

    def __init__(self, adapter: BaseAgentAdapter) -> None:
        self.adapter = adapter

    def run(
        self,
        task: MultiTurnTask,
        workspace_dir: Path,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> MultiTurnResult:
        """Replay a multi-turn task through the adapter.

        Each user turn is sent to the adapter. The adapter's response
        becomes context for the next user turn. Tool calls and token
        usage are collected per turn.
        """
        import time

        conversation_history: list[dict[str, str]] = []
        turn_results: list[TurnResult] = []
        total_tokens_in = 0
        total_tokens_out = 0
        total_cost = 0.0

        max_turns = min(task.max_turns, len(task.turns))
        effective_timeout = timeout or task.timeout_seconds

        for i, turn in enumerate(task.turns[:max_turns]):
            if turn.role == "user":
                conversation_history.append({"role": "user", "content": turn.content})
                continue

            # Assistant turn — send accumulated conversation to adapter
            prompt = self._build_prompt(conversation_history)

            t0 = time.monotonic()
            try:
                result = self.adapter.run(
                    prompt=prompt,
                    workspace_dir=workspace_dir,
                    env=env,
                    timeout=effective_timeout,
                )
                latency = time.monotonic() - t0
            except Exception as exc:
                latency = time.monotonic() - t0
                result = ExecutionResult(
                    task_id=task.task_id,
                    harness=self.adapter.name,
                    benchmark="multi_turn",
                    prompt=prompt,
                    stdout="",
                    stderr=str(exc),
                    exit_code=1,
                    duration_seconds=latency,
                )

            # Extract metrics
            tokens_in, tokens_out = self.adapter.extract_token_usage(result.stdout)
            tool_calls = self.adapter.count_tool_calls(result.stdout)

            if tokens_in:
                total_tokens_in += tokens_in
            if tokens_out:
                total_tokens_out += tokens_out

            cost = self.adapter.estimate_cost(
                self.adapter.name,
                tokens_in or 0,
                tokens_out or 0,
            )
            if cost:
                total_cost += cost

            # Build turn result
            turn_result = TurnResult(
                turn_index=i,
                role="assistant",
                content=result.stdout,
                tool_calls=tool_calls,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_seconds=latency,
                exit_code=result.exit_code,
            )
            turn_results.append(turn_result)

            # Add to conversation history
            conversation_history.append({"role": "assistant", "content": result.stdout})

        # Overall result
        all_passed = all(tr.exit_code == 0 for tr in turn_results) if turn_results else False
        total_latency = sum(tr.latency_seconds for tr in turn_results)

        return MultiTurnResult(
            task_id=task.task_id,
            harness=self.adapter.name,
            turn_results=turn_results,
            total_turns=len(turn_results),
            all_turns_passed=all_passed,
            total_tokens_in=total_tokens_in,
            total_tokens_out=total_tokens_out,
            total_cost_usd=total_cost,
            total_latency_seconds=total_latency,
        )

    def _build_prompt(self, history: list[dict[str, str]]) -> str:
        """Build a single prompt from conversation history."""
        parts = []
        for msg in history:
            role = msg["role"].upper()
            parts.append(f"[{role}]\n{msg['content']}")
        return "\n\n".join(parts)


@dataclass
class TurnResult:
    """Result of a single turn in a multi-turn conversation."""

    turn_index: int
    role: str
    content: str
    tool_calls: dict[str, int] = field(default_factory=dict)
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_seconds: float = 0.0
    exit_code: int = 0


@dataclass
class MultiTurnResult:
    """Aggregated result of a multi-turn conversation replay."""

    task_id: str
    harness: str
    turn_results: list[TurnResult]
    total_turns: int
    all_turns_passed: bool
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_cost_usd: float = 0.0
    total_latency_seconds: float = 0.0

    @property
    def score(self) -> float:
        """Simple score: fraction of turns that succeeded."""
        if not self.turn_results:
            return 0.0
        return sum(1 for t in self.turn_results if t.exit_code == 0) / len(self.turn_results)

    @property
    def total_tokens(self) -> int:
        return self.total_tokens_in + self.total_tokens_out
