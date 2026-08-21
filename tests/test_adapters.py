"""Tests for all agent adapters and resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents import (
    ADAPTERS,
    AntigravityAdapter,
    DeepSeekHarnessAdapter,
    DeepSeekReasonixAdapter,
    GeminiCLIAdapter,
    OpenCodeAdapter,
    resolve,
)


def test_resolve_adapters() -> None:
    for name in [
        "claude-code",
        "antigravity-cli",
        "deepseek-harness",
        "DeepSeek-Reasonix",
        "gemini-cli",
        "opencode",
        "stub",
    ]:
        adapter = resolve(name)
        assert adapter.name == name

    with pytest.raises(KeyError):
        resolve("unknown-agent")


def test_antigravity_adapter_setup(tmp_path: Path) -> None:
    adapter = AntigravityAdapter()
    ctx = adapter.setup(
        env_vars={"LLM_API": "https://api.example.com", "LLM_MODEL": "test-model"},
        plugins=["caveman"],
        mcp_servers=["context7"],
    )
    try:
        config_path = ctx.workspace_dir / ".antigravity" / "config.json"
        assert config_path.exists()
        cfg = json.loads(config_path.read_text())
        assert cfg["api_base"] == "${LLM_API}"
    finally:
        adapter.teardown()


def test_gemini_adapter_setup_with_mcp(tmp_path: Path, mcp_registry_path: Path) -> None:
    adapter = GeminiCLIAdapter()
    ctx = adapter.setup(
        env_vars={"HARNESS_BENCH_MCP_REGISTRY": str(mcp_registry_path)},
        plugins=[],
        mcp_servers=["repomix"],
    )
    try:
        ext_path = ctx.workspace_dir / "gemini-extension.json"
        assert ext_path.exists()
        ext = json.loads(ext_path.read_text())
        assert "repomix" in ext["mcpServers"]
    finally:
        adapter.teardown()


def test_opencode_adapter_setup(tmp_path: Path) -> None:
    adapter = OpenCodeAdapter()
    ctx = adapter.setup(
        env_vars={"LLM_API": "https://api.example.com"},
        plugins=[],
        mcp_servers=["repomix"],
    )
    try:
        cfg_path = ctx.workspace_dir / "opencode.json"
        assert cfg_path.exists()
        cfg = json.loads(cfg_path.read_text())
        assert cfg["provider"]["name"] == "litellm"
        assert "repomix" in cfg["mcp_servers"]
        assert ctx.extra_env["OPENCODE_CONFIG"] == str(cfg_path)
    finally:
        adapter.teardown()


def test_deepseek_reasonix_adapter_setup(tmp_path: Path) -> None:
    adapter = DeepSeekReasonixAdapter()
    assert adapter.name == "DeepSeek-Reasonix"
    ctx = adapter.setup(env_vars={}, plugins=[], mcp_servers=[])
    try:
        assert ctx.extra_env["OPENAI_BASE"] == "${LLM_API}"
    finally:
        adapter.teardown()
