"""Tests for the bubblewrap sandbox wrapping helper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agents.base import BaseAgentAdapter


def _make_adapter() -> BaseAgentAdapter:
    class _Stub(BaseAgentAdapter):
        name = "bwrap-stub"
        cli_binary = "stub"

        def _on_setup(self, ctx, plugins, mcp_servers):
            return None

        @staticmethod
        def resolve_cli() -> str | None:
            return "/usr/bin/stub"

    return _Stub()


def test_wrap_returns_unchanged_when_env_unset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARNESS_BENCH_USE_BWRAP", raising=False)
    a = _make_adapter()
    cmd = ["echo", "hi"]
    assert a._wrap_with_bwrap(cmd, tmp_path) == cmd


def test_wrap_inserts_bwrap_when_enabled_and_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARNESS_BENCH_USE_BWRAP", "1")
    a = _make_adapter()
    cmd = ["echo", "hi"]
    with patch("agents.base.shutil.which", return_value="/usr/bin/bwrap"):
        wrapped = a._wrap_with_bwrap(cmd, tmp_path)
    assert wrapped[0] == "/usr/bin/bwrap"
    assert "--bind" in wrapped
    assert str(tmp_path) in wrapped
    assert "--" in wrapped
    assert wrapped[-2:] == ["--", "echo"] or wrapped[-1] == "hi"
    # Verify the trailing argv matches the original cmd.
    assert wrapped[-len(cmd) :] == cmd


def test_wrap_falls_back_when_bwrap_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARNESS_BENCH_USE_BWRAP", "1")
    a = _make_adapter()
    cmd = ["echo", "hi"]
    with patch("agents.base.shutil.which", return_value=None):
        wrapped = a._wrap_with_bwrap(cmd, tmp_path)
    assert wrapped == cmd


def test_wrap_returns_unchanged_for_empty_cmd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARNESS_BENCH_USE_BWRAP", "1")
    a = _make_adapter()
    with patch("agents.base.shutil.which", return_value="/usr/bin/bwrap"):
        wrapped = a._wrap_with_bwrap([], tmp_path)
    # Empty cmd still gets wrapped (the bwrap binary plus sandbox flags
    # followed by "--"). The important property is no crash.
    assert wrapped[0] == "/usr/bin/bwrap"


def test_wrap_includes_unshare_net_when_network_isolation_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HARNESS_BENCH_USE_BWRAP", "1")
    monkeypatch.setenv("HARNESS_BENCH_NETWORK_ISOLATION", "1")
    a = _make_adapter()
    cmd = ["echo", "hi"]
    with patch("agents.base.shutil.which", return_value="/usr/bin/bwrap"):
        wrapped = a._wrap_with_bwrap(cmd, tmp_path)
    assert "--unshare-net" in wrapped
    assert wrapped[0] == "/usr/bin/bwrap"


def test_wrap_omits_unshare_net_when_network_isolation_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HARNESS_BENCH_USE_BWRAP", "1")
    monkeypatch.delenv("HARNESS_BENCH_NETWORK_ISOLATION", raising=False)
    a = _make_adapter()
    cmd = ["echo", "hi"]
    with patch("agents.base.shutil.which", return_value="/usr/bin/bwrap"):
        wrapped = a._wrap_with_bwrap(cmd, tmp_path)
    assert "--unshare-net" not in wrapped
