"""Tests for ClaudeCodeAdapter."""

from __future__ import annotations

import json
from pathlib import Path

from agents.claude_code_adapter import ClaudeCodeAdapter


def test_claude_code_token_extraction() -> None:
    adapter = ClaudeCodeAdapter()
    sample_stdout = (
        '{"type": "message_start", "message": {"id": "msg_1"}}\n'
        '{"type": "usage", "input_tokens": 150, "output_tokens": 42}\n'
        '{"type": "message_stop"}\n'
    )
    inp, out = adapter.extract_token_usage(sample_stdout)
    assert inp == 150
    assert out == 42


def test_claude_code_tool_call_counting() -> None:
    adapter = ClaudeCodeAdapter()
    sample_stdout = (
        '{"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}\n'
        '{"type": "tool_use", "name": "FileEdit", "input": {"path": "a.py"}}\n'
        '{"type": "tool_use", "name": "Bash", "input": {"command": "pwd"}}\n'
    )
    tools = adapter.count_tool_calls(sample_stdout)
    assert tools == {"Bash": 2, "FileEdit": 1}


def test_claude_code_mcp_config_synthesis(tmp_path: Path, mcp_registry_path: Path) -> None:
    adapter = ClaudeCodeAdapter()
    ctx = adapter.setup(
        env_vars={"HARNESS_BENCH_MCP_REGISTRY": str(mcp_registry_path)},
        plugins=[],
        mcp_servers=["chrome-devtools-mcp", "context7"],
    )
    try:
        assert ctx.mcp_config_path is not None
        assert ctx.mcp_config_path.exists()
        config_data = json.loads(ctx.mcp_config_path.read_text())
        assert "mcpServers" in config_data
        assert "chrome-devtools-mcp" in config_data["mcpServers"]
        assert "context7" in config_data["mcpServers"]
        assert config_data["mcpServers"]["chrome-devtools-mcp"]["command"] == "npx"
    finally:
        adapter.teardown()


def test_claude_code_missing_cli_error(tmp_path: Path) -> None:
    adapter = ClaudeCodeAdapter()
    adapter.cli_binary = "nonexistent-claude-binary-xyz"
    adapter.setup(env_vars={}, plugins=[], mcp_servers=[])
    try:
        result = adapter.execute_task("hello", tmp_path, timeout=5)
        assert result.exit_code == -1
        assert result.error == "cli_not_found"
    finally:
        adapter.teardown()
