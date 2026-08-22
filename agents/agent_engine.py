"""Unified Multi-Turn Autonomous Agent Engine (importable module).

Executes real iterative ReAct coding agent loops against OpenAI,
Anthropic, or LiteLLM endpoints. Provides complete agent system prompts,
tool schemas (``execute_bash`` / ``write_file`` / ``read_file``),
multi-turn observation feedback, full token accumulation, tool
invocation tracking, and workspace action execution.

This module is the canonical import target used by the
``agent-engine`` adapter (``agents/agent_engine_adapter.py``) and by
the fallback transport on any adapter whose CLI is missing.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

AGENT_SYSTEM_PROMPT = """You are Antigravity, an autonomous AI software engineering agent.
Your objective is to solve the given coding, terminal, or benchmarking task precisely in the workspace.

You have access to the following workspace tools:

1. execute_bash(command: str)
Execute a shell command in the current working directory and inspect stdout/stderr.
Example:
```xml
<tool_call>
<name>execute_bash</name>
<args>{"command": "echo 'verified' > marker.txt"}</args>
</tool_call>
```

2. write_file(path: str, content: str)
Write or overwrite a file in the workspace.
Example:
```xml
<tool_call>
<name>write_file</name>
<args>{"path": "solution.py", "content": "def solution():\\n    return 42\\n"}</args>
</tool_call>
```

3. read_file(path: str)
Read the content of a file in the workspace.
Example:
```xml
<tool_call>
<name>read_file</name>
<args>{"path": "solution.py"}</args>
</tool_call>
```

