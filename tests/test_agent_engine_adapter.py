"""Tests for the agent-engine adapter and fallback transport."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agents import ADAPTERS
from agents.agent_engine_adapter import (
    AgentEngineAdapter,
    fallback_env_enabled,
)
from agents.base import AdapterContext


def test_agent_engine_adapter_appears_in_registry() -> None:
    """`agent-engine` must be a first-class adapter."""
    assert "agent-engine" in ADAPTERS
    assert ADAPTERS["agent-engine"] is AgentEngineAdapter


def test_agent_engine_adapter_resolve_cli_always_present() -> None:
    assert AgentEngineAdapter.resolve_cli() is not None


def test_agent_engine_adapter_runs_against_mock_endpoint(tmp_path: Path) -> None:
    """Mock run_agent_loop_timed and verify ExecutionResult shape."""
    fake_outcome = {
        "final_output": "<execute_bash>\n<write_file>\n",
        "tokens_in": 123,
        "tokens_out": 45,
        "tool_calls_count": 2,
        "duration_seconds": 0.5,
    }
    with patch("agents.agent_engine_adapter.run_agent_loop_timed", return_value=fake_outcome) as mocked:
        adapter = AgentEngineAdapter()
        ctx = AdapterContext(workspace_dir=tmp_path)
        adapter._ctx = ctx
        result = adapter._on_execute_task(
            prompt="do something",
            workspace_dir=tmp_path,
            timeout=10,
        )
    assert mocked.call_count == 1
    assert result.harness == "agent-engine"
    assert result.exit_code == 0
    assert result.tokens_input == 123
    assert result.tokens_output == 45
    assert result.tokens_total == 168
    assert result.tool_calls.get("execute_bash") == 1
    assert result.tool_calls.get("write_file") == 1


def test_fallback_env_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARNESS_BENCH_FALLBACK_ENGINE", raising=False)
    assert fallback_env_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", "TRUE"])
def test_fallback_env_enabled_for_truthy_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("HARNESS_BENCH_FALLBACK_ENGINE", value)
    assert fallback_env_enabled() is True


def test_fallback_triggered_when_cli_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With fallback enabled and CLI missing, the adapter routes to engine."""
    monkeypatch.setenv("HARNESS_BENCH_FALLBACK_ENGINE", "1")

    # Build a minimal adapter that uses the base-class _on_execute_task
    # (which is the path that consults _should_fallback_to_engine).
    # We can't subclass AgentEngineAdapter because it overrides the
    # default _on_execute_task with a direct run_agent_loop call.
    from agents.base import BaseAgentAdapter

    class _CliLessAdapter(BaseAgentAdapter):
        name = "cliless-test"
        cli_binary = "cliless"

        def _on_setup(self, ctx, plugins, mcp_servers):
            return None

        @staticmethod
        def resolve_cli() -> str | None:
            return None

    with (
        patch(
            "agents.agent_engine_adapter.AgentEngineAdapter.fallback_run",
            return_value=_make_result(),
        ) as fallback,
        patch.object(_CliLessAdapter, "_run_cli") as run_cli,
    ):
        adapter = _CliLessAdapter()
        adapter._ctx = AdapterContext(workspace_dir=tmp_path)
        adapter._on_execute_task(prompt="hi", workspace_dir=tmp_path, timeout=10)
    assert fallback.call_count == 1
    assert run_cli.call_count == 0


def test_fallback_not_triggered_when_cli_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fallback env enabled but CLI resolves -> still goes through CLI path."""
    monkeypatch.setenv("HARNESS_BENCH_FALLBACK_ENGINE", "1")

    from agents.base import BaseAgentAdapter

    class _FakeAdapter(BaseAgentAdapter):
        name = "fake-cli"
        cli_binary = "fake-cli"

        def _on_setup(self, ctx, plugins, mcp_servers):
            return None

        @staticmethod
        def resolve_cli() -> str | None:
            return "/usr/bin/fake"

    with patch.object(_FakeAdapter, "_run_cli") as run_cli:
        a = _FakeAdapter()
        a._ctx = AdapterContext(workspace_dir=tmp_path)
        a._on_execute_task(prompt="x", workspace_dir=tmp_path, timeout=10)
    assert run_cli.call_count == 1


def _make_result():
    from agents.base import ExecutionResult

    return ExecutionResult(
        harness="agent-engine-fallback",
        benchmark="",
        task_id="",
        exit_code=0,
        duration_seconds=0.0,
        stdout="ok",
        tokens_input=10,
        tokens_output=5,
        tokens_total=15,
    )
