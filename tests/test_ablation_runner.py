"""Tests for the 5-tier AblationRunner."""

from __future__ import annotations

from pathlib import Path

from benchmarks.runner import BenchmarkRunner, RunConfig
from core.types import AblationTier
from evaluation.ablation_runner import TIER_CELLS, AblationRunner, TierCell
from mcp import MCPLauncher
from plugins import PluginLoader


def _make_runner(tmp_path: Path, plugin_registry: Path, mcp_registry: Path) -> BenchmarkRunner:
    config = RunConfig(
        name="unit-ablation",
        harness=["stub"],
        benchmark=["coder_eval"],
        plugins=["none"],
        mcp_servers=["none"],
        tasks_limit=1,
        timeout_seconds=30,
        output_format="json",
        output_dir=tmp_path / "runs",
    )
    return BenchmarkRunner(
        config,
        PluginLoader(plugin_registry),
        MCPLauncher(mcp_registry),
    )


def test_tier_cell_order_matches_5_tiers() -> None:
    """TIER_CELLS must enumerate tier_0 through tier_4 in order."""
    assert [c.tier for c in TIER_CELLS] == [
        AblationTier.TIER_0_BARE.value,
        AblationTier.TIER_1_LSP.value,
        AblationTier.TIER_2_SKILLS.value,
        AblationTier.TIER_3_MCP.value,
        AblationTier.TIER_4_FULL_STACK.value,
    ]


def test_tier_cell_lsp_enabled_distinguishes_tiers() -> None:
    """Tier 1 and Tier 4 have lsp_enabled; the rest do not."""
    by_tier = {c.tier: c for c in TIER_CELLS}
    assert by_tier[AblationTier.TIER_0_BARE.value].lsp_enabled is False
    assert by_tier[AblationTier.TIER_1_LSP.value].lsp_enabled is True
    assert by_tier[AblationTier.TIER_2_SKILLS.value].lsp_enabled is False
    assert by_tier[AblationTier.TIER_3_MCP.value].lsp_enabled is False
    assert by_tier[AblationTier.TIER_4_FULL_STACK.value].lsp_enabled is True


def test_ablation_runner_emits_five_cells(
    tmp_path: Path,
    plugin_registry_path: Path,
    mcp_registry_path: Path,
) -> None:
    """End-to-end: run against stub + coder_eval, expect 5 cells with all 5 tiers."""
    runner = _make_runner(tmp_path, plugin_registry_path, mcp_registry_path)
    ablation = AblationRunner(
        harness_name="stub",
        benchmark_name="coder_eval",
        benchmark_runner=runner,
    )
    result = ablation.run()
    assert result.report is not None
    assert set(result.cells.keys()) == {
        AblationTier.TIER_0_BARE.value,
        AblationTier.TIER_1_LSP.value,
        AblationTier.TIER_2_SKILLS.value,
        AblationTier.TIER_3_MCP.value,
        AblationTier.TIER_4_FULL_STACK.value,
    }
    assert len(result.summaries) == 5


def test_ablation_runner_tags_results_with_tier(
    tmp_path: Path,
    plugin_registry_path: Path,
    mcp_registry_path: Path,
) -> None:
    """Every per-task ExecutionResult carries the explicit tier string."""
    runner = _make_runner(tmp_path, plugin_registry_path, mcp_registry_path)
    ablation = AblationRunner(
        harness_name="stub",
        benchmark_name="coder_eval",
        benchmark_runner=runner,
    )
    result = ablation.run()
    for tier_name, results in result.cells.items():
        assert all(r.tier == tier_name for r in results), (
            f"cell {tier_name} has mis-tagged results: {[r.tier for r in results]}"
        )


def test_ablation_runner_records_lsp_enabled_per_cell(
    tmp_path: Path,
    plugin_registry_path: Path,
    mcp_registry_path: Path,
) -> None:
    """Tier 1 / Tier 4 cells must record lsp_enabled=True on every result."""
    runner = _make_runner(tmp_path, plugin_registry_path, mcp_registry_path)
    ablation = AblationRunner(
        harness_name="stub",
        benchmark_name="coder_eval",
        benchmark_runner=runner,
    )
    result = ablation.run()
    assert all(r.lsp_enabled for r in result.cells[AblationTier.TIER_1_LSP.value])
    assert all(r.lsp_enabled for r in result.cells[AblationTier.TIER_4_FULL_STACK.value])
    assert not any(r.lsp_enabled for r in result.cells[AblationTier.TIER_0_BARE.value])
    assert not any(r.lsp_enabled for r in result.cells[AblationTier.TIER_2_SKILLS.value])
    assert not any(r.lsp_enabled for r in result.cells[AblationTier.TIER_3_MCP.value])


def test_resolve_cells_substitutes_plugin_and_mcp_names() -> None:
    """Custom plugin / mcp names should appear in Tier 2/3/4 cells only."""
    from evaluation.ablation_runner import _resolve_cells

    cells = _resolve_cells(skills_plugin="ECC", mcp_for_ablation="context7")
    by_tier = {c.tier: c for c in cells}
    assert "ECC" in by_tier[AblationTier.TIER_2_SKILLS.value].plugins
    assert "ECC" in by_tier[AblationTier.TIER_4_FULL_STACK.value].plugins
    assert "context7" in by_tier[AblationTier.TIER_3_MCP.value].mcp_servers
    assert "context7" in by_tier[AblationTier.TIER_4_FULL_STACK.value].mcp_servers
    # Tier 0/1 should have empty plugins.
    assert by_tier[AblationTier.TIER_0_BARE.value].plugins == []
    assert by_tier[AblationTier.TIER_1_LSP.value].plugins == []


def test_tier_cell_is_immutable() -> None:
    """Frozen dataclass => attribute assignment raises."""
    import pytest

    cell = TierCell(tier="tier_0_bare", plugins=[], mcp_servers=["none"], lsp_enabled=False)
    with pytest.raises((AttributeError, Exception)):  # FrozenInstanceError or AttributeError
        cell.tier = "tier_1_lsp"  # type: ignore[misc]
