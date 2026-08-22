"""Core data contracts and Pydantic schemas for Harness Benchmark 2.0."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AblationTier(StrEnum):
    """Deterministic ablation testing tiers."""

    TIER_0_BARE = "tier_0_bare"  # Bare model reasoning without tools/skills/LSP/MCP
    TIER_1_LSP = "tier_1_lsp"  # + LSP diagnostics / compiler feedback loop
    TIER_2_SKILLS = "tier_2_skills"  # + Static rule modules & utility plugins
    TIER_3_MCP = "tier_3_mcp"  # + Isolated external dynamic MCP tools
    TIER_4_FULL_STACK = "tier_4_full_stack"  # Full Stack: LSP + Skills + MCP


class FailureCategory(StrEnum):
    """Standardized failure classification."""

    NONE = "none"
    LSP_SYNTAX_ERROR = "lsp_syntax_error"
    MCP_PROTOCOL_TIMEOUT = "mcp_protocol_timeout"
    CONTEXT_OVERFLOW = "context_overflow"
    TOOL_CALL_HALLUCINATION = "tool_call_hallucination"
    ASSERTION_FAILURE = "assertion_failure"
    COMMAND_TIMEOUT = "command_timeout"
    RUNTIME_ERROR = "runtime_error"


class TaskSpec(BaseModel):
    """Specification of an evaluation task."""

    task_id: str
    prompt: str
    expected: dict[str, Any] | None = None
    workspace_subdir: str | None = None
    requires_lsp: bool = False
    requires_mcp: bool = False
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
    cache_read_input_tokens: int = 0


class ExecutionResult(BaseModel):
    """Raw result of executing a harness against a benchmark task."""

    harness: str
    benchmark: str
    task_id: str
    tier: str | None = None
    plugins: list[str] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list)
    plugins_loaded: list[str] = Field(default_factory=list)
    mcp_loaded: list[str] = Field(default_factory=list)
    lsp_enabled: bool = False
    exit_code: int
    duration_seconds: float
    stdout: str = ""
    stderr: str = ""
    tokens_input: int | None = None
    tokens_output: int | None = None
    tokens_total: int | None = None
    cache_read_input_tokens: int = 0
    turns_count: int = 1
    tool_calls: dict[str, int] = Field(default_factory=dict)
    passed: bool | None = None
    cost_usd: float | None = None
    failure_category: str = FailureCategory.NONE.value
    error: str | None = None
    oracle_log: str | None = None
    lsp_diagnostics: list[str] = Field(default_factory=list)
    turns: list[AgentTurn] = Field(default_factory=list)


class MetricSummary(BaseModel):
    """Aggregated metrics across a set of executed tasks."""

    tier: str | None = None
    count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    pass_rate: float = 0.0
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    latency_mean: float = 0.0
    turns_mean: float = 1.0
    tokens_input_total: int = 0
    tokens_output_total: int = 0
    tokens_total: int = 0
    cache_read_tokens_total: int = 0
    cache_hit_rate: float = 0.0
    tool_calls_total: int = 0
    tool_calls_by_name: dict[str, int] = Field(default_factory=dict)
    cost_usd_total: float = 0.0
    failure_breakdown: dict[str, int] = Field(default_factory=dict)
    lsp_errors_resolved: int = 0


class CellSummary(BaseModel):
    """Summary of a single matrix cell (harness x benchmark x plugins x mcp)."""

    harness: str
    benchmark: str
    plugins: list[str]
    mcp_servers: list[str]
    summary: MetricSummary


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


class TierDelta(BaseModel):
    """Statistical delta between Tier 0 Baseline and an advanced tier."""

    tier_name: str
    pass_rate: float
    delta_pass_rate: float  # +X%
    tokens_per_task: int
    delta_tokens_pct: float  # -Y%
    latency_p50: float
    delta_latency_pct: float
    turns_mean: float
    delta_turns_pct: float
    cost_total: float
    delta_cost_pct: float


class MultiTierAblationReport(BaseModel):
    """Full 5-tier ablation comparison across a harness and benchmark suite."""

    harness: str
    benchmark: str
    model: str
    tier_deltas: dict[str, TierDelta] = Field(default_factory=dict)
    lsp_improvement_pct: float = 0.0
    skills_improvement_pct: float = 0.0
    mcp_improvement_pct: float = 0.0
    full_stack_improvement_pct: float = 0.0
    summary_verdict: str = ""


class BenchmarkReport(BaseModel):
    """Top-level serialized report of an entire benchmark run."""

    run_id: str
    name: str = "ad-hoc"
    started_at: float = Field(default_factory=time.time)
    finished_at: float | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    summaries: list[CellSummary] = Field(default_factory=list)
    ablation_reports: list[MultiTierAblationReport] = Field(default_factory=list)
    results: list[ExecutionResult] = Field(default_factory=list)
