"""Adapter registry: maps harness name -> adapter class.

Add a new harness by subclassing BaseAgentAdapter and appending it here.
The runner resolves ``harness`` CLI args against ``ADAPTERS``.
"""

from __future__ import annotations

from agents.base import BaseAgentAdapter, ExecutionResult

# Real adapters (filled in below).
from agents.claude_code_adapter import ClaudeCodeAdapter
from agents.antigravity_adapter import AntigravityAdapter
from agents.deepseek_harness_adapter import DeepSeekHarnessAdapter, DeepSeekReasonixAdapter
from agents.gemini_cli_adapter import GeminiCLIAdapter
from agents.opencode_adapter import OpenCodeAdapter
from agents.stub_adapter import StubAdapter

ADAPTERS: dict[str, type[BaseAgentAdapter]] = {
    "claude-code": ClaudeCodeAdapter,
    "antigravity-cli": AntigravityAdapter,
    "deepseek-harness": DeepSeekHarnessAdapter,
    "DeepSeek-Reasonix": DeepSeekReasonixAdapter,
    "gemini-cli": GeminiCLIAdapter,
    "opencode": OpenCodeAdapter,
    "stub": StubAdapter,  # for smoke tests; not part of the real matrix
}


def resolve(name: str) -> BaseAgentAdapter:
    """Instantiate an adapter by registry name.

    Raises KeyError if the name is unknown — the caller should map ``all``
    to the full set before calling here.
    """
    try:
        return ADAPTERS[name]()
    except KeyError as exc:
        raise KeyError(
            f"unknown harness {name!r}; known: {sorted(ADAPTERS)}"
        ) from exc


__all__ = [
    "ADAPTERS",
    "AdapterContext",
    "AntigravityAdapter",
    "BaseAgentAdapter",
    "ClaudeCodeAdapter",
    "DeepSeekHarnessAdapter",
    "DeepSeekReasonixAdapter",
    "ExecutionResult",
    "GeminiCLIAdapter",
    "OpenCodeAdapter",
    "StubAdapter",
    "resolve",
]