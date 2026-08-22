"""Chained Rubric Interpreter for DAG-based task evaluation.

Implements a directed acyclic graph (DAG) of criteria where failure at
node C_i automatically zero-scores all downstream dependents C_{i+k}.

Rubric YAML format::

    criteria:
      - id: file_created
        description: "Output file exists"
        check:
          type: file_exists
          path: "output.txt"

      - id: content_valid
        description: "File contains expected content"
        check:
          type: file_contains
          path: "output.txt"
          pattern: "Hello"
        depends_on: [file_created]

      - id: no_errors
        description: "No error messages in output"
        check:
          type: not_contains
          text: "ERROR"
        depends_on: [content_valid]

    weights:
      file_created: 1.0
      content_valid: 2.0
      no_errors: 1.0

Usage::

    from evaluation.rubric_interpreter import RubricInterpreter, load_rubric

    rubric = load_rubric(Path("tasks/my-task/rubric.yaml"))
    interp = RubricInterpreter(rubric)
    result = interp.evaluate(workspace_dir=Path("/tmp/run-123"), stdout="...")
    print(result.score, result.max_score, result.passed)
"""

from __future__ import annotations

import logging
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CriterionCheck:
    """A single check to perform."""

    type: str  # file_exists, file_contains, not_contains, shell_command, stdout_contains, min_lines
    # Fields vary by type
    path: str | None = None
    pattern: str | None = None
    text: str | None = None
    command: str | None = None
    min_lines: int | None = None


@dataclass
class Criterion:
    """A single rubric criterion (node in the DAG)."""

    id: str
    description: str
    check: CriterionCheck
    depends_on: list[str] = field(default_factory=list)


@dataclass
class Rubric:
    """A complete rubric definition."""

    criteria: list[Criterion]
    weights: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Default weight of 1.0 for criteria without explicit weights
        for c in self.criteria:
            if c.id not in self.weights:
                self.weights[c.id] = 1.0


@dataclass
class CriterionResult:
    """Result of evaluating a single criterion."""

    criterion_id: str
    passed: bool
    message: str = ""
    skipped: bool = False  # True when upstream dependency failed


@dataclass
class RubricResult:
    """Result of evaluating a complete rubric."""

    criterion_results: list[CriterionResult]
    score: float
    max_score: float
    passed: bool  # True if all criteria passed

    @property
    def score_pct(self) -> float:
        return (self.score / self.max_score * 100) if self.max_score > 0 else 0.0


def load_rubric(path: Path) -> Rubric:
    """Load a rubric from a YAML file."""
    data = yaml.safe_load(path.read_text())
    criteria = []
    for c in data.get("criteria", []):
        check_data = c.get("check", {})
        check = CriterionCheck(
            type=check_data.get("type", "shell_command"),
            path=check_data.get("path"),
            pattern=check_data.get("pattern"),
            text=check_data.get("text"),
            command=check_data.get("command"),
            min_lines=check_data.get("min_lines"),
        )
        criteria.append(Criterion(
            id=c["id"],
            description=c.get("description", ""),
            check=check,
            depends_on=c.get("depends_on", []),
        ))
    weights = data.get("weights", {})
    return Rubric(criteria=criteria, weights=weights)


