"""File-change diff evaluator for workspace state comparison.

Compares the workspace state after agent execution against expected
file changes to evaluate whether the agent modified the right files
with the right content.

Usage::

    from evaluation.diff_evaluator import DiffEvaluator, ExpectedChange

    evaluator = DiffEvaluator()
    changes = evaluator.capture_diff(workspace_path)
    result = evaluator.evaluate(changes, expected=[ExpectedChange(path="app.py", contains="def main")])
"""

from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FileChange:
    """Record of a file change in the workspace."""

    path: str
    action: str  # "created", "modified", "deleted", "unchanged"
    old_content: str = ""
    new_content: str = ""
    old_lines: int = 0
    new_lines: int = 0

    @property
    def diff(self) -> str:
        """Unified diff between old and new content."""
        if self.action == "unchanged":
            return ""
        old_lines = self.old_content.splitlines(keepends=True)
        new_lines = self.new_content.splitlines(keepends=True)
        return "".join(difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{self.path}",
            tofile=f"b/{self.path}",
        ))


@dataclass
class ExpectedChange:
    """An expected file change specification."""

    path: str
    action: str | None = None  # "created", "modified", "deleted", or None (any)
    contains: str | None = None  # content must contain this string
    not_contains: str | None = None  # content must NOT contain this string
    min_lines: int | None = None
    max_lines: int | None = None
    regex: str | None = None  # content must match this regex


@dataclass
class DiffEvalResult:
    """Result of evaluating workspace diff against expectations."""

    score: float  # 0.0 to 1.0
    total_expected: int
    matched: int
    mismatched: int
    unexpected_changes: list[str]
    details: list[dict[str, Any]] = field(default_factory=list)
    rationale: str = ""

    @property
    def passed(self) -> bool:
        return self.score >= 0.5


class DiffEvaluator:
    """Evaluate workspace file changes against expected specifications."""

    def score(self, actual_changes: list[FileChange], expected: list[ExpectedChange]) -> DiffEvalResult:
        """Score actual changes against expected changes."""
        matched = 0
        mismatched = 0
        details = []

        for exp in expected:
            # Find matching actual change
            actual = None
            for ac in actual_changes:
                if ac.path == exp.path:
                    actual = ac
                    break

            detail: dict[str, Any] = {"path": exp.path, "checks": []}

            if actual is None:
                mismatched += 1
                detail["status"] = "missing"
                detail["checks"].append({"check": "file_exists", "passed": False})
                details.append(detail)
                continue

            checks_passed = 0
            checks_total = 0

            # Action check
            if exp.action:
                checks_total += 1
                action_ok = actual.action == exp.action
                if action_ok:
                    checks_passed += 1
                detail["checks"].append({
                    "check": "action",
                    "expected": exp.action,
                    "actual": actual.action,
                    "passed": action_ok,
                })

            # Contains check
            if exp.contains:
                checks_total += 1
                contains_ok = exp.contains in actual.new_content
                if contains_ok:
                    checks_passed += 1
                detail["checks"].append({
                    "check": "contains",
                    "expected": exp.contains,
                    "passed": contains_ok,
                })

            # Not-contains check
            if exp.not_contains:
                checks_total += 1
                not_contains_ok = exp.not_contains not in actual.new_content
                if not_contains_ok:
                    checks_passed += 1
                detail["checks"].append({
                    "check": "not_contains",
                    "forbidden": exp.not_contains,
                    "passed": not_contains_ok,
                })

            # Line count checks
            if exp.min_lines is not None:
                checks_total += 1
                lines_ok = actual.new_lines >= exp.min_lines
                if lines_ok:
                    checks_passed += 1
                detail["checks"].append({
                    "check": "min_lines",
                    "expected": exp.min_lines,
                    "actual": actual.new_lines,
                    "passed": lines_ok,
                })

            if exp.max_lines is not None:
                checks_total += 1
                lines_ok = actual.new_lines <= exp.max_lines
                if lines_ok:
                    checks_passed += 1
                detail["checks"].append({
                    "check": "max_lines",
                    "expected": exp.max_lines,
                    "actual": actual.new_lines,
                    "passed": lines_ok,
                })

            # Regex check
            if exp.regex:
                checks_total += 1
                import re
                regex_ok = bool(re.search(exp.regex, actual.new_content))
                if regex_ok:
                    checks_passed += 1
                detail["checks"].append({
                    "check": "regex",
                    "pattern": exp.regex,
                    "passed": regex_ok,
                })

            if checks_total == 0:
                # No specific checks, just file existence
                checks_total = 1
                checks_passed = 1

            if checks_passed == checks_total:
                matched += 1
                detail["status"] = "matched"
            else:
                mismatched += 1
                detail["status"] = "mismatched"

            details.append(detail)

        # Unexpected changes (files changed that weren't expected)
        expected_paths = {e.path for e in expected}
        unexpected = [ac.path for ac in actual_changes if ac.path not in expected_paths]

        total = len(expected)
        score = matched / total if total > 0 else (1.0 if not unexpected else 0.5)

        # Deduct for unexpected changes
        if unexpected and total > 0:
            penalty = min(0.3, len(unexpected) * 0.1)
            score = max(0.0, score - penalty)

        parts = []
        if mismatched:
            parts.append(f"{mismatched}/{total} expected changes didn't match")
        if unexpected:
            parts.append(f"{len(unexpected)} unexpected file changes")
        if not parts:
            parts.append("all expected changes matched")

        return DiffEvalResult(
            score=score,
            total_expected=total,
            matched=matched,
            mismatched=mismatched,
            unexpected_changes=unexpected,
            details=details,
            rationale="; ".join(parts),
        )

    def capture_diff(self, workspace: Path, baseline: dict[str, str] | None = None) -> list[FileChange]:
        """Capture file changes in a workspace directory.

        Args:
            workspace: Path to the workspace directory.
            baseline: Optional dict of {path: content} representing the
                original state. If None, treats all existing files as new.
        """
        changes: list[FileChange] = []
        baseline = baseline or {}

        if not workspace.exists():
            return changes

        for f in sorted(workspace.rglob("*")):
            if f.is_dir():
                continue
            rel = str(f.relative_to(workspace))

            try:
                content = f.read_text(errors="replace")
            except Exception:
                continue

            new_lines = len(content.splitlines())

            if rel in baseline:
                old_content = baseline[rel]
                old_lines = len(old_content.splitlines())
                if content == old_content:
                    action = "unchanged"
                else:
                    action = "modified"
            else:
                old_content = ""
                old_lines = 0
                action = "created"

            changes.append(FileChange(
                path=rel,
                action=action,
                old_content=old_content,
                new_content=content,
                old_lines=old_lines,
                new_lines=new_lines,
            ))

        # Check for deleted files
        for rel in baseline:
            full = workspace / rel
            if not full.exists():
                changes.append(FileChange(
                    path=rel,
                    action="deleted",
                    old_content=baseline[rel],
                    new_content="",
                    old_lines=len(baseline[rel].splitlines()),
                    new_lines=0,
                ))

        return changes
