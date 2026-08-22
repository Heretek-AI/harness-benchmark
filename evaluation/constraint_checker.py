"""Deterministic constraint checker for IFBench-style tasks.

Evaluates agent output against structural and lexical constraints without
calling an LLM.  Constraints are specified as a dictionary and checked
against the raw stdout of the agent.

Supported constraint types:
    regex           — output must match the given regex pattern
    not_regex       — output must NOT match the given regex pattern
    contains        — output must contain the given substring
    not_contains    — output must NOT contain the given substring
    word_count_min  — minimum word count
    word_count_max  — maximum word count
    line_count_min  — minimum line count
    line_count_max  — maximum line count
    exact_match     — output must exactly equal the given string (stripped)
    starts_with     — output must start with the given prefix
    ends_with       — output must end with the given suffix
    forbidden_tokens — list of tokens that must not appear in output
    required_tokens  — list of tokens that must all appear in output

Usage::

    from evaluation.constraint_checker import ConstraintChecker

    checker = ConstraintChecker({
        "word_count_min": 10,
        "word_count_max": 200,
        "forbidden_tokens": ["TODO", "FIXME"],
        "regex": r"^# .+",
    })
    passed, violations = checker.check("Some output text")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConstraintViolation:
    """A single constraint that was not satisfied."""

    constraint_type: str
    expected: str
    actual: str | None = None

    def __str__(self) -> str:
        msg = f"{self.constraint_type}: expected {self.expected}"
        if self.actual:
            msg += f", got {self.actual}"
        return msg


@dataclass
class ConstraintCheckResult:
    """Result of checking a set of constraints."""

    passed: bool
    violations: list[ConstraintViolation] = field(default_factory=list)

    def __str__(self) -> str:
        if self.passed:
            return "All constraints passed"
        return f"{len(self.violations)} constraint(s) failed: " + "; ".join(
            str(v) for v in self.violations
        )


class ConstraintChecker:
    """Evaluate text output against a set of deterministic constraints."""

    def __init__(self, constraints: dict) -> None:
        """
        Args:
            constraints: Dictionary of constraint_type -> expected value.
        """
        self.constraints = constraints

    def check(self, output: str) -> ConstraintCheckResult:
        """Check output against all constraints.

        Args:
            output: The agent's raw stdout text.

        Returns:
            ConstraintCheckResult with passed=True if all constraints satisfied.
        """
        violations: list[ConstraintViolation] = []
        stripped = output.strip()

        # regex
        if "regex" in self.constraints:
            pattern = self.constraints["regex"]
            if not re.search(pattern, output, re.MULTILINE):
                violations.append(
                    ConstraintViolation("regex", f"match /{pattern}/", "no match")
                )

        # not_regex
        if "not_regex" in self.constraints:
            pattern = self.constraints["not_regex"]
            if re.search(pattern, output, re.MULTILINE):
                violations.append(
                    ConstraintViolation("not_regex", f"not match /{pattern}/", "matched")
                )

        # contains
        if "contains" in self.constraints:
            target = self.constraints["contains"]
            if target not in output:
                violations.append(
                    ConstraintViolation("contains", f"contain {target!r}", "not found")
                )

        # not_contains
        if "not_contains" in self.constraints:
            target = self.constraints["not_contains"]
            if target in output:
                violations.append(
                    ConstraintViolation("not_contains", f"not contain {target!r}", "found")
                )

        # word_count_min / max
        words = output.split()
        word_count = len(words)
        if "word_count_min" in self.constraints:
            minimum = self.constraints["word_count_min"]
            if word_count < minimum:
                violations.append(
                    ConstraintViolation("word_count_min", f">= {minimum}", str(word_count))
                )
        if "word_count_max" in self.constraints:
            maximum = self.constraints["word_count_max"]
            if word_count > maximum:
                violations.append(
                    ConstraintViolation("word_count_max", f"<= {maximum}", str(word_count))
                )

        # line_count_min / max
        lines = output.splitlines()
        line_count = len(lines)
        if "line_count_min" in self.constraints:
            minimum = self.constraints["line_count_min"]
            if line_count < minimum:
                violations.append(
                    ConstraintViolation("line_count_min", f">= {minimum}", str(line_count))
                )
        if "line_count_max" in self.constraints:
            maximum = self.constraints["line_count_max"]
            if line_count > maximum:
                violations.append(
                    ConstraintViolation("line_count_max", f"<= {maximum}", str(line_count))
                )

        # exact_match
        if "exact_match" in self.constraints:
            expected = self.constraints["exact_match"]
            if stripped != expected:
                violations.append(
                    ConstraintViolation("exact_match", repr(expected), repr(stripped[:100]))
                )

        # starts_with
        if "starts_with" in self.constraints:
            prefix = self.constraints["starts_with"]
            if not stripped.startswith(prefix):
                violations.append(
                    ConstraintViolation("starts_with", f"start with {prefix!r}", repr(stripped[:100]))
                )

        # ends_with
        if "ends_with" in self.constraints:
            suffix = self.constraints["ends_with"]
            if not stripped.endswith(suffix):
                violations.append(
                    ConstraintViolation("ends_with", f"end with {suffix!r}", repr(stripped[-100:]))
                )

        # forbidden_tokens
        if "forbidden_tokens" in self.constraints:
            for token in self.constraints["forbidden_tokens"]:
                if token in output:
                    violations.append(
                        ConstraintViolation("forbidden_tokens", f"not contain {token!r}", "found")
                    )

        # required_tokens
        if "required_tokens" in self.constraints:
            for token in self.constraints["required_tokens"]:
                if token not in output:
                    violations.append(
                        ConstraintViolation("required_tokens", f"contain {token!r}", "not found")
                    )

        return ConstraintCheckResult(
            passed=len(violations) == 0,
            violations=violations,
        )
