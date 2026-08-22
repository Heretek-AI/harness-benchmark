"""Dynamic plugin loader.

The runner calls ``synthesize_agent_config(adapter, plugin_names)`` once
per (adapter, plugin-set) tuple and gets back a directory the adapter can
hand to its harness via the harness-specific mechanism (``--plugin-dir``,
``gemini-extension.json``, ``opencode.json``, ...).

Each plugin in the registry is a directory tree under ``source_path``; the
loader symlinks (or copies, on filesystems that don't support symlinks)
each requested plugin into a single staging root so the harness sees a
flat plugin root.

Adding a new plugin is a one-line edit to ``plugins/registry.json`` —
no Python changes required.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PluginSpec(BaseModel):
    name: str
    display_name: str
    source_path: Path
    format: str
    injects: list[str]
    description: str = ""


class PluginLoader:
    """Read-only loader for ``plugins/registry.json``."""

    def __init__(self, registry_path: str | Path) -> None:
        self.registry_path = Path(registry_path)
        with self.registry_path.open() as f:
            data = json.load(f)
        self._entries: dict[str, PluginSpec] = {
            name: PluginSpec(
                name=name,
                display_name=spec["display_name"],
                source_path=Path(spec["source_path"]),
                format=spec["format"],
                injects=list(spec.get("injects", [])),
                description=spec.get("description", ""),
            )
            for name, spec in data["plugins"].items()
        }

    def names(self) -> list[str]:
        return sorted(self._entries)

    def load(self, name: str) -> PluginSpec:
        try:
            return self._entries[name]
        except KeyError as exc:
            raise KeyError(f"plugin {name!r} not in registry; known: {sorted(self._entries)}") from exc

    def synthesize_agent_config(
        self,
        adapter_name: str,
        plugin_names: list[str],
        staging_root: str | Path | None = None,
    ) -> Path | None:
        """Materialize a plugin root the given adapter can consume.

        Returns the absolute path of the staging root, or ``None`` when no
        plugins were requested (so the adapter can skip its plugin flag).
        Caller is responsible for cleanup (the runner passes the path into
        the adapter, which scrubs it via ``BaseAgentAdapter.teardown``).
        """
        cleaned: list[str] = [n for n in (plugin_names or []) if n and n != "none"]
        if not cleaned:
            return None

        if staging_root is None:
            staging = Path(tempfile.mkdtemp(prefix=f"hb-plugins-{adapter_name}-"))
        else:
            staging = Path(staging_root)
            staging.mkdir(parents=True, exist_ok=True)

        for name in cleaned:
            spec = self.load(name)
            if not spec.source_path.exists():
                logger.warning(
                    "plugin %s source_path %s does not exist; skipping",
                    name,
                    spec.source_path,
                )
                continue
            dest = staging / name
            if dest.exists() or dest.is_symlink():
                if dest.is_symlink():
                    dest.unlink()
                else:
                    shutil.rmtree(dest)
            # Symlinks are cheaper and keep the source-of-truth single; on
            # filesystems that lack symlink support, fall back to copy.
            try:
                dest.symlink_to(spec.source_path.resolve(), target_is_directory=True)
            except (OSError, NotImplementedError):
                shutil.copytree(spec.source_path, dest)
        logger.debug(
            "synthesized plugin staging root %s with plugins=%s",
            staging,
            cleaned,
        )
        return staging
