"""Weighted 5-dimension composite benchmark score.

Adopted from §5 of the Gemini deep-research report:

- Task Correctness    (0.40) — cell-level pass rate
- Verification Quality (0.20) — fraction of tasks with a non-empty oracle log
- Policy Adherence    (0.15) — 1 - (security_findings / max(1, total_tool_calls))
- Context Efficiency  (0.10) — 1 - min(tokens_per_task / max_window, 1)
- Recovery Behavior   (0.10) — 1 - hallucinated_tool_calls / total_tool_calls

Returns a value in [0, 1]. Dimensions are normalised individually so
the score stays meaningful when some metrics are missing (e.g., a
harness without MCP traffic has 0 security findings by construction).
"""

from __future__ import annotations

from core.types import ExecutionResult, MetricSummary

# Relative weights from the PDF §5. The PDF lists 0.40 / 0.20 / 0.15 / 0.10 / 0.10
# which sums to 0.95; we renormalize at import time so the composite is
# guaranteed to land in [0, 1] regardless of the original values.
_RAW_WEIGHTS: dict[str, float] = {
    "task_correctness": 0.40,
    "verification_quality": 0.20,
    "policy_adherence": 0.15,
    "context_efficiency": 0.10,
    "recovery_behavior": 0.10,
}
_RAW_SUM = sum(_RAW_WEIGHTS.values())
WEIGHTS: dict[str, float] = {k: v / _RAW_SUM for k, v in _RAW_WEIGHTS.items()}

# Tokens-per-task that we consider the practical ceiling for context-
# efficient operation. Tokens beyond this drive Context Efficiency toward 0.
ASSUMED_MAX_TOKENS = 200_000

# Recovery: categories that count as "hallucinated tool calls" — i.e.,
# the agent asked for tools that don't exist, the harness had to map them
# to nothing, or the LLM hallucinated parameter values.
RECOVERY_PENALTY_CATEGORIES = frozenset(
    {
        "tool_call_hallucination",
        "context_overflow",
    }
)


def _verification_quality(results: list[ExecutionResult]) -> float:
    """Fraction of tasks with a non-empty oracle log (or passed=False still got graded)."""
    if not results:
        return 0.0
    graded = sum(1 for r in results if r.oracle_log is not None or r.passed is not None)
    return graded / len(results)


def _policy_adherence(results: list[ExecutionResult]) -> float:
    """1 - (security_findings / total_tool_calls). Empty findings -> 1.0."""
    total_tool_calls = sum(sum(r.tool_calls.values()) for r in results)
    findings = sum(len(r.security_findings) for r in results)
    if total_tool_calls == 0 and findings == 0:
        return 1.0
    if total_tool_calls == 0:
        return max(0.0, 1.0 - findings * 0.1)
    return max(0.0, 1.0 - findings / total_tool_calls)


def _context_efficiency(results: list[ExecutionResult]) -> float:
    if not results:
        return 0.0
    counts = [r.tokens_total or 0 for r in results if r.tokens_total is not None]
    if not counts:
        return 0.0
    avg = sum(counts) / len(counts)
    return max(0.0, 1.0 - min(avg / ASSUMED_MAX_TOKENS, 1.0))


def _recovery_behavior(results: list[ExecutionResult]) -> float:
    """1 - (tool_call_hallucination + context_overflow) / total_tool_calls."""
    total_tool_calls = sum(sum(r.tool_calls.values()) for r in results)
    hall = sum(1 for r in results if r.failure_category in RECOVERY_PENALTY_CATEGORIES)
    if total_tool_calls == 0:
        return 1.0 if hall == 0 else max(0.0, 1.0 - hall * 0.1)
    return max(0.0, 1.0 - hall / max(1, total_tool_calls))


def compute_composite(
    summary: MetricSummary,
    results: list[ExecutionResult] | None = None,
) -> float:
    """Compute the composite score in [0, 1] using summary + per-task results.

    When ``results`` is omitted, dimensions that need it (verification,
    policy, context, recovery) fall back to summary-only proxies:
    verification_quality = 1.0 if count > 0, policy = 1.0,
    context_efficiency = 1 - min(tokens_total / (count * ASSUMED_MAX_TOKENS), 1),
    recovery = 1 - failed_count / count.
    """
    if summary.count == 0:
        return 0.0

    if results is not None and len(results) >= 1:
        task_correctness = summary.pass_rate or 0.0
        verification = _verification_quality(results)
        policy = _policy_adherence(results)
        context = _context_efficiency(results)
        recovery = _recovery_behavior(results)
    else:
        # Summary-only fallback. Treat verification as 1.0 when we
        # have any graded tasks (the runner always runs the grader,
        # so a non-empty cell implies graded outputs).
        task_correctness = summary.pass_rate or 0.0
        verification = 1.0 if summary.count > 0 else 0.0
        policy = 1.0
        avg_tokens = (summary.tokens_total or 0) / summary.count
        context = max(0.0, 1.0 - min(avg_tokens / ASSUMED_MAX_TOKENS, 1.0))
        recovery = max(0.0, 1.0 - summary.failed_count / summary.count) if summary.count else 0.0

    score = (
        WEIGHTS["task_correctness"] * task_correctness
        + WEIGHTS["verification_quality"] * verification
        + WEIGHTS["policy_adherence"] * policy
        + WEIGHTS["context_efficiency"] * context
        + WEIGHTS["recovery_behavior"] * recovery
    )
    return round(max(0.0, min(1.0, score)), 4)


def explain_composite(
    summary: MetricSummary,
    results: list[ExecutionResult] | None = None,
) -> dict[str, float]:
    """Return the per-dimension [0,1] values that feed into compute_composite."""
    if results is not None and len(results) >= 1:
        return {
            "task_correctness": summary.pass_rate or 0.0,
            "verification_quality": _verification_quality(results),
            "policy_adherence": _policy_adherence(results),
            "context_efficiency": _context_efficiency(results),
            "recovery_behavior": _recovery_behavior(results),
        }
    return {
        "task_correctness": summary.pass_rate or 0.0,
        "verification_quality": 1.0 if summary.count > 0 else 0.0,
        "policy_adherence": 1.0,
        "context_efficiency": (
            max(0.0, 1.0 - min((summary.tokens_total or 0) / (summary.count * ASSUMED_MAX_TOKENS), 1.0))
            if summary.count
            else 0.0
        ),
        "recovery_behavior": (max(0.0, 1.0 - summary.failed_count / summary.count) if summary.count else 0.0),
    }


__all__ = [
    "ASSUMED_MAX_TOKENS",
    "WEIGHTS",
    "compute_composite",
    "explain_composite",
]
