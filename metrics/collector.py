"""Accumulate per-task ``ExecutionResult``s and emit a summary dict.

Designed for streaming use inside the runner: ``record`` is called once per
task; ``summarize`` is called once per (harness, benchmark) cell. The
collector never holds raw stdout (only the structured fields) so memory
stays flat for long runs.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from agents.base import ExecutionResult


@dataclass
class MetricCollector:
    name: str = "default"
    _rows: list[ExecutionResult] = field(default_factory=list)

    def record(self, result: ExecutionResult, benchmark: str = "") -> None:
        # Decorate the result with the benchmark label so the report can
        # attribute each row without a separate index.
        if not result.benchmark:
            result.benchmark = benchmark
        self._rows.append(result)

    def reset(self) -> None:
        self._rows.clear()

    def rows(self) -> list[ExecutionResult]:
        return list(self._rows)

    def summarize(self) -> dict[str, Any]:
        rows = self._rows
        if not rows:
            return {
                "count": 0,
                "pass_rate": None,
                "latency_p50": None,
                "latency_p95": None,
                "tokens_input_total": None,
                "tokens_output_total": None,
                "cost_usd_total": None,
                "tool_calls_total": 0,
                "tool_calls_by_name": {},
            }
        scored = [r for r in rows if r.passed is not None]
        pass_rate = sum(1 for r in scored if r.passed) / len(scored) if scored else None
        latencies = sorted(r.duration_seconds for r in rows)
        p50 = latencies[int(len(latencies) * 0.5)]
        p95 = latencies[min(int(len(latencies) * 0.95), len(latencies) - 1)]
        tokens_in = sum(r.tokens_input or 0 for r in rows)
        tokens_out = sum(r.tokens_output or 0 for r in rows)
        cost = sum(r.cost_usd or 0.0 for r in rows)
        tool_counts: Counter[str] = Counter()
        for r in rows:
            for name, n in r.tool_calls.items():
                tool_counts[name] += n
        return {
            "count": len(rows),
            "pass_rate": pass_rate,
            "latency_p50": round(p50, 3),
            "latency_p95": round(p95, 3),
            "tokens_input_total": tokens_in,
            "tokens_output_total": tokens_out,
            "cost_usd_total": round(cost, 4),
            "tool_calls_total": sum(tool_counts.values()),
            "tool_calls_by_name": dict(tool_counts.most_common()),
        }
