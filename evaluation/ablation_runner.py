"""Empirically run the deterministic 5-tier ablation matrix.

For a single (harness, benchmark) pair, drives five ordered cells and
returns a ``MultiTierAblationReport``. Each cell is an explicit
configuration of (plugins, mcp_servers, lsp_enabled) chosen so that the
empirical deltas cleanly attribute gains to the right augmentation.

Tier cells::

    tier_0_bare         -> nothing
    tier_1_lsp          -> +LSP feedback loop
    tier_2_skills       -> +static rule harness (caveman)
    tier_3_mcp          -> +MCP dynamic tools (repomix)
    tier_4_full_stack   -> +LSP + skills + MCP together

The default plugin / mcp names (``caveman`` / ``repomix``) can be
overridden via ``AblationRunner.__init__`` arguments; both are
registered in ``plugins/registry.json`` and ``mcp/mcp_registry.json``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from core.types import (
    AblationTier,
    CellSummary,
    MetricSummary,
    MultiTierAblationReport,
)
from evaluation.ablation import AblationEngine

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TierCell:
    """Configuration for one ablation cell."""

    tier: str
    plugins: list[str]
    mcp_servers: list[str]
    lsp_enabled: bool


# The canonical 5-tier matrix. Order matters: the ablation engine
# references cells by tier name, but downstream readers expect tier_0
# first.
TIER_CELLS: tuple[TierCell, ...] = (
    TierCell(AblationTier.TIER_0_BARE.value, plugins=[], mcp_servers=["none"], lsp_enabled=False),
    TierCell(AblationTier.TIER_1_LSP.value, plugins=[], mcp_servers=["none"], lsp_enabled=True),
    TierCell(
        AblationTier.TIER_2_SKILLS.value,
        plugins=["caveman"],
        mcp_servers=["none"],
        lsp_enabled=False,
    ),
    TierCell(
        AblationTier.TIER_3_MCP.value,
        plugins=[],
        mcp_servers=["repomix"],
        lsp_enabled=False,
    ),
    TierCell(
        AblationTier.TIER_4_FULL_STACK.value,
        plugins=["caveman"],
        mcp_servers=["repomix"],
        lsp_enabled=True,
    ),
)


@dataclass
class AblationRunResult:
    """Outcome of an AblationRunner.run() invocation."""

    harness: str
    benchmark: str
    model: str
    cells: dict[str, list[Any]] = field(default_factory=dict)  # tier -> [ExecutionResult]
    summaries: list[CellSummary] = field(default_factory=list)
    report: MultiTierAblationReport | None = None


class AblationRunner:
    """Drive the 5-tier ablation matrix for one (harness, benchmark) pair.

    Reuses the existing ``BenchmarkRunner._run_cell`` so MCP launching,
    plugin staging, hermetic workspaces, oracle grading, and metrics
    collection all stay consistent with the standard sweep.
    """

    def __init__(
        self,
        harness_name: str,
        benchmark_name: str,
        benchmark_runner: Any,
        skills_plugin: str = "caveman",
        mcp_for_ablation: str = "repomix",
    ) -> None:
        self.harness_name = harness_name
        self.benchmark_name = benchmark_name
        self.benchmark_runner = benchmark_runner
        self.cells: tuple[TierCell, ...] = _resolve_cells(skills_plugin, mcp_for_ablation)

    def run(self) -> AblationRunResult:
        result = AblationRunResult(
            harness=self.harness_name,
            benchmark=self.benchmark_name,
            model="",
        )
        run_dir = self.benchmark_runner.config.output_dir / "ablation"
        run_dir.mkdir(parents=True, exist_ok=True)

        for cell in self.cells:
            logger.info(
                "ablation cell %s plugins=%s mcp=%s lsp=%s",
                cell.tier,
                cell.plugins,
                cell.mcp_servers,
                cell.lsp_enabled,
            )
            # Mutate the runner's config per-cell. We restore it after
            # the cell finishes so subsequent cells start clean.
            prior_plugins = self.benchmark_runner.config.plugins
            prior_mcp = self.benchmark_runner.config.mcp_servers
            prior_lsp = self.benchmark_runner.config.lsp_enabled
            try:
                self.benchmark_runner.config.plugins = list(cell.plugins)
                self.benchmark_runner.config.mcp_servers = list(cell.mcp_servers)
                self.benchmark_runner.config.lsp_enabled = cell.lsp_enabled
                cell_results = self.benchmark_runner._run_cell(
                    self.harness_name,
                    self.benchmark_name,
                    list(cell.plugins),
                    list(cell.mcp_servers),
                    run_dir,
                    lsp_enabled=cell.lsp_enabled,
                )
            finally:
                self.benchmark_runner.config.plugins = prior_plugins
                self.benchmark_runner.config.mcp_servers = prior_mcp
                self.benchmark_runner.config.lsp_enabled = prior_lsp

            # Tag every result with the explicit tier so downstream
            # readers can attribute results without re-inferring.
            for r in cell_results:
                r.tier = cell.tier

            result.cells[cell.tier] = cell_results

            # Build the per-cell summary.
            self.benchmark_runner.metric_collector.reset()
            for r in cell_results:
                self.benchmark_runner.metric_collector.record(r, benchmark=self.benchmark_name)
            summary = self.benchmark_runner.metric_collector.summarize()
            cell_summary = CellSummary(
                harness=self.harness_name,
                benchmark=self.benchmark_name,
                plugins=list(cell.plugins),
                mcp_servers=list(cell.mcp_servers),
                summary=MetricSummary(**summary),
            )
            result.summaries.append(cell_summary)

        # Compute the cross-tier delta report.
        result.report = AblationEngine.compute_ablation_report(
            harness=self.harness_name,
            benchmark=self.benchmark_name,
            model=result.model,
            cell_summaries=result.summaries,
        )
        return result


def _resolve_cells(skills_plugin: str, mcp_for_ablation: str) -> tuple[TierCell, ...]:
    """Build a TIER_CELLS sequence substituting the requested plugin/mcp names."""
    return tuple(
        TierCell(
            tier=c.tier,
            plugins=[skills_plugin if c.plugins else p for p in c.plugins],
            mcp_servers=[mcp_for_ablation if m and m != "none" else m for m in c.mcp_servers],
            lsp_enabled=c.lsp_enabled,
        )
        for c in TIER_CELLS
    )
