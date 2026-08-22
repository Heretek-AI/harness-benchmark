"""Unified benchmark orchestrator.

Given a run config (preset YAML or CLI inputs), the runner:

1. Resolves ``harness``, ``benchmark``, ``plugins``, ``mcp_servers`` (the
   special tokens ``all`` and ``none`` expand against the registries).
2. For each (harness x benchmark x plugin-set x mcp-set) tuple:
   a. Creates an adapter, calls ``setup(env, plugins, mcp_servers)``.
   b. Synthesizes the plugin staging root via ``PluginLoader``.
   c. Launches any MCP servers via ``MCPLauncher`` and patches the
      adapter's env so it can find the registry path.
   d. Iterates tasks: copies fixtures, runs the harness, grades the
      result, records metrics.
   e. Tears down the adapter and the MCP servers.
3. Returns a ``RunReport`` summarising every (harness, benchmark) cell.

The runner is harness-agnostic: it knows nothing about Claude Code or
Gemini except through the adapter interface and the registries.
"""

from __future__ import annotations

import itertools
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents import ADAPTERS, BaseAgentAdapter
from agents.base import ExecutionResult
from benchmarks import REGISTRY as BENCHMARKS
from benchmarks import BaseBenchmark
from metrics.collector import MetricCollector
from metrics.report_generator import render_markdown
from plugins import PluginLoader

logger = logging.getLogger(__name__)


@dataclass
class RunConfig:
    name: str
    harness: list[str]
    benchmark: list[str]
    plugins: list[str]
    mcp_servers: list[str]
    tasks_limit: int = 0
    timeout_seconds: int = 600
    output_format: str = "json"
    output_dir: Path = field(default_factory=lambda: Path("runs"))
    extra_env: dict[str, str] = field(default_factory=dict)


@dataclass
class RunReport:
    run_id: str
    config: RunConfig
    started_at: float
    finished_at: float | None = None
    results: list[ExecutionResult] = field(default_factory=list)
    metric_summaries: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "name": self.config.name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "config": {
                "harness": self.config.harness,
                "benchmark": self.config.benchmark,
                "plugins": self.config.plugins,
                "mcp_servers": self.config.mcp_servers,
                "tasks_limit": self.config.tasks_limit,
                "timeout_seconds": self.config.timeout_seconds,
            },
            "summaries": self.metric_summaries,
            "results": [r.model_dump() for r in self.results],
        }


