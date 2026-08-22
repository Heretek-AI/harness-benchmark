"""Tests for the structured telemetry emitter."""

from __future__ import annotations

import json
from pathlib import Path

from metrics.telemetry import TelemetryEmitter


def test_task_start_event(tmp_path: Path) -> None:
    with TelemetryEmitter(run_id="test-001", output_dir=tmp_path) as emitter:
        emitter.task_start(task_id="t1", harness="stub", benchmark="harbor")
    lines = (emitter.output_path).read_text().strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event"] == "task_start"
    assert event["task_id"] == "t1"
    assert event["harness"] == "stub"
    assert event["run_id"] == "test-001"


def test_tool_use_event(tmp_path: Path) -> None:
    with TelemetryEmitter(run_id="test-002", output_dir=tmp_path) as emitter:
        emitter.tool_use(task_id="t1", tool_name="bash", detail="echo hi")
    event = json.loads(emitter.output_path.read_text().strip())
    assert event["event"] == "tool_use"
    assert event["tool_name"] == "bash"
    assert event["detail"] == "echo hi"


def test_token_usage_event(tmp_path: Path) -> None:
    with TelemetryEmitter(run_id="test-003", output_dir=tmp_path) as emitter:
        emitter.token_usage(task_id="t1", tokens_in=100, tokens_out=50)
    event = json.loads(emitter.output_path.read_text().strip())
    assert event["event"] == "token_usage"
    assert event["tokens_in"] == 100
    assert event["tokens_out"] == 50


def test_task_end_event(tmp_path: Path) -> None:
    with TelemetryEmitter(run_id="test-004", output_dir=tmp_path) as emitter:
        emitter.task_end(task_id="t1", passed=True, duration=1.5)
    event = json.loads(emitter.output_path.read_text().strip())
    assert event["event"] == "task_end"
    assert event["passed"] is True
    assert event["duration_seconds"] == 1.5


def test_multiple_events_accumulate(tmp_path: Path) -> None:
    with TelemetryEmitter(run_id="test-005", output_dir=tmp_path) as emitter:
        emitter.task_start(task_id="t1", harness="stub", benchmark="harbor")
        emitter.tool_use(task_id="t1", tool_name="bash")
        emitter.token_usage(task_id="t1", tokens_in=10, tokens_out=5)
        emitter.task_end(task_id="t1", passed=True, duration=0.5)
        assert emitter.event_count == 4
    lines = emitter.output_path.read_text().strip().splitlines()
    assert len(lines) == 4
    events = [json.loads(l) for l in lines]
    assert [e["event"] for e in events] == ["task_start", "tool_use", "token_usage", "task_end"]


def test_long_detail_truncated(tmp_path: Path) -> None:
    long_detail = "x" * 1000
    with TelemetryEmitter(run_id="test-006", output_dir=tmp_path) as emitter:
        emitter.tool_use(task_id="t1", tool_name="bash", detail=long_detail)
    event = json.loads(emitter.output_path.read_text().strip())
    assert len(event["detail"]) <= 500


def test_output_dir_created(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "runs"
    with TelemetryEmitter(run_id="test-007", output_dir=out) as emitter:
        emitter.task_start(task_id="t1", harness="stub", benchmark="harbor")
    assert emitter.output_path.exists()
