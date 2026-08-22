"""Tool-use scorer for evaluating agent tool selection and sequencing.

Analyzes tool call logs to score whether an agent used the right tools
in the right order for a given task.

Usage::

    from evaluation.tool_scorer import ToolUseScorer, ToolCall

    scorer = ToolUseScorer()
    calls = [ToolCall(name="bash", args={"command": "ls"}, turn=1)]
    result = scorer.score(calls, expected_tools=["bash"], required_sequence=["bash"])
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """Record of a single tool invocation by the agent."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)
    turn: int = 0
    duration_ms: float = 0.0
    success: bool = True


@dataclass
class ToolUseResult:
    """Result of scoring tool usage for a single task."""

    score: float  # 0.0 to 1.0
    tools_used: list[str]
    tools_expected: list[str]
    tools_missed: list[str]
    tools_extra: list[str]
    sequence_correct: bool
    total_calls: int
    unique_tools: int
    rationale: str = ""

    @property
    def passed(self) -> bool:
        return self.score >= 0.5


class ToolUseScorer:
    """Score agent tool usage against expectations.

    Scoring dimensions:
    1. Tool coverage: Did the agent use all expected tools? (0.4 weight)
    2. No extra tools: Did the agent avoid unnecessary tools? (0.2 weight)
    3. Sequence correctness: Were tools called in the right order? (0.4 weight)
    """

    def __init__(
        self,
        coverage_weight: float = 0.4,
        extra_penalty: float = 0.2,
        sequence_weight: float = 0.4,
    ) -> None:
        self.coverage_weight = coverage_weight
        self.extra_penalty = extra_penalty
        self.sequence_weight = sequence_weight

    def score(
        self,
        actual_calls: list[ToolCall],
        expected_tools: list[str] | None = None,
        required_sequence: list[str] | None = None,
        forbidden_tools: list[str] | None = None,
    ) -> ToolUseResult:
        """Score a sequence of tool calls.

        Args:
            actual_calls: Tools actually invoked by the agent.
            expected_tools: Tools that should have been used (for coverage).
            required_sequence: Tools that must appear in this relative order.
            forbidden_tools: Tools that should NOT have been used.
        """
        tools_used = [c.name for c in actual_calls]
        unique_tools = list(dict.fromkeys(tools_used))  # preserve order, dedup

        # Coverage score
        expected = expected_tools or []
        if expected:
            used_set = set(tools_used)
            covered = [t for t in expected if t in used_set]
            coverage_score = len(covered) / len(expected) if expected else 1.0
            tools_missed = [t for t in expected if t not in used_set]
        else:
            coverage_score = 1.0 if tools_used else 0.5
            tools_missed = []

        # Extra tools penalty
        forbidden = set(forbidden_tools or [])
        extra = [t for t in unique_tools if t not in expected and t not in forbidden]
        if expected:
            extra_ratio = len(extra) / len(expected) if expected else 0
            extra_score = max(0.0, 1.0 - extra_ratio)
        else:
            extra_score = 1.0

        # Sequence correctness
        if required_sequence and len(required_sequence) > 1:
            # Check if required tools appear in relative order
            seq_idx = []
            for req in required_sequence:
                for i, call in enumerate(actual_calls):
                    if call.name == req:
                        seq_idx.append(i)
                        break
                else:
                    seq_idx.append(-1)

            # All required tools must be found
            if -1 in seq_idx:
                sequence_correct = False
                sequence_score = 0.0
            else:
                sequence_correct = all(
                    seq_idx[i] < seq_idx[i + 1]
                    for i in range(len(seq_idx) - 1)
                )
                sequence_score = 1.0 if sequence_correct else 0.5
        else:
            sequence_correct = True
            sequence_score = 1.0

        # Forbidden tools
        forbidden_used = [t for t in tools_used if t in forbidden]
        if forbidden_used:
            coverage_score *= 0.5  # heavy penalty for using forbidden tools

        # Weighted final score
        score = (
            self.coverage_weight * coverage_score
            + self.extra_penalty * extra_score
            + self.sequence_weight * sequence_score
        )
        score = max(0.0, min(1.0, score))

        # Rationale
        parts = []
        if tools_missed:
            parts.append(f"missed tools: {', '.join(tools_missed)}")
        if extra:
            parts.append(f"extra tools: {', '.join(extra)}")
        if forbidden_used:
            parts.append(f"forbidden tools used: {', '.join(forbidden_used)}")
        if not sequence_correct:
            parts.append("tool sequence incorrect")
        if not parts:
            parts.append("all tool usage criteria met")

        return ToolUseResult(
            score=score,
            tools_used=tools_used,
            tools_expected=expected,
            tools_missed=tools_missed,
            tools_extra=extra,
            sequence_correct=sequence_correct,
            total_calls=len(actual_calls),
            unique_tools=len(unique_tools),
            rationale="; ".join(parts),
        )
