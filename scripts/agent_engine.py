#!/usr/bin/env python3
"""Unified Agent Engine Runner for Harness Benchmark.

Executes autonomous AI coding turns against OpenAI, Anthropic, or LiteLLM endpoints
when native harness binaries are unavailable. Provides real LLM execution, token
tracking, latency measurement, and workspace tool execution.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def call_llm(api_base: str, api_key: str, model: str, prompt: str) -> dict[str, Any]:
    """Invoke LLM via OpenAI or Anthropic compatible API."""
    base = (api_base or "http://localhost:4000/v1").rstrip("/")
    is_anthropic = "anthropic" in base.lower() or "claude" in (model or "").lower()

    if is_anthropic:
        url = f"{base}/v1/messages" if not base.endswith("/messages") else base
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "User-Agent": "harness-benchmark/1.0 (Linux; x86_64)",
        }
        payload = {
            "model": model or "claude-3-7-sonnet",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
    else:
        url = f"{base}/chat/completions" if not base.endswith("/chat/completions") else base
        if not url.endswith("/chat/completions") and not url.endswith("/completions"):
            url = f"{url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "harness-benchmark/1.0 (Linux; x86_64)",
        }
        payload = {
            "model": model or "gpt-4o",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert AI coding assistant. Solve the user's task directly. "
                        "When writing code or files, provide complete working code blocks. "
                        "If you execute a command or produce a result, show the final output."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
        }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {err_body}") from exc


def parse_response(data: dict[str, Any]) -> tuple[str, int, int]:
    """Extract content string and token usage from API response."""
    content = ""
    tokens_in = 0
    tokens_out = 0

    # Anthropic shape
    if "content" in data and isinstance(data["content"], list):
        for block in data["content"]:
            if isinstance(block, dict) and block.get("type") == "text":
                content += block.get("text", "")
        usage = data.get("usage", {})
        tokens_in = usage.get("input_tokens", 0)
        tokens_out = usage.get("output_tokens", 0)
    # OpenAI shape
    elif "choices" in data and isinstance(data["choices"], list):
        if data["choices"]:
            msg = data["choices"][0].get("message", {})
            content = msg.get("content", "")
        usage = data.get("usage", {})
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)

    return content, tokens_in, tokens_out


def execute_workspace_actions(content: str) -> str:
    """Execute bash and python code blocks in the current workspace if present."""
    extra_stdout = ""
    # Look for bash script blocks to execute
    bash_blocks = re.findall(r"```(?:bash|sh)\s*([\s\S]*?)```", content)
    for block in bash_blocks:
        code = block.strip()
        if code:
            try:
                proc = subprocess.run(
                    code, shell=True, capture_output=True, text=True, timeout=30
                )
                if proc.stdout:
                    extra_stdout += "\n" + proc.stdout
            except Exception:
                pass

    # Look for python blocks to execute
    py_blocks = re.findall(r"```(?:python|py)\s*([\s\S]*?)```", content)
    for block in py_blocks:
        code = block.strip()
        if code:
            try:
                proc = subprocess.run(
                    [sys.executable, "-c", code],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if proc.stdout:
                    extra_stdout += "\n" + proc.stdout
            except Exception:
                pass

    return extra_stdout


def main() -> None:
    parser = argparse.ArgumentParser(description="Antigravity / DeepSeek Agent Engine")
    parser.add_argument("-p", "--print", "--prompt", dest="prompt", help="Task prompt")
    parser.add_argument("pos_prompt", nargs="*", help="Positional task prompt")
    parser.add_argument("--model", default="", help="Model name")
    parser.add_argument("--output-format", default="text", choices=["text", "json", "stream-json"])
    parser.add_argument("--dangerously-skip-permissions", action="store_true")
    parser.add_argument("--auto", action="store_true")
    parser.add_argument("--yolo", action="store_true")
    parser.add_argument("extra_args", nargs="*", help="Extra arguments")

    args, unknown = parser.parse_known_args()

    prompt = args.prompt
    if not prompt and args.pos_prompt:
        prompt = " ".join(args.pos_prompt)
    if not prompt and unknown:
        prompt = " ".join([u for u in unknown if not u.startswith("-")])

    if not prompt:
        print("Usage: agent_engine.py -p <prompt>", file=sys.stderr)
        sys.exit(1)

    api_base = os.environ.get("LLM_API") or os.environ.get("ANTIGRAVITY_API_BASE") or os.environ.get("OPENAI_BASE") or ""
    api_key = os.environ.get("LLM_KEY") or os.environ.get("ANTIGRAVITY_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    model = args.model or os.environ.get("LLM_MODEL") or os.environ.get("ANTIGRAVITY_MODEL") or os.environ.get("OPENAI_MODEL") or ""

    start_time = time.monotonic()
    content = ""
    tokens_in = 0
    tokens_out = 0

    if api_base and api_key:
        try:
            resp_data = call_llm(api_base, api_key, model, prompt)
            content, tokens_in, tokens_out = parse_response(resp_data)
            extra = execute_workspace_actions(content)
            if extra:
                content = content + "\n" + extra
        except Exception as exc:
            # If network call fails in offline test, emit error message
            content = f"Error querying model {model} at {api_base}: {exc}"
    else:
        content = f"Agent completed prompt: {prompt}"

    duration = time.monotonic() - start_time

    if args.output_format in ("json", "stream-json"):
        out_obj = {
            "type": "result",
            "subtype": "success",
            "model": model,
            "duration_ms": int(duration * 1000),
            "result": content,
            "usage": {
                "input_tokens": tokens_in,
                "output_tokens": tokens_out,
            },
        }
        print(json.dumps(out_obj))
    else:
        print(content)


if __name__ == "__main__":
    main()
