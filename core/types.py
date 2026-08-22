"""Core data contracts and Pydantic schemas for Harness Benchmark 2.0."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field


class TaskSpec(BaseModel):
    """Specification of an evaluation task."""

    task_id: str
    prompt: str
    expected: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """Structured record of a single tool invocation."""

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: str | None = None
    exit_code: int | None = None
    duration_seconds: float = 0.0
    timestamp: float = Field(default_factory=time.time)


class AgentTurn(BaseModel):
    """Record of a single conversational turn by the agent harness."""

    turn_index: int
    role: str = "assistant"
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tokens_input: int = 0
    tokens_output: int = 0


class ExecutionResult(BaseModel):
    """Raw result of executing a harness against a benchmark task."""

    harness: str
    benchmark: str
    task_id: str
    plugins: list[str] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list)
    exit_code: int
    duration_seconds: float
    stdout: str = ""
    stderr: str = ""
    tokens_input: int | None = None
    tokens_output: int | None = None
    tokens_total: int | None = None
    tool_calls: dict[str, int] = Field(default_factory=dict)
    passed: bool | None = None
    cost_usd: float | None = None
    error: str | None = None
    oracle_log: str | None = None
    turns: list[AgentTurn] = Field(default_factory=list)


class MetricSummary(BaseModel):
    """Aggregated metrics across a set of executed tasks."""

    count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    pass_rate: float = 0.0
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    latency_mean: float = 0.0
    tokens_input_total: int = 0
    tokens_output_total: int = 0
    tokens_total: int = 0
    tool_calls_total: int = 0
    cost_usd_total: float = 0.0


class CellSummary(BaseModel):
    """Summary of a single matrix cell (harness x benchmark x plugins x mcp)."""

    harness: str
    benchmark: str
    plugins: list[str]
    mcp_servers: list[str]
    summary: MetricSummary


class BenchmarkReport(BaseModel):
    """Top-level serialized report of an entire benchmark run."""

    run_id: str
    name: str = "ad-hoc"
    started_at: float = Field(default_factory=time.time)
    finished_at: float | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    summaries: list[CellSummary] = Field(default_factory=list)
    results: list[ExecutionResult] = Field(default_factory=list)


class ABComparisonResult(BaseModel):
    """Comparative analysis between a baseline configuration and a treatment."""

    harness: str
    benchmark: str
    baseline_plugins: list[str]
    baseline_mcp: list[str]
    treatment_plugins: list[str]
    treatment_mcp: list[str]
    baseline_pass_rate: float
    treatment_pass_rate: float
    delta_pass_rate: float
    baseline_latency_p50: float
    treatment_latency_p50: float
    delta_latency_pct: float
    baseline_tokens_total: int
    treatment_tokens_total: int
    delta_tokens_pct: float
    baseline_tool_calls: int
    treatment_tool_calls: int
    delta_tool_calls_pct: float
    narrative_verdict: str
