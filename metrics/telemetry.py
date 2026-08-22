"""Structured telemetry export for per-task execution events.

Emits JSONL events to ``results/<run-id>/telemetry.jsonl`` with one JSON
object per line.  Events are typed via the ``event`` field:

    task_start    — emitted when a task begins execution
    tool_use      — emitted for each tool call observed in the agent output
    token_usage   — emitted when token counts are extracted
    task_end      — emitted when a task completes (includes pass/fail + duration)

Usage::

    from metrics.telemetry import TelemetryEmitter

    emitter = TelemetryEmitter(run_id="ci-12345", output_dir=Path("runs"))
    emitter.task_start(task_id="add-numbers", harness="stub", benchmark="harbor")
    emitter.tool_use(task_id="add-numbers", tool_name="bash", detail="echo hi")
    emitter.token_usage(task_id="add-numbers", tokens_in=150, tokens_out=42)
    emitter.task_end(task_id="add-numbers", passed=True, duration=1.23)
    emitter.close()
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TelemetryEmitter:
    """Append-only JSONL emitter for structured benchmark telemetry."""

    def __init__(self, run_id: str, output_dir: Path) -> None:
        self.run_id = run_id
        self.output_dir = output_dir / run_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._path = self.output_dir / "telemetry.jsonl"
        self._handle = open(self._path, "a", encoding="utf-8")
        self._event_count = 0

    def _emit(self, event_type: str, **fields: Any) -> None:
        record = {"event": event_type, "run_id": self.run_id, **fields}
        line = json.dumps(record, default=str, ensure_ascii=False)
        self._handle.write(line + "\n")
        self._handle.flush()
        self._event_count += 1

    def task_start(
        self,
        task_id: str,
        harness: str,
        benchmark: str,
        plugins: list[str] | None = None,
        mcp_servers: list[str] | None = None,
    ) -> None:
        """Emit a task_start event."""
        self._emit(
            "task_start",
            task_id=task_id,
            harness=harness,
            benchmark=benchmark,
            plugins=plugins or [],
            mcp_servers=mcp_servers or [],
        )

    def tool_use(
        self,
        task_id: str,
        tool_name: str,
        detail: str | None = None,
    ) -> None:
        """Emit a tool_use event."""
        fields: dict[str, Any] = {"task_id": task_id, "tool_name": tool_name}
        if detail:
            fields["detail"] = detail[:500]  # truncate long details
        self._emit("tool_use", **fields)

    def token_usage(
        self,
        task_id: str,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
    ) -> None:
        """Emit a token_usage event."""
        self._emit(
            "token_usage",
            task_id=task_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )

    def task_end(
        self,
        task_id: str,
        passed: bool,
        duration: float,
        exit_code: int | None = None,
        error: str | None = None,
    ) -> None:
        """Emit a task_end event."""
        fields: dict[str, Any] = {
            "task_id": task_id,
            "passed": passed,
            "duration_seconds": duration,
        }
        if exit_code is not None:
            fields["exit_code"] = exit_code
        if error:
            fields["error"] = error[:500]
        self._emit("task_end", **fields)

    @property
    def event_count(self) -> int:
        return self._event_count

    @property
    def output_path(self) -> Path:
        return self._path

    def close(self) -> None:
        """Flush and close the JSONL file."""
        self._handle.flush()
        self._handle.close()

    def __enter__(self) -> TelemetryEmitter:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
