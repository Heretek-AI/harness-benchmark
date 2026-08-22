"""Tests for the LSP feedback loop module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from evaluation.lsp_feedback import (
    MAX_LSP_ITERATIONS,
    run_lsp_iteration_loop,
    wrap_prompt_for_lsp,
)


def _make_adapter() -> MagicMock:
    a = MagicMock()
    a.execute_task = MagicMock(return_value=MagicMock(name="ExecutionResult"))
    return a


def test_wrap_prompt_returns_unchanged_when_disabled(tmp_path: Path) -> None:
    assert wrap_prompt_for_lsp("hello", tmp_path, lsp_enabled=False) == "hello"


def test_wrap_prompt_returns_unchanged_when_workspace_clean(tmp_path: Path) -> None:
    """Enabled but no diagnostics -> still no prefix."""
    assert wrap_prompt_for_lsp("hello", tmp_path, lsp_enabled=True) == "hello"


def test_wrap_prompt_includes_diagnostics_when_enabled(tmp_path: Path) -> None:
    """Enabled and dirty workspace -> diagnostics prefix."""
    (tmp_path / "broken.py").write_text("def foo(:\n")
    out = wrap_prompt_for_lsp("write the function", tmp_path, lsp_enabled=True)
    assert "[LSP Diagnostics" in out
    assert "write the function" in out


def test_run_lsp_iteration_loop_one_call_when_disabled(tmp_path: Path) -> None:
    adapter = _make_adapter()
    result, diags = run_lsp_iteration_loop(adapter, prompt="p", workspace_dir=tmp_path, timeout=10, lsp_enabled=False)
    assert adapter.execute_task.call_count == 1
    assert diags == []
    assert result is not None


def test_run_lsp_iteration_loop_breaks_on_clean_workspace(tmp_path: Path) -> None:
    adapter = _make_adapter()
    # Workspace is clean; even with lsp_enabled=True we should run exactly once.
    _result, diags = run_lsp_iteration_loop(adapter, prompt="p", workspace_dir=tmp_path, timeout=10, lsp_enabled=True)
    assert adapter.execute_task.call_count == 1
    assert diags == []


def test_run_lsp_iteration_loop_caps_at_max_iters(tmp_path: Path) -> None:
    adapter = _make_adapter()
    # Make a permanently broken file so diagnostics are non-empty every iteration.
    (tmp_path / "broken.py").write_text("def foo(:\n")
    _result, diags = run_lsp_iteration_loop(
        adapter,
        prompt="p",
        workspace_dir=tmp_path,
        timeout=10,
        lsp_enabled=True,
        max_iters=MAX_LSP_ITERATIONS,
    )
    # 1 initial call + (max_iters - 1) feedback rounds = max_iters total.
    assert adapter.execute_task.call_count == MAX_LSP_ITERATIONS
    assert len(diags) >= MAX_LSP_ITERATIONS - 1
    # The first call received the prefixed prompt; subsequent calls received
    # the "[LSP Iteration N/M]" prompt.
    first_prompt = adapter.execute_task.call_args_list[0].args[0]
    last_prompt = adapter.execute_task.call_args_list[-1].args[0]
    assert first_prompt.startswith("[LSP Diagnostics")
    assert last_prompt.startswith(f"[LSP Iteration {MAX_LSP_ITERATIONS}/{MAX_LSP_ITERATIONS}]")


def test_run_lsp_iteration_loop_breaks_when_iteration_fixes_workspace(tmp_path: Path) -> None:
    """After the harness writes a clean file, the loop should stop."""
    adapter = _make_adapter()

    broken = tmp_path / "broken.py"
    broken.write_text("def foo(:\n")  # dirty

    def fake_execute(prompt: str, cwd: Path, timeout: int):
        # On the first call (post-prefix), overwrite the broken file with valid code.
        if "[LSP Iteration 2/" in prompt:
            broken.write_text("def foo():\n    return 1\n")
        return MagicMock(name="ExecutionResult")

    adapter.execute_task.side_effect = fake_execute

    _, diags = run_lsp_iteration_loop(
        adapter,
        prompt="p",
        workspace_dir=tmp_path,
        timeout=10,
        lsp_enabled=True,
        max_iters=3,
    )
    # 1 initial + 1 feedback (after which workspace is clean) = 2 total.
    assert adapter.execute_task.call_count == 2
    # Round-1 diagnostics were observed.
    assert any("SyntaxError" in d or "LSP Lint" in d or d for d in diags)
