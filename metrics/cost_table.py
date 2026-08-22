"""Tiny model-pricing table.

Prices are USD per 1M tokens. Override ``HARNESS_BENCH_PRICING_JSON`` to
point at your own table; otherwise the defaults below apply.

This is intentionally minimal — add entries as new models show up in the
benchmark runs. Unknown models produce ``None`` cost, which the report
surfaces as ``-`` rather than a misleading ``0.0``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5": {"input": 0.8, "output": 4.0},
    "gpt-4o": {"input": 5.0, "output": 15.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.0},
    "gemini-2.5-flash": {"input": 0.3, "output": 2.5},
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


def cost_for(model: str, tokens_in: int, tokens_out: int) -> float | None:
    """Return USD cost, or None if ``model`` isn't priced."""
    _load_overrides()
    entry = _PRICING.get(model)
    if entry is None:
        return None
    cost = (tokens_in / 1_000_000) * entry["input"] + (tokens_out / 1_000_000) * entry["output"]
    return round(cost, 6)
