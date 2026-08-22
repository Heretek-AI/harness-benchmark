"""Tests for the deterministic constraint checker."""

from __future__ import annotations

from evaluation.constraint_checker import ConstraintChecker


def test_empty_constraints_pass() -> None:
    checker = ConstraintChecker({})
    result = checker.check("anything")
    assert result.passed is True


def test_regex_match() -> None:
    checker = ConstraintChecker({"regex": r"^# Heading"})
    assert checker.check("# Heading\nSome content").passed is True
    assert checker.check("No heading here").passed is False


def test_not_regex() -> None:
    checker = ConstraintChecker({"not_regex": r"TODO|FIXME"})
    assert checker.check("Clean code").passed is True
    assert checker.check("Has a TODO here").passed is False


def test_contains() -> None:
    checker = ConstraintChecker({"contains": "hello"})
    assert checker.check("say hello world").passed is True
    assert checker.check("say goodbye").passed is False


def test_not_contains() -> None:
    checker = ConstraintChecker({"not_contains": "password"})
    assert checker.check("safe output").passed is True
    assert checker.check("password=secret").passed is False


def test_word_count_min() -> None:
    checker = ConstraintChecker({"word_count_min": 5})
    assert checker.check("one two three four five").passed is True
    assert checker.check("one two").passed is False


def test_word_count_max() -> None:
    checker = ConstraintChecker({"word_count_max": 3})
    assert checker.check("one two three").passed is True
    assert checker.check("one two three four").passed is False


def test_line_count_min() -> None:
    checker = ConstraintChecker({"line_count_min": 3})
    assert checker.check("a\nb\nc").passed is True
    assert checker.check("a\nb").passed is False


def test_line_count_max() -> None:
    checker = ConstraintChecker({"line_count_max": 2})
    assert checker.check("a\nb").passed is True
    assert checker.check("a\nb\nc").passed is False


def test_exact_match() -> None:
    checker = ConstraintChecker({"exact_match": "Hello, World!"})
    assert checker.check("Hello, World!").passed is True
    assert checker.check("Hello, World! ").passed is True  # trailing space stripped
    assert checker.check("Different").passed is False
    assert checker.check("Hello, World!!").passed is False


def test_starts_with() -> None:
    checker = ConstraintChecker({"starts_with": "# "})
    assert checker.check("# Title").passed is True
    assert checker.check("Title").passed is False


def test_ends_with() -> None:
    checker = ConstraintChecker({"ends_with": "."})
    assert checker.check("Ends with period.").passed is True
    assert checker.check("No period").passed is False


def test_forbidden_tokens() -> None:
    checker = ConstraintChecker({"forbidden_tokens": ["TODO", "FIXME", "HACK"]})
    assert checker.check("Clean code").passed is True
    assert checker.check("Has a TODO").passed is False
    assert checker.check("Has a FIXME").passed is False


def test_required_tokens() -> None:
    checker = ConstraintChecker({"required_tokens": ["import", "def"]})
    assert checker.check("import os\ndef main():").passed is True
    assert checker.check("import os").passed is False  # missing def


def test_multiple_constraints() -> None:
    checker = ConstraintChecker({
        "word_count_min": 3,
        "word_count_max": 10,
        "not_contains": "error",
        "starts_with": "Result:",
    })
    assert checker.check("Result: all good").passed is True
    assert checker.check("Result: error found").passed is False  # contains error
    assert checker.check("No prefix").passed is False  # doesn't start with Result:
    assert checker.check("Result: one").passed is False  # too few words


def test_violation_details() -> None:
    checker = ConstraintChecker({"contains": "expected"})
    result = checker.check("actual output")
    assert result.passed is False
    assert len(result.violations) == 1
    assert result.violations[0].constraint_type == "contains"
    assert "expected" in str(result.violations[0])
