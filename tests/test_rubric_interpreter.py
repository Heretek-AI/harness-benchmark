"""Tests for the chained rubric interpreter."""

from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.rubric_interpreter import (
    Criterion,
    CriterionCheck,
    Rubric,
    RubricInterpreter,
    RubricResult,
    load_rubric,
)


def _simple_rubric() -> Rubric:
    return Rubric(
        criteria=[
            Criterion(
                id="a",
                description="File exists",
                check=CriterionCheck(type="file_exists", path="output.txt"),
            ),
            Criterion(
                id="b",
                description="File contains hello",
                check=CriterionCheck(type="file_contains", path="output.txt", pattern="hello"),
                depends_on=["a"],
            ),
            Criterion(
                id="c",
                description="No errors in stdout",
                check=CriterionCheck(type="not_contains", text="ERROR"),
                depends_on=["b"],
            ),
        ],
        weights={"a": 1.0, "b": 2.0, "c": 1.0},
    )


def test_all_pass(tmp_path: Path) -> None:
    (tmp_path / "output.txt").write_text("hello world")
    interp = RubricInterpreter(_simple_rubric())
    result = interp.evaluate(workspace_dir=tmp_path, stdout="all good")
    assert result.passed is True
    assert result.score == 4.0
    assert result.max_score == 4.0
    assert result.score_pct == 100.0


def test_first_fails_skips_downstream(tmp_path: Path) -> None:
    # output.txt does NOT exist → criterion a fails → b and c skipped
    interp = RubricInterpreter(_simple_rubric())
    result = interp.evaluate(workspace_dir=tmp_path, stdout="all good")
    assert result.passed is False
    assert result.score == 0.0
    # Check that b and c were skipped
    by_id = {r.criterion_id: r for r in result.criterion_results}
    assert by_id["a"].passed is False
    assert by_id["b"].skipped is True
    assert by_id["c"].skipped is True


def test_middle_fails_skips_downstream(tmp_path: Path) -> None:
    (tmp_path / "output.txt").write_text("goodbye world")  # no "hello"
    interp = RubricInterpreter(_simple_rubric())
    result = interp.evaluate(workspace_dir=tmp_path, stdout="all good")
    assert result.passed is False
    by_id = {r.criterion_id: r for r in result.criterion_results}
    assert by_id["a"].passed is True  # file exists
    assert by_id["b"].passed is False  # no "hello"
    assert by_id["c"].skipped is True  # skipped because b failed
    assert result.score == 1.0  # only a's weight


def test_stdout_check(tmp_path: Path) -> None:
    (tmp_path / "output.txt").write_text("hello world")
    interp = RubricInterpreter(_simple_rubric())
    result = interp.evaluate(workspace_dir=tmp_path, stdout="ERROR: something broke")
    by_id = {r.criterion_id: r for r in result.criterion_results}
    assert by_id["a"].passed is True
    assert by_id["b"].passed is True
    assert by_id["c"].passed is False  # stdout contains ERROR


def test_shell_command_pass(tmp_path: Path) -> None:
    rubric = Rubric(
        criteria=[
            Criterion(
                id="shell",
                description="Shell check",
                check=CriterionCheck(type="shell_command", command="test -f output.txt"),
            ),
        ],
    )
    (tmp_path / "output.txt").write_text("data")
    interp = RubricInterpreter(rubric)
    result = interp.evaluate(workspace_dir=tmp_path)
    assert result.passed is True


def test_shell_command_fail(tmp_path: Path) -> None:
    rubric = Rubric(
        criteria=[
            Criterion(
                id="shell",
                description="Shell check",
                check=CriterionCheck(type="shell_command", command="test -f nonexistent.txt"),
            ),
        ],
    )
    interp = RubricInterpreter(rubric)
    result = interp.evaluate(workspace_dir=tmp_path)
    assert result.passed is False


def test_min_lines(tmp_path: Path) -> None:
    rubric = Rubric(
        criteria=[
            Criterion(
                id="lines",
                description="Enough lines",
                check=CriterionCheck(type="min_lines", path="code.py", min_lines=5),
            ),
        ],
    )
    (tmp_path / "code.py").write_text("line1\nline2\nline3\nline4\nline5\n")
    interp = RubricInterpreter(rubric)
    result = interp.evaluate(workspace_dir=tmp_path)
    assert result.passed is True

    (tmp_path / "code.py").write_text("short")
    result = interp.evaluate(workspace_dir=tmp_path)
    assert result.passed is False


def test_load_rubric_from_yaml(tmp_path: Path) -> None:
    yaml_content = """
criteria:
  - id: check_a
    description: "First check"
    check:
      type: file_exists
      path: "out.txt"
  - id: check_b
    description: "Second check"
    check:
      type: file_contains
      path: "out.txt"
      pattern: "data"
    depends_on: [check_a]
weights:
  check_a: 1.0
  check_b: 3.0
"""
    rubric_path = tmp_path / "rubric.yaml"
    rubric_path.write_text(yaml_content)
    rubric = load_rubric(rubric_path)
    assert len(rubric.criteria) == 2
    assert rubric.criteria[0].id == "check_a"
    assert rubric.criteria[1].depends_on == ["check_a"]
    assert rubric.weights["check_b"] == 3.0


def test_empty_rubric() -> None:
    rubric = Rubric(criteria=[])
    interp = RubricInterpreter(rubric)
    result = interp.evaluate()
    assert result.passed is True
    assert result.score == 0.0
    assert result.max_score == 0.0


def test_no_weights_default_to_one() -> None:
    rubric = Rubric(
        criteria=[
            Criterion(id="x", description="", check=CriterionCheck(type="not_contains", text="ERR")),
            Criterion(id="y", description="", check=CriterionCheck(type="not_contains", text="ERR")),
        ],
    )
    interp = RubricInterpreter(rubric)
    result = interp.evaluate(stdout="clean output")
    assert result.score == 2.0
    assert result.max_score == 2.0
