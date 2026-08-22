"""MCP launcher behaviour.

We use a 1-line ``echo`` command to keep the test hermetic — the launcher
just needs to spawn + reap the subprocess.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from mcp import MCPLauncher


@pytest.mark.skipif(shutil.which("echo") is None, reason="no /bin/echo on PATH")
def test_launch_and_terminate(mcp_registry_path: Path, tmp_path: Path) -> None:
    """Round-trip: launch 'echo' as a stdio MCP, terminate it cleanly."""
    import json

    raw = json.loads(mcp_registry_path.read_text())
    raw["servers"]["test-echo"] = {
        "display_name": "Echo test",
        "command": shutil.which("echo"),
        "args": [],
        "env": {},
        "transport": "stdio",
    }
    fake_registry = tmp_path / "fake_registry.json"
    fake_registry.write_text(json.dumps(raw))
    launcher = MCPLauncher(fake_registry)
    handles = launcher.launch(["test-echo"])
    assert len(handles) == 1
    assert handles[0].proc is not None
    # echo exits immediately on stdin EOF; just wait it out.
    handles[0].proc.wait(timeout=2)
    # terminate() must be safe to call even after natural exit.
    launcher.terminate(handles)


def test_launch_unknown_raises(mcp_registry_path: Path) -> None:
    launcher = MCPLauncher(mcp_registry_path)
    with pytest.raises(KeyError):
        launcher.launch(["nonexistent-mcp"])
