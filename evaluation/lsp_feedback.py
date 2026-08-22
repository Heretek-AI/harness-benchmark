"""Pre-prompt and post-task LSP diagnostic feedback loops.

Two operations:

- ``wrap_prompt_for_lsp`` prepends a snapshot of any current LSP
  diagnostics to the harness prompt. Used as the Tier 1 ablation cell's
  distinguishing behaviour.
- ``run_lsp_iteration_loop`` invokes the harness up to ``max_iters``
  times, re-checking diagnostics after each round and re-prompting the
  harness with the latest diagnostics if any remain. Stops early when
  diagnostics are clean.

The runner wires these into ``BenchmarkRunner._run_cell`` so the rest of
the matrix sweep is harness-agnostic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.lsp import LSPDiagnosticsEngine

MAX_LSP_ITERATIONS = 3
_MAX_DIAGS_PER_PREFIX = 10


def wrap_prompt_for_lsp(
    prompt: str,
    workspace_dir: Path,
    lsp_enabled: bool,
) -> str:
    """Return ``prompt`` unchanged for Tier 0; prefix diagnostics for Tier 1+.

    Diagnostics are capped at ``_MAX_DIAGS_PER_PREFIX`` lines so the
    prepended block never dominates the original prompt.
    """
    if not lsp_enabled:
        return prompt
    diagnostics = LSPDiagnosticsEngine.check_workspace(workspace_dir)
    if not diagnostics:
        return prompt
    body = "\n".join(diagnostics[:_MAX_DIAGS_PER_PREFIX])
    return f"[LSP Diagnostics ({len(diagnostics)} issue(s))]:\n{body}\n\n{prompt}"


def run_lsp_iteration_loop(
    adapter: Any,
    prompt: str,
    workspace_dir: Path,
    timeout: int,
    lsp_enabled: bool,
    max_iters: int = MAX_LSP_ITERATIONS,
) -> tuple[Any, list[str]]:
    """Run the harness with optional LSP feedback rounds.

    Returns ``(final_execution_result, accumulated_diagnostics)``.
    ``accumulated_diagnostics`` is empty when ``lsp_enabled=False``; for
    enabled cells it contains every diagnostic line observed across
    rounds (useful for the report).
    """
    iter_diagnostics: list[str] = []
    current_prompt = wrap_prompt_for_lsp(prompt, workspace_dir, lsp_enabled)
    result = adapter.execute_task(current_prompt, workspace_dir, timeout=timeout)

    if not lsp_enabled:
        return result, iter_diagnostics

    for i in range(1, max_iters):
        diagnostics = LSPDiagnosticsEngine.check_workspace(workspace_dir)
        iter_diagnostics.extend(diagnostics)
        if not diagnostics:
            break
        body = "\n".join(diagnostics[:_MAX_DIAGS_PER_PREFIX])
        current_prompt = f"[LSP Iteration {i + 1}/{max_iters}]:\n{body}\n\nOriginal prompt:\n{prompt}"
        result = adapter.execute_task(current_prompt, workspace_dir, timeout=timeout)

    return result, iter_diagnostics
