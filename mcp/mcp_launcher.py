"""MCP server launcher.

Reads ``mcp/mcp_registry.json`` and starts each named server as a
subprocess in stdio (or SSE) mode. The launcher is responsible only for
process lifecycle; the adapter passes the resulting command/env into its
harness-specific MCP config (e.g., Claude Code's ``--mcp-config``,
Gemini's ``gemini-extension.json``).

Handles are returned as ``MCPServerHandle`` objects containing the
``Popen`` and the resolved spec, so adapters can introspect
``command``/``args``/``env`` when building their config.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MCPServerHandle:
    name: str
    spec: dict[str, Any]
    proc: subprocess.Popen[bytes] | None = None
    transport: str = "stdio"
    pid: int = field(default=0)


class MCPLauncher:
    """Lifecycle owner for ``mcp/mcp_registry.json``."""

    def __init__(self, registry_path: str | Path) -> None:
        self.registry_path = Path(registry_path)
        with self.registry_path.open() as f:
            data = json.load(f)
        self._entries: dict[str, dict[str, Any]] = data["servers"]

    def names(self) -> list[str]:
        return sorted(self._entries)

    def spec(self, name: str) -> dict[str, Any]:
        try:
            return self._entries[name]
        except KeyError as exc:
            raise KeyError(
                f"MCP server {name!r} not in registry; known: {sorted(self._entries)}"
            ) from exc

    # ---- lifecycle ----

    def launch(self, names: list[str]) -> list[MCPServerHandle]:
        """Spawn each requested MCP server.

        Returns handles even when spawning fails (proc=None) so callers can
        include the failure in their harness config and observe the
        resulting error in the bench output.
        """
        handles: list[MCPServerHandle] = []
        cleaned = [n for n in (names or []) if n and n != "none"]
        for name in cleaned:
            entry = self.spec(name)
            transport = entry.get("transport", "stdio")
            if transport != "stdio":
                # SSE / HTTP transports don't need a local subprocess;
                # return a handle carrying the URL so the adapter can
                # reference it.
                handles.append(
                    MCPServerHandle(name=name, spec=entry, transport=transport)
                )
                continue
            cmd = [entry["command"], *entry.get("args", [])]
            env = {
                **os.environ,
                **{
                    k: os.path.expandvars(v) if isinstance(v, str) else v
                    for k, v in (entry.get("env") or {}).items()
                },
            }
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                )
            except (FileNotFoundError, OSError) as exc:
                logger.warning("failed to spawn MCP %s: %s", name, exc)
                handles.append(
                    MCPServerHandle(
                        name=name, spec=entry, proc=None, transport=transport
                    )
                )
                continue
            handles.append(
                MCPServerHandle(
                    name=name, spec=entry, proc=proc, transport=transport, pid=proc.pid
                )
            )
        return handles

    def wait_ready(
        self, handles: list[MCPServerHandle], timeout: float = 5.0
    ) -> None:
        """Best-effort readiness probe.

        stdio MCP servers don't expose a liveness signal over their stdio
        pipes (the harness owns the pipes after ``--mcp-config``), so we
        just confirm the process is still alive after a short delay.
        """
        deadline = time.monotonic() + timeout
        for h in handles:
            if h.proc is None:
                continue
            time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
            if h.proc.poll() is not None:
                logger.warning(
                    "MCP %s exited during startup with rc=%s",
                    h.name,
                    h.proc.returncode,
                )

    def terminate(self, handles: list[MCPServerHandle]) -> None:
        """Tear down all servers. Idempotent."""
        for h in handles:
            if h.proc is None or h.proc.poll() is not None:
                continue
            try:
                h.proc.terminate()
                try:
                    h.proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    h.proc.kill()
                    h.proc.wait(timeout=2)
            except OSError as exc:  # pragma: no cover - defensive
                logger.warning("error terminating MCP %s: %s", h.name, exc)

    # ---- helpers ----

    @staticmethod
    def which(name: str) -> str | None:
        return shutil.which(name)