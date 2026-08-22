"""Unified Extension Manager for Plugins, MCP Servers, and Skills."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from extensions.base import BaseExtensionManager, ExtensionSpec


class UnifiedExtensionManager(BaseExtensionManager):
    """Manages discovery, staging, and lifecycle for plugins, MCP servers, and skills."""

    def __init__(
        self,
        plugin_registry_path: Path | None = None,
        mcp_registry_path: Path | None = None,
    ) -> None:
        root = Path(__file__).resolve().parents[1]
        self.plugin_registry_path = plugin_registry_path or (root / "plugins" / "registry.json")
        self.mcp_registry_path = mcp_registry_path or (root / "mcp" / "mcp_registry.json")
        self._plugins_cache: dict[str, ExtensionSpec] | None = None
        self._mcp_cache: dict[str, ExtensionSpec] | None = None

    def list_plugins(self) -> dict[str, ExtensionSpec]:
        if self._plugins_cache is None:
            self._plugins_cache = {}
            if self.plugin_registry_path.exists():
                try:
                    data = json.loads(self.plugin_registry_path.read_text())
                    for name, meta in data.get("plugins", {}).items():
                        self._plugins_cache[name] = ExtensionSpec(
                            name=name,
                            extension_type="plugin",
                            display_name=meta.get("display_name", name),
                            description=meta.get("description", ""),
                            source_path=meta.get("source_path"),
                            config=meta,
                        )
                except Exception:
                    pass
        return self._plugins_cache

    def list_mcp_servers(self) -> dict[str, ExtensionSpec]:
        if self._mcp_cache is None:
            self._mcp_cache = {}
            if self.mcp_registry_path.exists():
                try:
                    data = json.loads(self.mcp_registry_path.read_text())
                    for name, meta in data.get("servers", {}).items():
                        self._mcp_cache[name] = ExtensionSpec(
                            name=name,
                            extension_type="mcp",
                            display_name=meta.get("display_name", name),
                            description=meta.get("description", ""),
                            config=meta,
                        )
                except Exception:
                    pass
        return self._mcp_cache

    def stage_for_harness(
        self,
        harness_name: str,
        workspace_dir: Path,
        extensions: list[str],
    ) -> dict[str, Any]:
        """Stage plugins and MCP configurations into the target workspace."""
        plugins_meta = self.list_plugins()
        extras: dict[str, Any] = {"env": {}, "args": []}

        # Stage Plugins
        staged_plugins = [e for e in extensions if e in plugins_meta]
        if staged_plugins:
            staging_root = workspace_dir / ".staged_plugins"
            staging_root.mkdir(parents=True, exist_ok=True)
            for name in staged_plugins:
                spec = plugins_meta[name]
                if spec.source_path:
                    src = Path(spec.source_path)
                    if not src.is_absolute():
                        src = (self.plugin_registry_path.parent / src).resolve()
                    if src.exists():
                        dst = staging_root / name
                        if src.is_dir():
                            shutil.copytree(src, dst, dirs_exist_ok=True)
                        else:
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src, dst)
            extras["plugin_dir"] = str(staging_root)

        return extras
