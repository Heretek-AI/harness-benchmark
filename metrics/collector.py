"""Accumulate per-task ExecutionResults and emit comprehensive multi-tier telemetry."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from core.types import AblationTier, ExecutionResult, FailureCategory
from evaluation.composite_score import compute_composite


@dataclass
class MetricCollector:
    name: str = "default"
    _rows: list[ExecutionResult] = field(default_factory=list)

    def record(self, result: ExecutionResult, benchmark: str = "") -> None:
        if not result.benchmark:
            result.benchmark = benchmark
        # Auto-classify failure category if not set
        if result.passed is False and (
            not result.failure_category or result.failure_category == FailureCategory.NONE.value
        ):
            if result.exit_code == -1 or "timed out" in (result.stderr or "").lower():
                result.failure_category = FailureCategory.COMMAND_TIMEOUT.value
            elif "syntaxerror" in (result.oracle_log or "").lower() or "syntaxerror" in (result.stderr or "").lower():
                result.failure_category = FailureCategory.LSP_SYNTAX_ERROR.value
            elif (
                "assertionerror" in (result.oracle_log or "").lower() or "assert " in (result.oracle_log or "").lower()
            ):
                result.failure_category = FailureCategory.ASSERTION_FAILURE.value
            elif "mcp" in (result.stderr or "").lower() and "timeout" in (result.stderr or "").lower():
                result.failure_category = FailureCategory.MCP_PROTOCOL_TIMEOUT.value
            elif "tool" in (result.stderr or "").lower() and "not found" in (result.stderr or "").lower():
                result.failure_category = FailureCategory.TOOL_CALL_HALLUCINATION.value
            else:
                result.failure_category = FailureCategory.RUNTIME_ERROR.value
        self._rows.append(result)

    def reset(self) -> None:
        self._rows.clear()

    def rows(self) -> list[ExecutionResult]:
        return list(self._rows)

    @staticmethod
    def infer_tier(plugins: list[str], mcp_servers: list[str], lsp_enabled: bool = False) -> str:
        """Infer deterministic ablation tier from components.

        ``lsp_enabled`` is an explicit boolean (not a proxy from
        ``lsp_diagnostics``); an empty diagnostics list must NOT be read
        as "LSP disabled".
        """
        has_plugins = bool(plugins and plugins != ["none"])
        has_mcp = bool(mcp_servers and mcp_servers != ["none"])

        if lsp_enabled and has_plugins and has_mcp:
            return AblationTier.TIER_4_FULL_STACK.value
        if has_mcp:
            return AblationTier.TIER_3_MCP.value
        if has_plugins:
            return AblationTier.TIER_2_SKILLS.value
        if lsp_enabled:
            return AblationTier.TIER_1_LSP.value
        return AblationTier.TIER_0_BARE.value

    def summarize(self) -> dict[str, Any]:
        rows = self._rows
        if not rows:
            return {
                "count": 0,
                "passed_count": 0,
                "failed_count": 0,
                "pass_rate": None,
                "pass_at_1": 0.0,
                "pass_at_2": None,
                "pass_at_3": None,
                "latency_p50": None,
                "latency_p95": None,
                "latency_mean": None,
                "turns_mean": 1.0,
                "tokens_input_total": None,
                "tokens_output_total": None,
                "tokens_total": None,
                "cache_read_tokens_total": 0,
                "cache_hit_rate": 0.0,
                "cost_usd_total": None,
                "tool_calls_total": 0,
                "tool_calls_by_name": {},
                "failure_breakdown": {},
                "lsp_errors_resolved": 0,
                "security_findings_total": 0,
                "composite_score": None,
            }

        scored = [r for r in rows if r.passed is not None]
        passed_count = sum(1 for r in scored if r.passed)
        failed_count = sum(1 for r in scored if not r.passed)
        pass_rate = passed_count / len(scored) if scored else None

        latencies = sorted(r.duration_seconds for r in rows)
        p50 = latencies[int(len(latencies) * 0.5)]
        p95 = latencies[min(int(len(latencies) * 0.95), len(latencies) - 1)]
        mean_lat = sum(latencies) / len(latencies)

        turns = [getattr(r, "turns_count", 1) or 1 for r in rows]
        turns_mean = round(sum(turns) / len(turns), 2)

        tokens_in = sum(r.tokens_input or 0 for r in rows)
        tokens_out = sum(r.tokens_output or 0 for r in rows)
        tokens_total = sum(r.tokens_total or ((r.tokens_input or 0) + (r.tokens_output or 0)) for r in rows)
        cache_read = sum(getattr(r, "cache_read_input_tokens", 0) or 0 for r in rows)
        cache_hit_rate = round(cache_read / (tokens_in + cache_read), 4) if (tokens_in + cache_read) > 0 else 0.0

        cost = sum(r.cost_usd or 0.0 for r in rows)

        tool_counts: Counter[str] = Counter()
        failure_counts: Counter[str] = Counter()
        lsp_resolved = sum(len(getattr(r, "lsp_diagnostics", [])) for r in rows)

        security_findings_total = sum(len(getattr(r, "security_findings", []) or []) for r in rows)

        for r in rows:
            for name, n in r.tool_calls.items():
                tool_counts[name] += n
            if r.passed is False:
                cat = getattr(r, "failure_category", FailureCategory.RUNTIME_ERROR.value)
                failure_counts[cat] += 1

        first_r = rows[0]
        tier = self.infer_tier(
            first_r.plugins,
            first_r.mcp_servers,
            bool(getattr(first_r, "lsp_enabled", False)),
        )

        # Composite score: prefer the per-task (richer) computation;
        # fall back to a summary-only estimate when results aren't held
        # (callers that want the richer score can call
        # ``MetricCollector.summarize_with_results(rows)`` directly).
        try:
            from core.types import MetricSummary as _MS

            composite = compute_composite(
                _MS(
                    count=len(rows),
                    passed_count=passed_count,
                    failed_count=failed_count,
                    pass_rate=pass_rate or 0.0,
                    tokens_total=tokens_total,
                ),
                results=rows,
            )
        except Exception:
            composite = None

        return {
            "tier": tier,
            "count": len(rows),
            "passed_count": passed_count,
            "failed_count": failed_count,
            "pass_rate": pass_rate,
            "pass_at_1": pass_rate if pass_rate is not None else 0.0,
            "pass_at_2": None,
            "pass_at_3": None,
            "latency_p50": round(p50, 3),
            "latency_p95": round(p95, 3),
            "latency_mean": round(mean_lat, 3),
            "turns_mean": turns_mean,
            "tokens_input_total": tokens_in,
            "tokens_output_total": tokens_out,
            "tokens_total": tokens_total,
            "cache_read_tokens_total": cache_read,
            "cache_hit_rate": cache_hit_rate,
            "cost_usd_total": round(cost, 4),
            "tool_calls_total": sum(tool_counts.values()),
            "tool_calls_by_name": dict(tool_counts.most_common()),
            "failure_breakdown": dict(failure_counts.most_common()),
            "lsp_errors_resolved": lsp_resolved,
            "security_findings_total": security_findings_total,
            "composite_score": composite,
        }
