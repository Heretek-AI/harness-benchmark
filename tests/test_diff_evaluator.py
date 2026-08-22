"""Tests for file-change diff evaluator."""

from __future__ import annotations

from pathlib import Path

from evaluation.diff_evaluator import DiffEvaluator, ExpectedChange, FileChange


def test_perfect_match() -> None:
    evaluator = DiffEvaluator()
    changes = [
        FileChange(path="app.py", action="created", new_content="def main():\n    pass\n", new_lines=2),
    ]
    expected = [ExpectedChange(path="app.py", action="created")]
    result = evaluator.score(changes, expected)
    assert result.score == 1.0
    assert result.passed
    assert result.matched == 1


def test_contains_check() -> None:
    evaluator = DiffEvaluator()
    changes = [
        FileChange(path="app.py", action="created", new_content="def main():\n    print('hello')\n", new_lines=2),
    ]
    expected = [ExpectedChange(path="app.py", contains="def main")]
    result = evaluator.score(changes, expected)
    assert result.score == 1.0


def test_not_contains_check() -> None:
    evaluator = DiffEvaluator()
    changes = [
        FileChange(path="app.py", action="created", new_content="def main():\n    pass\n", new_lines=2),
    ]
    expected = [ExpectedChange(path="app.py", not_contains="import os")]
    result = evaluator.score(changes, expected)
    assert result.score == 1.0


def test_missing_file() -> None:
    evaluator = DiffEvaluator()
    changes = []
    expected = [ExpectedChange(path="app.py", action="created")]
    result = evaluator.score(changes, expected)
    assert result.score == 0.0
    assert not result.passed
    assert result.mismatched == 1


def test_wrong_action() -> None:
    evaluator = DiffEvaluator()
    changes = [
        FileChange(path="app.py", action="modified", new_content="x", new_lines=1),
    ]
    expected = [ExpectedChange(path="app.py", action="created")]
    result = evaluator.score(changes, expected)
    assert result.mismatched == 1


def test_unexpected_changes_penalty() -> None:
    evaluator = DiffEvaluator()
    changes = [
        FileChange(path="app.py", action="created", new_content="x", new_lines=1),
        FileChange(path="extra.py", action="created", new_content="y", new_lines=1),
    ]
    expected = [ExpectedChange(path="app.py", action="created")]
    result = evaluator.score(changes, expected)
    assert "extra.py" in result.unexpected_changes
    assert result.score < 1.0


def test_line_count_min() -> None:
    evaluator = DiffEvaluator()
    changes = [
        FileChange(path="app.py", action="created", new_content="a\nb\nc\n", new_lines=3),
    ]
    expected = [ExpectedChange(path="app.py", min_lines=2)]
    result = evaluator.score(changes, expected)
    assert result.score == 1.0


def test_line_count_max() -> None:
    evaluator = DiffEvaluator()
    changes = [
        FileChange(path="app.py", action="created", new_content="a\nb\nc\n", new_lines=3),
    ]
    expected = [ExpectedChange(path="app.py", max_lines=2)]
    result = evaluator.score(changes, expected)
    assert result.mismatched == 1


def test_capture_diff_new_files(tmp_path: Path) -> None:
    (tmp_path / "hello.py").write_text("print('hello')\n")
    evaluator = DiffEvaluator()
    changes = evaluator.capture_diff(tmp_path)
    assert len(changes) == 1
    assert changes[0].path == "hello.py"
    assert changes[0].action == "created"


def test_capture_diff_modified(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("v1")
    evaluator = DiffEvaluator()
    baseline = {"app.py": "v1"}
    (tmp_path / "app.py").write_text("v2")
    changes = evaluator.capture_diff(tmp_path, baseline=baseline)
    modified = [c for c in changes if c.path == "app.py"]
    assert len(modified) == 1
    assert modified[0].action == "modified"
