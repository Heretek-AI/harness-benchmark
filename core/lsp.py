"""Language Server Protocol (LSP) & AST Diagnostic Feedback Engine."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


class LSPDiagnosticsEngine:
    """Provides compiler and language server diagnostic feedback loops."""

    @staticmethod
    def check_syntax(code: str, filename: str = "<string>") -> list[str]:
        """Perform static AST parsing and compile checking on a code snippet."""
        diagnostics: list[str] = []
        try:
            ast.parse(code, filename=filename)
        except SyntaxError as e:
            diagnostics.append(f"LSP SyntaxError: {e.msg} at line {e.lineno}, col {e.offset}")
        except Exception as e:
            diagnostics.append(f"LSP ParseError: {e!s}")
        return diagnostics

    @staticmethod
    def check_workspace(workspace_dir: Path) -> list[str]:
        """Run AST validation and static checks across all Python files in workspace."""
        diagnostics: list[str] = []
        if not workspace_dir.exists():
            return diagnostics

        for py_file in workspace_dir.glob("**/*.py"):
            try:
                code = py_file.read_text(encoding="utf-8")
                errs = LSPDiagnosticsEngine.check_syntax(code, filename=py_file.name)
                diagnostics.extend(errs)
            except Exception as e:
                diagnostics.append(f"LSP ReadError: {py_file.name}: {e}")

        # Optional fast ruff check if available
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "ruff", "check", "--select=E,F", str(workspace_dir)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode != 0 and proc.stdout:
                for line in proc.stdout.splitlines()[:5]:
                    if line.strip():
                        diagnostics.append(f"LSP Lint: {line.strip()}")
        except Exception:
            pass

        return diagnostics
