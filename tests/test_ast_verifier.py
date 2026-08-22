"""Tests for the AST verification pipeline."""

from __future__ import annotations

from pathlib import Path

from evaluation.ast_verifier import ASTVerifier, VerificationResult, VerificationSpec


def test_valid_python_file(tmp_path: Path) -> None:
    (tmp_path / "solution.py").write_text(
        "import os\n\ndef sort_list(items):\n    return sorted(items)\n"
    )
    spec = VerificationSpec(
        must_compile=True,
        required_functions=["sort_list"],
        required_imports=["os"],
    )
    result = ASTVerifier(spec).verify(tmp_path)
    assert result.passed is True
    assert "sort_list" in result.functions_found
    assert "os" in result.imports_found


def test_syntax_error(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("def f(\n")
    spec = VerificationSpec(must_compile=True)
    result = ASTVerifier(spec).verify(tmp_path)
    assert result.passed is False
    assert any("Syntax error" in v for v in result.violations)


def test_missing_function(tmp_path: Path) -> None:
    (tmp_path / "solution.py").write_text("def other(): pass\n")
    spec = VerificationSpec(required_functions=["sort_list"])
    result = ASTVerifier(spec).verify(tmp_path)
    assert result.passed is False
    assert any("sort_list" in v for v in result.violations)


def test_missing_class(tmp_path: Path) -> None:
    (tmp_path / "solution.py").write_text("def f(): pass\n")
    spec = VerificationSpec(required_classes=["MyClass"])
    result = ASTVerifier(spec).verify(tmp_path)
    assert result.passed is False
    assert any("MyClass" in v for v in result.violations)


def test_missing_import(tmp_path: Path) -> None:
    (tmp_path / "solution.py").write_text("def f(): pass\n")
    spec = VerificationSpec(required_imports=["json"])
    result = ASTVerifier(spec).verify(tmp_path)
    assert result.passed is False
    assert any("json" in v for v in result.violations)


def test_forbidden_name(tmp_path: Path) -> None:
    (tmp_path / "solution.py").write_text("def eval(): pass\n")
    spec = VerificationSpec(forbidden_names=["eval"])
    result = ASTVerifier(spec).verify(tmp_path)
    assert result.passed is False
    assert any("eval" in v for v in result.violations)


def test_min_files(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n")
    spec = VerificationSpec(min_files=3)
    result = ASTVerifier(spec).verify(tmp_path)
    assert result.passed is False
    assert any("at least 3" in v for v in result.violations)


def test_max_files(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.py").write_text("y = 2\n")
    (tmp_path / "c.py").write_text("z = 3\n")
    spec = VerificationSpec(max_files=2)
    result = ASTVerifier(spec).verify(tmp_path)
    assert result.passed is False
    assert any("Too many" in v for v in result.violations)


def test_min_lines(tmp_path: Path) -> None:
    (tmp_path / "solution.py").write_text("x = 1\n")
    spec = VerificationSpec(min_lines_total=100)
    result = ASTVerifier(spec).verify(tmp_path)
    assert result.passed is False
    assert any("lines" in v for v in result.violations)


def test_no_workspace() -> None:
    spec = VerificationSpec()
    result = ASTVerifier(spec).verify(None)
    assert result.passed is False
    assert "No workspace" in result.violations[0]


def test_empty_workspace(tmp_path: Path) -> None:
    spec = VerificationSpec()
    result = ASTVerifier(spec).verify(tmp_path)
    assert result.passed is True  # no violations in empty workspace
    assert result.files_scanned == 0


def test_multi_file(tmp_path: Path) -> None:
    (tmp_path / "utils.py").write_text("import json\ndef helper(): pass\n")
    (tmp_path / "main.py").write_text("from utils import helper\ndef run(): pass\n")
    spec = VerificationSpec(
        required_functions=["helper", "run"],
        required_imports=["json"],
        must_compile=True,
    )
    result = ASTVerifier(spec).verify(tmp_path)
    assert result.passed is True
    assert result.files_scanned == 2
