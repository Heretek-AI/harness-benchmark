"""Regression tests for the agent_engine CLI entry point.

When ``scripts/install_harness.sh`` builds bash shims for harnesses whose
real CLI isn't on PATH, the shim invokes
``python3 ~/.local/bin/agent_engine.py "$@"``. That file is a copy of
``agents/agent_engine.py`` so it MUST be runnable as a subprocess and
emit the JSON envelope ``BaseAgentAdapter.extract_token_usage`` parses.

These tests assert both behaviors; they are the regression guard for
the CI scenario where every cell completes in ~70 ms with empty stdout
(the bug we shipped in the previous overhaul).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Invoke ``python3 agents/agent_engine.py`` with the given args + env."""
    full_env = os.environ.copy()
    # Remove any inherited creds so we exercise the fallback path
    # unless the caller explicitly asks for a remote call.
    for k in ("LLM_API", "LLM_KEY", "LLM_MODEL", "ANTIGRAVITY_API_BASE"):
        full_env.pop(k, None)
    if env:
        full_env.update({k: v for k, v in env.items() if v is not None})
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "agents" / "agent_engine.py"), *args],
        capture_output=True,
        text=True,
        env=full_env,
        check=False,
        timeout=30,
    )


def test_cli_emits_json_envelope_when_no_creds() -> None:
    """No LLM_API/LLM_KEY -> stub envelope with deterministic token counts."""
    proc = _run_cli("-p", "write fib", "--output-format", "json")
    assert proc.returncode == 0
    body = json.loads(proc.stdout)
    assert body["type"] == "result"
    assert body["subtype"] == "success"
    assert body["usage"]["input_tokens"] == 100
    assert body["usage"]["output_tokens"] == 20
    assert body["tool_calls"] == 0
    assert "result" in body


def test_cli_accepts_dangerously_skip_permissions_flag() -> None:
    """The bash shim passes --dangerously-skip-permissions; the CLI must not error."""
    proc = _run_cli(
        "-p",
        "echo hi",
        "--dangerously-skip-permissions",
        "--output-format",
        "json",
    )
    assert proc.returncode == 0
    body = json.loads(proc.stdout)
    assert body["type"] == "result"


def test_cli_errors_when_no_prompt() -> None:
    proc = _run_cli("--output-format", "json")
    assert proc.returncode != 0


def test_cli_text_output_is_human_readable() -> None:
    proc = _run_cli("-p", "echo hi", "--output-format", "text")
    assert proc.returncode == 0
    # text mode just prints the result string.
    assert "echo hi" in proc.stdout


def test_cli_envelope_round_trips_through_adapter_token_parser() -> None:
    """Run the CLI and feed the stdout through BaseAgentAdapter.extract_token_usage.

    Validates that the wire format produced by the CLI is what the base
    adapter expects.
    """
    from agents.stub_adapter import StubAdapter

    proc = _run_cli("-p", "test", "--output-format", "json")
    body = json.loads(proc.stdout)

    adapter = StubAdapter()
    tokens_in, tokens_out = adapter.extract_token_usage(json.dumps(body))
    assert tokens_in == body["usage"]["input_tokens"]
    assert tokens_out == body["usage"]["output_tokens"]
