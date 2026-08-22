"""Abstract base interfaces for extensions (Plugins, MCP, Skills)."""

from __future__ import annotations

import abc
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ExtensionSpec(BaseModel):
    """Metadata specification of an extension."""

    name: str
    extension_type: str  # "plugin" | "mcp" | "skill"
    display_name: str
    description: str = ""
    source_path: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class BaseExtensionManager(abc.ABC):
    """Abstract manager responsible for staging and lifecycle of extensions."""

    @abc.abstractmethod
    def stage_for_harness(
        self,
        harness_name: str,
        workspace_dir: Path,
        extensions: list[str],
    ) -> dict[str, Any]:
        """Stage requested extensions into workspace and return environment/config extras."""
        raise NotImplementedError