Instructions:
- When given a task, reason step-by-step, invoke necessary tools to create or edit files and run verification.
- Always execute commands to create requested files or verify output.
- When done, provide your final response and output `<task_complete>`.
"""


def call_llm_turn(
    api_base: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
) -> tuple[str, int, int]:
    """Invoke one LLM conversation turn via Anthropic or OpenAI endpoint.

    Tries four candidate URL shapes (``/messages``, ``/v1/messages``,
    ``/chat/completions``, ``/v1/chat/completions``) and returns on the
    first 2xx response.
    """
    base = (api_base or "http://localhost:4000/v1").rstrip("/")
    target_model = model or "MiniMax-M3"

    headers_anthropic = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "Authorization": f"Bearer {api_key}",
        "anthropic-version": "2023-06-01",
        "User-Agent": "harness-benchmark/1.0 (Linux; x86_64)",
    }
    anthropic_msgs = [m for m in messages if m.get("role") != "system"]
    sys_content = "\n\n".join([m["content"] for m in messages if m.get("role") == "system"]) or AGENT_SYSTEM_PROMPT
    payload_anthropic = {
        "model": target_model,
        "max_tokens": 4096,
        "system": sys_content,
        "messages": anthropic_msgs if anthropic_msgs else [{"role": "user", "content": "Begin."}],
    }

    headers_openai = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "harness-benchmark/1.0 (Linux; x86_64)",
    }
    payload_openai = {
        "model": target_model,
        "messages": messages,
        "temperature": 0.0,
    }

    candidates = [
        (f"{base}/messages", headers_anthropic, payload_anthropic),
        (f"{base}/v1/messages", headers_anthropic, payload_anthropic),
        (f"{base}/chat/completions", headers_openai, payload_openai),
        (f"{base}/v1/chat/completions", headers_openai, payload_openai),
    ]

    last_error: Exception | None = None
    for url, headers, payload in candidates:
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = resp.read().decode("utf-8")
                if not body.strip():
                    continue
                data = json.loads(body)

                if "content" in data and isinstance(data["content"], list):
                    content = "".join(
                        [b.get("text", "") for b in data["content"] if isinstance(b, dict) and b.get("type") == "text"]
                    )
                    usage = data.get("usage", {})
                    return content, usage.get("input_tokens", 0), usage.get("output_tokens", 0)

                if "choices" in data and isinstance(data["choices"], list):
                    content = ""
                    if data["choices"]:
                        msg = data["choices"][0].get("message", {})
                        content = msg.get("content", "")
                    usage = data.get("usage", {})
                    return content, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)

        except Exception as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Failed to query LLM endpoint at {base}")


def execute_tool(name: str, args: dict[str, Any], workspace_dir: Path) -> str:
    """Execute a single tool call inside ``workspace_dir``."""
    name = name.strip().lower()
    if name in ("execute_bash", "bash", "shell", "run_command"):
        cmd = args.get("command") or args.get("cmd") or ""
        if not cmd:
            return "Error: no command provided"
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=str(workspace_dir),
                timeout=45,
            )
            out = proc.stdout
            if proc.stderr:
                out += f"\n[stderr]: {proc.stderr}"
            return out.strip() or f"Command executed with exit code {proc.returncode}"
        except subprocess.TimeoutExpired:
            return "Error: command timed out after 45s"
        except Exception as exc:
            return f"Error executing bash: {exc}"

    if name in ("write_file", "write", "create_file", "save_file"):
        path_str = args.get("path") or args.get("filePath") or args.get("file") or ""
        content = args.get("content") or args.get("code") or ""
        if not path_str:
            return "Error: no path provided"
        try:
            target = (workspace_dir / path_str).resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            return f"File {path_str} wrote successfully ({len(content)} bytes)."
        except Exception as exc:
            return f"Error writing file: {exc}"

    if name in ("read_file", "read", "view_file", "cat"):
        path_str = args.get("path") or args.get("filePath") or args.get("file") or ""
        if not path_str:
            return "Error: no path provided"
        try:
            target = (workspace_dir / path_str).resolve()
            if not target.exists():
                return f"Error: file {path_str} not found"
            return target.read_text()
        except Exception as exc:
            return f"Error reading file: {exc}"

    return f"Unknown tool: {name}"


def parse_tool_calls(text: str) -> list[tuple[str, dict[str, Any]]]:
    """Parse tool calls from XML tags or markdown code fences."""
    calls: list[tuple[str, dict[str, Any]]] = []

    xml_matches = re.findall(
        r"<tool_call>\s*<name>(.*?)</name>\s*<args>(.*?)</args>\s*</tool_call>",
        text,
        re.DOTALL,
    )
    for name, args_raw in xml_matches:
        try:
            args_obj = json.loads(args_raw.strip())
            calls.append((name.strip(), args_obj))
        except Exception:
            calls.append((name.strip(), {"command": args_raw.strip()}))

    if not calls:
        bash_blocks = re.findall(r"```(?:bash|sh)\s*([\s\S]*?)```", text)
        for block in bash_blocks:
            cmd = block.strip()
            if cmd:
                calls.append(("execute_bash", {"command": cmd}))

    return calls


def run_agent_loop(
    api_base: str,
    api_key: str,
    model: str,
    prompt: str,
    workspace_dir: Path,
    max_turns: int = 8,
) -> tuple[str, int, int, int]:
    """Run iterative ReAct agent loop.

    Returns ``(final_output, tokens_in, tokens_out, tool_calls_count)``.
    Loops until the model emits ``<task_complete>`` or ``max_turns`` is
    reached, whichever comes first.
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    total_tokens_in = 0
    total_tokens_out = 0
    total_tool_calls = 0
    final_output = ""

    for _turn in range(max_turns):
        turn_text, t_in, t_out = call_llm_turn(api_base, api_key, model, messages)
        total_tokens_in += t_in
        total_tokens_out += t_out
        final_output = turn_text

        tool_calls = parse_tool_calls(turn_text)
        if not tool_calls or "<task_complete>" in turn_text:
            break

        messages.append({"role": "assistant", "content": turn_text})
        observations: list[str] = []

        for name, args in tool_calls:
            total_tool_calls += 1
            obs = execute_tool(name, args, workspace_dir)
            observations.append(f"Observation for {name}:\n{obs}")

        obs_content = "\n\n".join(observations)
        messages.append(
            {
                "role": "user",
                "content": f"{obs_content}\n\nProceed to solve the task or output <task_complete>.",
            }
        )

    return final_output, total_tokens_in, total_tokens_out, total_tool_calls


def run_agent_loop_timed(
    api_base: str,
    api_key: str,
    model: str,
    prompt: str,
    workspace_dir: Path,
    max_turns: int = 8,
) -> dict[str, Any]:
    """Wrap :func:`run_agent_loop` with timing + structured dict return.

    Used by the ``AgentEngineAdapter`` so we don't reinvent timing
    bookkeeping inside the adapter class.
    """
    start = time.monotonic()
    final_output, tokens_in, tokens_out, tool_calls_count = run_agent_loop(
        api_base,
        api_key,
        model,
        prompt,
        workspace_dir,
        max_turns=max_turns,
    )
    return {
        "final_output": final_output,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tool_calls_count": tool_calls_count,
        "duration_seconds": time.monotonic() - start,
    }


__all__ = [
    "AGENT_SYSTEM_PROMPT",
    "call_llm_turn",
    "execute_tool",
    "parse_tool_calls",
    "run_agent_loop",
    "run_agent_loop_timed",
]
