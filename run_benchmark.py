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
import json
import logging
import os
import sys
from pathlib import Path

import yaml

# Allow ``python run_benchmark.py`` to import the package modules without
# the user needing ``pip install -e .`` first.
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.runner import BenchmarkRunner, RunConfig
from mcp import MCPLauncher
from metrics import render_github_summary, render_json, render_markdown
from plugins import PluginLoader


def _split_csv(value: str) -> list[str]:
    if not value:
        return []
    if value.strip() in ("none", "all"):
        return [value.strip()]
    return [v.strip() for v in value.split(",") if v.strip()]


def _load_preset(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _resolve_registry_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    plugin_registry = Path(
        args.plugin_registry
        or os.environ.get("HARNESS_BENCH_PLUGIN_REGISTRY")
        or REPO_ROOT / "plugins" / "registry.json"
    )
    mcp_registry = Path(
        args.mcp_registry
        or os.environ.get("HARNESS_BENCH_MCP_REGISTRY")
        or REPO_ROOT / "mcp" / "mcp_registry.json"
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
    parser.add_argument("--config", type=Path, help="Preset YAML to load")
    parser.add_argument(
        "--harness",
        default="all",
        help="Comma-separated harness names, 'all', or 'none' (run without harness).",
    )
    parser.add_argument(
        "--benchmark",
        default="all",
        help="Comma-separated benchmark names, 'all', or 'none'.",
    )
    parser.add_argument(
        "--plugins",
        default="none",
        help="Comma-separated plugin names, 'all', or 'none'.",
    )
    parser.add_argument(
        "--mcp",
        dest="mcp_servers",
        default="none",
        help="Comma-separated MCP server names, 'all', or 'none'.",
    )
    parser.add_argument("--tasks-limit", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument(
        "--output-format",
        choices=["json", "markdown", "github-summary"],
        default="json",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("runs"))
    parser.add_argument(
        "--name", default="ad-hoc", help="Run name; becomes the run-id prefix."
    )
    parser.add_argument(
        "--plugin-registry", type=Path, help="Override plugins/registry.json path"
    )
    parser.add_argument(
        "--mcp-registry", type=Path, help="Override mcp/mcp_registry.json path"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Preset YAML wins for anything it sets; CLI flags override.
    preset = _load_preset(args.config) if args.config else {}

    harness = _split_csv(str(args.harness))
    benchmark = _split_csv(str(args.benchmark))
    plugins = _split_csv(str(args.plugins))
    mcp = _split_csv(str(args.mcp_servers))

    config = RunConfig(
        name=args.name,
        harness=harness,
        benchmark=benchmark,
        plugins=plugins,
        mcp_servers=mcp,
        tasks_limit=args.tasks_limit or int(preset.get("tasks_limit", 0) or 0),
        timeout_seconds=args.timeout or int(preset.get("timeout_seconds", 600)),
        output_format=args.output_format,
        output_dir=args.output_dir,
    )

    plugin_registry, mcp_registry = _resolve_registry_paths(args)
    plugin_loader = PluginLoader(plugin_registry)
    mcp_launcher = MCPLauncher(mcp_registry)

    runner = BenchmarkRunner(config, plugin_loader, mcp_launcher)
    report = runner.run()

    # Also print to stdout for ad-hoc local debugging; the per-run files
    # are the durable artefacts.
    if args.output_format == "json":
        print(render_json(report))
    elif args.output_format == "markdown":
        print(render_markdown(report))
    elif args.output_format == "github-summary":
        print(render_github_summary(report))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())