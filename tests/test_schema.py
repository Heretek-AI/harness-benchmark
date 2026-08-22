"""Schema validation for the run-config presets."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml


@pytest.mark.parametrize(
    "preset_name",
    ["full_matrix", "mcp_isolation", "smoke_test"],
)
def test_preset_validates_against_schema(repo_root: Path, preset_name: str) -> None:
    schema = json.loads((repo_root / "configs" / "schema.json").read_text())
    preset = yaml.safe_load((repo_root / "configs" / "presets" / f"{preset_name}.yaml").read_text())
    jsonschema.validate(preset, schema)
