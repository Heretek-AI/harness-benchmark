"""Tests for all agent adapters, endpoint configurations, and resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents import (
    ADAPTERS,
    AntigravityAdapter,
    ClaudeCodeAdapter,
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


def test_claude_code_adapter_setup(tmp_path: Path) -> None:
    adapter = ClaudeCodeAdapter()
    ctx = adapter.setup(
        env_vars={
            "LLM_API": "https://api.openai.proxy/v1",
            "LLM_KEY": "sk-test-key",
            "LLM_MODEL": "claude-3-7-sonnet",
        },
        plugins=[],
        mcp_servers=[],
    )
    try:
        settings_path = ctx.workspace_dir / ".claude" / "settings.json"
        assert settings_path.exists()
        settings = json.loads(settings_path.read_text())
        assert settings["env"]["ANTHROPIC_BASE_URL"] == "https://api.openai.proxy/v1"
        assert settings["env"]["ANTHROPIC_API_KEY"] == "sk-test-key"
        assert settings["env"]["ANTHROPIC_MODEL"] == "claude-3-7-sonnet"
        assert settings["model"] == "claude-3-7-sonnet"
        assert ctx.extra_env["ANTHROPIC_BASE_URL"] == "https://api.openai.proxy/v1"
        assert ctx.extra_env["ANTHROPIC_API_KEY"] == "sk-test-key"
    finally:
        adapter.teardown()


def test_antigravity_adapter_setup(tmp_path: Path) -> None:
    adapter = AntigravityAdapter()
    ctx = adapter.setup(
        env_vars={
            "LLM_API": "https://api.example.com",
            "LLM_KEY": "secret-key",
            "LLM_MODEL": "gemini-2.5-pro",
        },
        plugins=["caveman"],
        mcp_servers=["context7"],
    )
    try:
        config_path = ctx.workspace_dir / ".antigravity" / "config.json"
        assert config_path.exists()
        cfg = json.loads(config_path.read_text())
        assert cfg["api_base"] == "https://api.example.com"
        assert cfg["api_key"] == "secret-key"
        assert cfg["model"] == "gemini-2.5-pro"
        assert ctx.extra_env["ANTIGRAVITY_API_BASE"] == "https://api.example.com"
        assert ctx.extra_env["ANTIGRAVITY_API_KEY"] == "secret-key"
    finally:
        adapter.teardown()


def test_gemini_adapter_setup_with_mcp(tmp_path: Path, mcp_registry_path: Path) -> None:
    adapter = GeminiCLIAdapter()
    ctx = adapter.setup(
        env_vars={
            "LLM_API": "https://custom.gemini.proxy",
            "LLM_KEY": "gemini-secret-token",
            "LLM_MODEL": "gemini-2.5-flash",
            "HARNESS_BENCH_MCP_REGISTRY": str(mcp_registry_path),
        },
        plugins=[],
        mcp_servers=["repomix"],
    )
    try:
        settings_path = ctx.workspace_dir / ".gemini" / "settings.json"
        assert settings_path.exists()
        settings = json.loads(settings_path.read_text())
        assert settings["model"]["name"] == "gemini-2.5-flash"
        assert settings["general"]["defaultApprovalMode"] == "auto_edit"

        ext_path = ctx.workspace_dir / "gemini-extension.json"
        assert ext_path.exists()
        ext = json.loads(ext_path.read_text())
        assert "repomix" in ext["mcpServers"]
        assert ctx.extra_env["GEMINI_API_KEY"] == "gemini-secret-token"
        assert ctx.extra_env["GEMINI_API_BASE"] == "https://custom.gemini.proxy"
    finally:
        adapter.teardown()


def test_opencode_adapter_setup(tmp_path: Path) -> None:
    adapter = OpenCodeAdapter()
    ctx = adapter.setup(
        env_vars={
            "LLM_API": "http://localhost:4000/v1",
            "LLM_KEY": "litellm-master-key",
            "LLM_MODEL": "deepseek-r1",
        },
        plugins=[],
        mcp_servers=["repomix"],
    )
    try:
        cfg_path = ctx.workspace_dir / "opencode.json"
        assert cfg_path.exists()
        cfg = json.loads(cfg_path.read_text())
        assert cfg["model"] == "litellm/deepseek-r1"
        assert cfg["provider"]["litellm"]["options"]["baseURL"] == "http://localhost:4000/v1"
        assert cfg["provider"]["litellm"]["options"]["apiKey"] == "litellm-master-key"
        assert "deepseek-r1" in cfg["provider"]["litellm"]["models"]
        assert "repomix" in cfg["mcp_servers"]
        assert ctx.extra_env["OPENCODE_CONFIG"] == str(cfg_path)
        assert ctx.extra_env["OPENAI_API_BASE"] == "http://localhost:4000/v1"
    finally:
        adapter.teardown()


def test_deepseek_harness_adapter_setup(tmp_path: Path) -> None:
    adapter = DeepSeekHarnessAdapter()
    ctx = adapter.setup(
        env_vars={
            "LLM_API": "https://api.deepseek.com/v1",
            "LLM_KEY": "sk-dsh-key",
            "LLM_MODEL": "deepseek-coder",
        },
        plugins=[],
        mcp_servers=[],
    )
    try:
        cfg_path = ctx.workspace_dir / ".deepseek" / "config.json"
        assert cfg_path.exists()
        cfg = json.loads(cfg_path.read_text())
        assert cfg["api_base"] == "https://api.deepseek.com/v1"
        assert cfg["api_key"] == "sk-dsh-key"
        assert cfg["model"] == "deepseek-coder"
        assert ctx.extra_env["OPENAI_BASE"] == "https://api.deepseek.com/v1"
        assert ctx.extra_env["DEEPSEEK_API_KEY"] == "sk-dsh-key"
    finally:
        adapter.teardown()


def test_deepseek_reasonix_adapter_setup(tmp_path: Path) -> None:
    adapter = DeepSeekReasonixAdapter()
    assert adapter.name == "DeepSeek-Reasonix"
    ctx = adapter.setup(
        env_vars={
            "LLM_API": "https://api.deepseek.com/v1",
            "LLM_KEY": "sk-reasonix-key",
            "LLM_MODEL": "deepseek-v4-pro",
        },
        plugins=[],
        mcp_servers=[],
    )
    try:
        toml_path = ctx.workspace_dir / "reasonix.toml"
        assert toml_path.exists()
        content = toml_path.read_text()
        assert 'default_model = "litellm"' in content
        assert 'base_url = "https://api.deepseek.com/v1"' in content
        assert 'api_key_env = "REASONIX_API_KEY"' in content
        assert ctx.extra_env["REASONIX_API_KEY"] == "sk-reasonix-key"
        assert ctx.extra_env["OPENAI_BASE"] == "https://api.deepseek.com/v1"
    finally:
        adapter.teardown()
