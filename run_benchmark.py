"""Command-line entrypoint.

Examples
--------
Run the smoke preset against the stub harness::

    python run_benchmark.py --config configs/presets/smoke_test.yaml \\
        --harness stub --output-format markdown

Run a one-off sweep over claude-code + coder_eval + each MCP::

    python run_benchmark.py --harness claude-code --benchmark coder_eval \\
        --plugins none --mcp chrome-devtools-mcp,context7,repomix \\
        --tasks-limit 3 --output-format github-summary
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any

import yaml

# Allow ``python run_benchmark.py`` to import the package modules without
# the user needing ``pip install -e .`` first.
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.runner import BenchmarkRunner, RunConfig  # noqa: E402
from mcp import MCPLauncher  # noqa: E402
from metrics import render_github_summary, render_json, render_markdown  # noqa: E402
from plugins import PluginLoader  # noqa: E402


def _split_csv(value: str) -> list[str]:
    if not value:
        return []
    if value.strip() in ("none", "all"):
        return [value.strip()]
    return [v.strip() for v in value.split(",") if v.strip()]


def _load_preset(path: Path) -> dict:
    if not path.exists():
        candidate = REPO_ROOT / "configs" / "presets" / f"{path.name}"
        if candidate.exists():
            return yaml.safe_load(candidate.read_text())
        candidate_yaml = REPO_ROOT / "configs" / "presets" / f"{path.name}.yaml"
        if candidate_yaml.exists():
            return yaml.safe_load(candidate_yaml.read_text())
    return yaml.safe_load(path.read_text())


def _resolve_registry_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    plugin_registry = Path(
        args.plugin_registry
        or os.environ.get("HARNESS_BENCH_PLUGIN_REGISTRY")
        or REPO_ROOT / "plugins" / "registry.json"
    )
    mcp_registry = Path(
        args.mcp_registry or os.environ.get("HARNESS_BENCH_MCP_REGISTRY") or REPO_ROOT / "mcp" / "mcp_registry.json"
    )
    return plugin_registry, mcp_registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harness-benchmark",
        description=(
            "Run a (harness x benchmark x plugin x MCP) matrix against the "
            "configured LLM and emit JSON + Markdown artefacts."
        ),
    )
    parser.add_argument("--config", "--preset", dest="config", type=Path, help="Preset YAML to load (or preset name)")
    parser.add_argument(
        "--harness",
        default=None,
        help="Comma-separated harness names, 'all', or 'none' (run without harness).",
    )
    parser.add_argument(
        "--benchmark",
        default=None,
        help="Comma-separated benchmark names, 'all', or 'none'.",
    )
    parser.add_argument(
        "--plugins",
        default=None,
        help="Comma-separated plugin names, 'all', or 'none'.",
    )
    parser.add_argument(
        "--mcp",
        dest="mcp_servers",
        default=None,
        help="Comma-separated MCP server names, 'all', or 'none'.",
    )
    parser.add_argument("--tasks-limit", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=None)
    parser.add_argument(
        "--repeat",
        type=int,
        default=None,
        help="Run each task N times for pass^k consistency aggregation",
    )
    parser.add_argument(
        "--output-format",
        choices=["json", "markdown", "github-summary", "scorecard"],
        default=None,
    )
    parser.add_argument("--output-dir", type=Path, default=Path("runs"))
    parser.add_argument(
        "--junit-xml",
        type=Path,
        default=None,
        help="Path to export JUnit XML report",
    )
    parser.add_argument(
        "--minimum-task-score",
        type=float,
        default=None,
        help="Strict floor (0.0 - 1.0) for cell pass-rate. Fails with exit code 1 if below floor.",
    )
    parser.add_argument("--ab-test", action="store_true", help="Enable A/B comparative evaluation")
    parser.add_argument(
        "--ablation",
        action="store_true",
        help="Run the deterministic 5-tier ablation matrix (overrides preset; uses harness + benchmark only)",
    )
    parser.add_argument("--scorecard", action="store_true", help="Render human-centric model scorecard")
    parser.add_argument("--publish-issue", action="store_true", help="Publish report to date-labeled GitHub issue")
    parser.add_argument("--name", default=None, help="Run name; becomes the run-id prefix.")
    parser.add_argument("--plugin-registry", type=Path, help="Override plugins/registry.json path")
    parser.add_argument("--mcp-registry", type=Path, help="Override mcp/mcp_registry.json path")
    parser.add_argument("--debug", action="store_true", help="Enable rich turn-by-turn debug execution logs")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Preset YAML provides defaults; explicit CLI flags override.
    preset = _load_preset(args.config) if args.config else {}
    matrix = preset.get("matrix", {}) if isinstance(preset.get("matrix"), dict) else {}

    def _resolve_list(cli_val: str | None, preset_val: Any, default_str: str) -> list[str]:
        if cli_val is not None:
            return _split_csv(cli_val)
        if preset_val is not None:
            if isinstance(preset_val, list):
                return [str(x) for x in preset_val]
            return _split_csv(str(preset_val))
        return _split_csv(default_str)

    harness = _resolve_list(args.harness, matrix.get("harness"), "all")
    benchmark = _resolve_list(args.benchmark, matrix.get("benchmark"), "all")
    plugins = _resolve_list(args.plugins, matrix.get("plugins"), "none")
    mcp = _resolve_list(args.mcp_servers, matrix.get("mcp_servers"), "none")

    tasks_limit = args.tasks_limit if args.tasks_limit is not None else int(preset.get("tasks_limit", 0) or 0)
    timeout_seconds = args.timeout if args.timeout is not None else int(preset.get("timeout_seconds", 600) or 600)
    output_format = args.output_format if args.output_format is not None else str(preset.get("output_format", "json"))
    name = args.name if args.name is not None else str(preset.get("name") or "ad-hoc")
    repeat_count = args.repeat if args.repeat is not None else int(preset.get("repeat_count", 1) or 1)

    config = RunConfig(
        name=name,
        harness=harness,
        benchmark=benchmark,
        plugins=plugins,
        mcp_servers=mcp,
        tasks_limit=tasks_limit,
        timeout_seconds=timeout_seconds,
        output_format=output_format,
        output_dir=args.output_dir,
        repeat_count=repeat_count,
    )

    plugin_registry, mcp_registry = _resolve_registry_paths(args)
    plugin_loader = PluginLoader(plugin_registry)
    mcp_launcher = MCPLauncher(mcp_registry)

    if args.debug:
        from core.logger import logger as bench_logger

        bench_logger.debug_mode = True

    runner = BenchmarkRunner(config, plugin_loader, mcp_launcher)

    # Ablation runner is a thin layer over BenchmarkRunner._run_cell; it
    # overrides (plugins, mcp_servers, lsp_enabled) per cell and emits a
    # MultiTierAblationReport on top of the standard RunReport.
    ablation_result = None
    if args.ablation:
        from evaluation.ablation_runner import AblationRunner

        if len(harness) != 1 or len(benchmark) != 1:
            print(
                "::error::--ablation requires exactly one --harness and one --benchmark",
                file=sys.stderr,
            )
            return 1
        ablation = AblationRunner(
            harness_name=harness[0],
            benchmark_name=benchmark[0],
            benchmark_runner=runner,
            skills_plugin=(plugins[0] if plugins and plugins[0] not in (None, "", "none", "all") else "caveman"),
            mcp_for_ablation=(mcp[0] if mcp and mcp[0] not in (None, "", "none", "all") else "repomix"),
        )
        ablation_result = ablation.run()

    report = runner.run()

    if args.junit_xml:
        from metrics.junit_exporter import export_junit_xml

        export_junit_xml(report.results, args.junit_xml, suite_name=report.config.name)

    # Convert to Core BenchmarkReport for modern reporting subsystems
    from core.types import BenchmarkReport as CoreReport
    from core.types import CellSummary as CoreCellSummary
    from core.types import MetricSummary as CoreMetricSummary

    core_report = CoreReport(
        run_id=report.run_id,
        name=report.config.name,
        started_at=report.started_at,
        finished_at=report.finished_at,
        config=report.to_dict().get("config", {}),
        summaries=[
            CoreCellSummary(
                harness=s["harness"],
                benchmark=s["benchmark"],
                plugins=s["plugins"],
                mcp_servers=s["mcp_servers"],
                summary=CoreMetricSummary(**s["summary"]),
            )
            for s in report.metric_summaries
        ],
        results=report.results,
    )

    if args.scorecard or output_format == "scorecard":
        from reporting.scorecard import ScorecardGenerator

        print(ScorecardGenerator.render_markdown_leaderboard(core_report))
        print()
        print(ScorecardGenerator.render_task_drilldown_table(core_report))
    elif output_format == "json":
        print(render_json(report))
    elif output_format == "markdown":
        print(render_markdown(report))
    elif output_format == "github-summary":
        print(render_github_summary(report))

    if args.ab_test:
        from reporting.ab_comparator import ABComparator

        baselines = [s for s in core_report.summaries if not s.plugins and not s.mcp_servers]
        treatments = [s for s in core_report.summaries if s.plugins or s.mcp_servers]
        ab_diffs = []
        for b in baselines:
            for t in treatments:
                if b.harness == t.harness and b.benchmark == t.benchmark:
                    ab_diffs.append(ABComparator.compare_cells(b, t))
        if ab_diffs:
            print()
            print(ABComparator.render_ab_markdown_table(ab_diffs))

    if args.publish_issue:
        from reporting.github_issue import GitHubIssuePublisher

        issue_url = GitHubIssuePublisher.publish_issue(core_report)
        if issue_url:
            print(f"::notice::Published benchmark report to GitHub Issue: {issue_url}")
        else:
            print("::warning::Could not publish GitHub Issue (check gh auth status)")

    if ablation_result is not None and ablation_result.report is not None:
        from evaluation.ablation import AblationEngine

        print()
        print(AblationEngine.render_ablation_markdown(ablation_result.report))

    if args.minimum_task_score is not None:
        floor = float(args.minimum_task_score)
        failed_cells = []
        for cell in report.metric_summaries:
            rate = cell.get("summary", {}).get("pass_rate", 0.0)
            if rate < floor:
                failed_cells.append((cell.get("harness"), cell.get("benchmark"), rate))
        if failed_cells:
            for h, b, r in failed_cells:
                print(
                    f"::error::Score floor failed for {h} on {b}: {r * 100:.1f}% < {floor * 100:.1f}%", file=sys.stderr
                )
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