class BenchmarkRunner:
    """Drives one full run config end-to-end."""

    def __init__(
        self,
        config: RunConfig,
        plugin_loader: PluginLoader,
        mcp_launcher: Any,
        metric_collector: MetricCollector | None = None,
    ) -> None:
        self.config = config
        self.plugin_loader = plugin_loader
        self.mcp_launcher = mcp_launcher
        self.metric_collector = metric_collector or MetricCollector()
        # Patch env so adapters can find the registries without us having
        # to plumb paths through every constructor call.
        os.environ["HARNESS_BENCH_MCP_REGISTRY"] = str(mcp_launcher.registry_path)
        os.environ.setdefault("HARNESS_BENCH_PLUGIN_REGISTRY", str(plugin_loader.registry_path))

    # ---- public ----

    def run(self) -> RunReport:
        run_id = f"{self.config.name}-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        report = RunReport(run_id=run_id, config=self.config, started_at=time.time())
        run_dir = self.config.output_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        cells = list(
            itertools.product(
                self._harness_cells(),
                self._benchmark_cells(),
                self._plugin_cells(),
                self._mcp_cells(),
            )
        )
        logger.info("resolved %d cells to run", len(cells))

        for harness, benchmark, plugins, mcp_servers in cells:
            logger.info(
                "running cell harness=%s benchmark=%s plugins=%s mcp=%s",
                harness,
                benchmark,
                plugins,
                mcp_servers,
            )
            cell_results = self._run_cell(harness, benchmark, plugins, mcp_servers, run_dir)
            report.results.extend(cell_results)
            self.metric_collector.reset()
            for r in cell_results:
                self.metric_collector.record(r, benchmark=benchmark)
            report.metric_summaries.append(
                {
                    "harness": harness,
                    "benchmark": benchmark,
                    "plugins": plugins,
                    "mcp_servers": mcp_servers,
                    "summary": self.metric_collector.summarize(),
                }
            )

        report.finished_at = time.time()
        self._write_outputs(report, run_dir)
        return report

    # ---- internals ----

    def _run_cell(
        self,
        harness_name: str,
        benchmark_name: str,
        plugins: list[str],
        mcp_servers: list[str],
        run_dir: Path,
    ) -> list[ExecutionResult]:
        if harness_name not in ADAPTERS:
            logger.warning("unknown harness %r; skipping cell", harness_name)
            return []
        if benchmark_name not in BENCHMARKS:
            logger.warning("unknown benchmark %r; skipping cell", benchmark_name)
            return []

        adapter: BaseAgentAdapter = ADAPTERS[harness_name]()
        benchmark: BaseBenchmark = BENCHMARKS[benchmark_name]()
        plugin_dir = self.plugin_loader.synthesize_agent_config(harness_name, plugins)
        mcp_handles = self.mcp_launcher.launch(mcp_servers)
        self.mcp_launcher.wait_ready(mcp_handles)

        cell_env = {
            "LLM_API": os.environ.get("LLM_API", ""),
            "LLM_KEY": os.environ.get("LLM_KEY", ""),
            "LLM_MODEL": os.environ.get("LLM_MODEL", ""),
            **self.config.extra_env,
        }

        results: list[ExecutionResult] = []
        try:
            ctx = adapter.setup(
                env_vars=cell_env,
                plugins=plugins,
                mcp_servers=mcp_servers,
            )
            # Inject the synthesized plugin_dir into the context AFTER
            # setup (so adapters that don't expect it are unaffected).
            ctx.plugin_dir = plugin_dir

            for task in benchmark.iter_tasks(self.config.tasks_limit):
                cwd = ctx.workspace_dir
                if task.workspace_subdir:
                    cwd = cwd / task.workspace_subdir
                    cwd.mkdir(parents=True, exist_ok=True)
                benchmark.pre_setup(cwd)
                result = adapter.execute_task(task.prompt, cwd, timeout=self.config.timeout_seconds)
                result.benchmark = benchmark_name
                result.task_id = task.task_id
                result.plugins = list(plugins)
                result.mcp_servers = list(mcp_servers)
                result.passed = benchmark.grade(result, task.expected, cwd=cwd)
                if (
                    result.tokens_input is not None or result.tokens_output is not None
                ) and result.tokens_total is None:
                    result.tokens_total = (result.tokens_input or 0) + (result.tokens_output or 0)
                if result.tokens_total is not None and result.cost_usd is None:
                    result.cost_usd = BaseAgentAdapter.estimate_cost(
                        os.environ.get("LLM_MODEL", ""),
                        result.tokens_input or 0,
                        result.tokens_output or 0,
                    )
                results.append(result)
                # Per-task JSONL artifact for downstream drill-down.
                with (run_dir / f"{harness_name}__{benchmark_name}__{task.task_id}.jsonl").open("a") as f:
                    f.write(result.model_dump_json() + "\n")
        finally:
            try:
                adapter.teardown()
            finally:
                self.mcp_launcher.terminate(mcp_handles)
        return results

    def _harness_cells(self) -> list[str]:
        cleaned = [h for h in self.config.harness if h]
        if "all" in cleaned:
            return [name for name in ADAPTERS if name != "stub"]
        return cleaned

    def _benchmark_cells(self) -> list[str]:
        cleaned = [b for b in self.config.benchmark if b]
        if "all" in cleaned:
            return list(BENCHMARKS.keys())
        return cleaned

    def _plugin_cells(self) -> list[list[str]]:
        cleaned = [p for p in self.config.plugins if p]
        if "all" in cleaned:
            return [["none"]] + [[n] for n in self.plugin_loader.names()]
        if "none" in cleaned or not cleaned:
            return [[]]
        return [cleaned] if len(cleaned) > 1 else [[c] for c in cleaned]

    def _mcp_cells(self) -> list[list[str]]:
        cleaned = [m for m in self.config.mcp_servers if m]
        if "all" in cleaned:
            return [["none"]] + [[n] for n in self.mcp_launcher.names()]
        if "none" in cleaned or not cleaned:
            return [[]]
        return [cleaned] if len(cleaned) > 1 else [[c] for c in cleaned]

    # ---- outputs ----

    def _write_outputs(self, report: RunReport, run_dir: Path) -> None:
        (run_dir / "result.json").write_text(json.dumps(report.to_dict(), indent=2, default=str))
        if self.config.output_format in ("markdown", "github-summary"):
            (run_dir / "REPORT.md").write_text(render_markdown(report))
        logger.info("wrote outputs to %s", run_dir)