class RubricInterpreter:
    """Evaluate a rubric against a workspace and stdout."""

    def __init__(self, rubric: Rubric) -> None:
        self.rubric = rubric
        # Build adjacency: criterion_id -> list of dependents
        self._dependents: dict[str, list[str]] = defaultdict(list)
        self._by_id: dict[str, Criterion] = {}
        for c in rubric.criteria:
            self._by_id[c.id] = c
            for dep in c.depends_on:
                self._dependents[dep].append(c.id)

    def evaluate(
        self,
        workspace_dir: Path | None = None,
        stdout: str = "",
    ) -> RubricResult:
        """Evaluate all criteria in dependency order.

        Criteria whose dependencies failed are automatically skipped (scored as 0).
        """
        results: dict[str, CriterionResult] = {}
        failed_ids: set[str] = set()

        # Topological evaluation: process in order, respecting dependencies
        for criterion in self._topo_sort():
            # Check if any dependency failed
            if any(dep in failed_ids for dep in criterion.depends_on):
                results[criterion.id] = CriterionResult(
                    criterion_id=criterion.id,
                    passed=False,
                    message="Skipped: upstream dependency failed",
                    skipped=True,
                )
                failed_ids.add(criterion.id)
                continue

            # Evaluate the check
            passed, message = self._eval_check(criterion.check, workspace_dir, stdout)
            results[criterion.id] = CriterionResult(
                criterion_id=criterion.id,
                passed=passed,
                message=message,
            )
            if not passed:
                failed_ids.add(criterion.id)

        # Calculate weighted score
        score = 0.0
        max_score = 0.0
        all_passed = True
        for c in self.rubric.criteria:
            w = self.rubric.weights.get(c.id, 1.0)
            max_score += w
            r = results.get(c.id)
            if r and r.passed:
                score += w
            elif r and r.skipped:
                all_passed = False
            elif r:
                all_passed = False

        return RubricResult(
            criterion_results=list(results.values()),
            score=score,
            max_score=max_score,
            passed=all_passed,
        )

    def _eval_check(
        self,
        check: CriterionCheck,
        workspace_dir: Path | None,
        stdout: str,
    ) -> tuple[bool, str]:
        """Evaluate a single check and return (passed, message)."""
        if check.type == "file_exists":
            if workspace_dir is None:
                return False, "No workspace directory"
            fp = workspace_dir / check.path
            if fp.exists():
                return True, f"File exists: {check.path}"
            return False, f"File missing: {check.path}"

        if check.type == "file_contains":
            if workspace_dir is None:
                return False, "No workspace directory"
            fp = workspace_dir / check.path
            if not fp.exists():
                return False, f"File missing: {check.path}"
            content = fp.read_text(errors="replace")
            if check.pattern and check.pattern in content:
                return True, f"File contains: {check.pattern!r}"
            return False, f"File does not contain: {check.pattern!r}"

        if check.type == "not_contains":
            if check.text and check.text in stdout:
                return False, f"Stdout contains forbidden: {check.text!r}"
            return True, "Stdout clean"

        if check.type == "stdout_contains":
            if check.pattern and check.pattern in stdout:
                return True, f"Stdout contains: {check.pattern!r}"
            return False, f"Stdout missing: {check.pattern!r}"

        if check.type == "shell_command":
            if not check.command:
                return False, "No command specified"
            if workspace_dir is None:
                return False, "No workspace directory"
            try:
                proc = subprocess.run(
                    ["bash", "-c", check.command],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    cwd=workspace_dir,
                )
                if proc.returncode == 0:
                    return True, f"Command succeeded: {check.command}"
                return False, f"Command failed (rc={proc.returncode}): {proc.stderr[:200]}"
            except subprocess.TimeoutExpired:
                return False, f"Command timed out: {check.command}"
            except Exception as e:
                return False, f"Command error: {e}"

        if check.type == "min_lines":
            if workspace_dir is None:
                return False, "No workspace directory"
            if not check.path:
                return False, "No path specified"
            fp = workspace_dir / check.path
            if not fp.exists():
                return False, f"File missing: {check.path}"
            lines = len(fp.read_text(errors="replace").splitlines())
            if check.min_lines is not None and lines >= check.min_lines:
                return True, f"Line count {lines} >= {check.min_lines}"
            return False, f"Line count {lines} < {check.min_lines}"

        return False, f"Unknown check type: {check.type}"

    def _topo_sort(self) -> list[Criterion]:
        """Return criteria in topological order (dependencies first)."""
        visited: set[str] = set()
        order: list[Criterion] = []

        def visit(c_id: str) -> None:
            if c_id in visited:
                return
            visited.add(c_id)
            c = self._by_id.get(c_id)
            if c is None:
                return
            for dep in c.depends_on:
                visit(dep)
            order.append(c)

        for c in self.rubric.criteria:
            visit(c.id)

        return order
