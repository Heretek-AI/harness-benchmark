"""Comprehensive model-pricing table for multi-harness token cost accounting.

Prices are USD per 1M tokens. Override ``HARNESS_BENCH_PRICING_JSON`` to
point at your own table; otherwise the defaults below apply.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_PRICING: dict[str, dict[str, float]] = {
    # Anthropic
    "claude-opus-4": {"input": 15.0, "output": 75.0, "cache_read": 1.5},
    "claude-sonnet-4": {"input": 3.0, "output": 15.0, "cache_read": 0.3},
    "claude-haiku-4-5": {"input": 0.8, "output": 4.0, "cache_read": 0.08},
    "claude-3-7-sonnet-latest": {"input": 3.0, "output": 15.0, "cache_read": 0.3},
    "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0, "cache_read": 0.3},
    # OpenAI
    "gpt-4o": {"input": 2.5, "output": 10.0, "cache_read": 1.25},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6, "cache_read": 0.075},
    "o1": {"input": 15.0, "output": 60.0, "cache_read": 7.5},
    "o3-mini": {"input": 1.1, "output": 4.4, "cache_read": 0.55},
    # DeepSeek
    "deepseek-chat": {"input": 0.14, "output": 0.28, "cache_read": 0.014},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19, "cache_read": 0.14},
    "deepseek-v3": {"input": 0.14, "output": 0.28, "cache_read": 0.014},
    "deepseek-r1": {"input": 0.55, "output": 2.19, "cache_read": 0.14},
    # Google
    "gemini-2.5-pro": {"input": 1.25, "output": 10.0, "cache_read": 0.3125},
    "gemini-2.5-flash": {"input": 0.3, "output": 2.5, "cache_read": 0.075},
    "gemini-2.0-flash-exp": {"input": 0.0, "output": 0.0, "cache_read": 0.0},
    # MiniMax
    "MiniMax-M3": {"input": 0.40, "output": 1.60, "cache_read": 0.04},
    "minimax-m3": {"input": 0.40, "output": 1.60, "cache_read": 0.04},
    # Open / Local
    "qwen-2.5-coder-32b": {"input": 0.20, "output": 0.60, "cache_read": 0.02},
    "llama-3.3-70b-instruct": {"input": 0.35, "output": 0.90, "cache_read": 0.035},
}


def _load_overrides() -> None:
    path = os.environ.get("HARNESS_BENCH_PRICING_JSON")
    if not path:
        return
    p = Path(path)
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError:
        return
    if isinstance(data, dict):
        _PRICING.update(data)


def cost_for(model: str, tokens_in: int, tokens_out: int, cache_read_tokens: int = 0) -> float | None:
    """Return USD cost with prompt cache accounting, or None if ``model`` isn't priced."""
    _load_overrides()
    entry = _PRICING.get(model) or _PRICING.get(model.lower())
    if entry is None:
        return None
    cost = (
        (tokens_in / 1_000_000) * entry["input"]
        + (tokens_out / 1_000_000) * entry["output"]
        + (cache_read_tokens / 1_000_000) * entry.get("cache_read", 0.0)
    )
    return round(cost, 6)
