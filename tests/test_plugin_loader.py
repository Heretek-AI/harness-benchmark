"""Plugin loader behaviour."""

from __future__ import annotations

from pathlib import Path

import pytest

from plugins import PluginLoader


def test_load_known_plugin(plugin_registry_path: Path) -> None:
    loader = PluginLoader(plugin_registry_path)
    spec = loader.load("caveman")
    assert spec.name == "caveman"
    assert spec.source_path.exists(), spec.source_path
    assert "commands" in spec.injects


def test_load_unknown_plugin_raises(plugin_registry_path: Path) -> None:
    loader = PluginLoader(plugin_registry_path)
    with pytest.raises(KeyError):
        loader.load("does-not-exist")


def test_synthesize_with_none_returns_none(plugin_registry_path: Path) -> None:
    loader = PluginLoader(plugin_registry_path)
    out = loader.synthesize_agent_config("claude-code", ["none"])
    assert out is None


def test_synthesize_makes_staging_root(plugin_registry_path: Path, tmp_path: Path) -> None:
    loader = PluginLoader(plugin_registry_path)
    staging = loader.synthesize_agent_config("claude-code", ["caveman"], staging_root=tmp_path / "plugins")
    assert staging is not None
    assert (staging / "caveman").exists()
