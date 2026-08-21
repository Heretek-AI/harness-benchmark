"""Shared pytest fixtures."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def plugin_registry_path(repo_root: Path) -> Path:
    return repo_root / "plugins" / "registry.json"


@pytest.fixture(scope="session")
def mcp_registry_path(repo_root: Path) -> Path:
    return repo_root / "mcp" / "mcp_registry.json"