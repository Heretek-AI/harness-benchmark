"""Unit tests for the LSP & AST Diagnostic engine."""

from __future__ import annotations

from pathlib import Path

from core.lsp import LSPDiagnosticsEngine


def test_lsp_syntax_checks(tmp_path: Path) -> None:
    # 1. Clean code
    clean_code = "def valid_func(x: int) -> int:\n    return x * 2\n"
    diagnostics = LSPDiagnosticsEngine.check_syntax(clean_code, filename="clean.py")
    assert len(diagnostics) == 0

    # 2. Syntax error
    broken_code = "def broken_func(x\n    return x\n"
    errs = LSPDiagnosticsEngine.check_syntax(broken_code, filename="broken.py")
    assert len(errs) > 0
    assert "SyntaxError" in errs[0]

    # 3. Workspace check
    (tmp_path / "valid.py").write_text(clean_code)
    (tmp_path / "broken.py").write_text(broken_code)

    ws_diags = LSPDiagnosticsEngine.check_workspace(tmp_path)
    assert any("broken.py" in d or "SyntaxError" in d for d in ws_diags)
