"""Unit tests for the SVG status badge generator."""

from __future__ import annotations

from pathlib import Path

from metrics.badges import BadgeGenerator


def test_badge_svg_generation(tmp_path: Path) -> None:
    svg = BadgeGenerator.generate_svg("MCP-Improvement", "+34.2%", "#4c1")
    assert "<svg" in svg
    assert "MCP-Improvement" in svg
    assert "+34.2%" in svg

    exported = BadgeGenerator.export_badges(
        tmp_path / "badges",
        mcp_improvement_pct=34.2,
        lsp_error_reduction_pct=82.0,
        full_stack_pass_rate=0.92,
    )

    assert "mcp" in exported
    assert "lsp" in exported
    assert "full_stack" in exported
    assert exported["mcp"].exists()
    assert "+34.2%" in exported["mcp"].read_text(encoding="utf-8")
