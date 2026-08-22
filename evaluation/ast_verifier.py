"""AST Verification Pipeline for code structure validation.

Uses Python's built-in ``ast`` module to verify that generated code
contains expected structural elements (classes, functions, imports)
and compiles without syntax errors.  For multi-file repos, scans
all ``.py`` files in a workspace.

Usage::

    from evaluation.ast_verifier import ASTVerifier, VerificationSpec

    spec = VerificationSpec(
        required_functions=["sort_list", "merge_sort"],
        required_imports=["typing"],
        must_compile=True,
        min_files=2,
    )
    verifier = ASTVerifier(spec)
    result = verifier.verify(workspace_dir=Path("/tmp/run-123"))
    print(result.passed, result.violations)
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class VerificationSpec:
    """Specification for what the code must contain."""

    required_functions: list[str] = field(default_factory=list)
    required_classes: list[str] = field(default_factory=list)
    required_imports: list[str] = field(default_factory=list)  # module names
    forbidden_names: list[str] = field(default_factory=list)  # e.g. ["eval", "exec"]
    must_compile: bool = True
    min_files: int | None = None
    max_files: int | None = None
    min_lines_total: int | None = None


@dataclass
class VerificationResult:
    """Result of AST verification."""

    passed: bool
    violations: list[str] = field(default_factory=list)
    files_scanned: int = 0
    functions_found: list[str] = field(default_factory=list)
    classes_found: list[str] = field(default_factory=list)
    imports_found: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.passed:
            return f"AST verification passed ({self.files_scanned} files, {len(self.functions_found)} functions)"
        return f"AST verification failed: {'; '.join(self.violations)}"


class ASTVerifier:
    """Verify code structure using Python's ast module."""

    def __init__(self, spec: VerificationSpec) -> None:
        self.spec = spec

    def verify(self, workspace_dir: Path | None = None) -> VerificationResult:
        """Verify all .py files in the workspace against the spec."""
        if workspace_dir is None or not workspace_dir.exists():
            return VerificationResult(passed=False, violations=["No workspace directory"])

        py_files = list(workspace_dir.rglob("*.py"))
        violations: list[str] = []
        all_functions: list[str] = []
        all_classes: list[str] = []
        all_imports: list[str] = []

        # Check file count
        if self.spec.min_files is not None and len(py_files) < self.spec.min_files:
            violations.append(f"Need at least {self.spec.min_files} .py files, found {len(py_files)}")
        if self.spec.max_files is not None and len(py_files) > self.spec.max_files:
            violations.append(f"Too many .py files: {len(py_files)} > {self.spec.max_files}")

        total_lines = 0
        for py_file in py_files:
            try:
                source = py_file.read_text(errors="replace")
                total_lines += len(source.splitlines())

                # Compile check
                if self.spec.must_compile:
                    try:
                        compile(source, str(py_file), "exec")
                    except SyntaxError as e:
                        violations.append(f"Syntax error in {py_file.name}: {e}")
                        continue

                # Parse AST
                try:
                    tree = ast.parse(source)
                except SyntaxError:
                    continue

                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        all_functions.append(node.name)
                    elif isinstance(node, ast.AsyncFunctionDef):
                        all_functions.append(node.name)
                    elif isinstance(node, ast.ClassDef):
                        all_classes.append(node.name)
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            all_imports.append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            all_imports.append(node.module)

            except Exception as e:
                logger.debug("Error reading %s: %s", py_file, e)

        # Check min_lines
        if self.spec.min_lines_total is not None and total_lines < self.spec.min_lines_total:
            violations.append(f"Need at least {self.spec.min_lines_total} total lines, found {total_lines}")

        # Check required functions
        for fn in self.spec.required_functions:
            if fn not in all_functions:
                violations.append(f"Missing required function: {fn}")

        # Check required classes
        for cls in self.spec.required_classes:
            if cls not in all_classes:
                violations.append(f"Missing required class: {cls}")

        # Check required imports
        for imp in self.spec.required_imports:
            if imp not in all_imports:
                violations.append(f"Missing required import: {imp}")

        # Check forbidden names
        all_names = all_functions + all_classes
        for name in self.spec.forbidden_names:
            if name in all_names:
                violations.append(f"Forbidden name found: {name}")

        return VerificationResult(
            passed=len(violations) == 0,
            violations=violations,
            files_scanned=len(py_files),
            functions_found=sorted(set(all_functions)),
            classes_found=sorted(set(all_classes)),
            imports_found=sorted(set(all_imports)),
        )
