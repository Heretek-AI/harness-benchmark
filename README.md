# Harness Benchmark

A matrixed benchmark suite for AI coding harnesses (Claude Code, Gemini
CLI, OpenCode, DeepSeek, Antigravity), Claude plugins
(`caveman`, `claude-mem`, `ECC`, `graphify`, `headroom`, `ponytail`,
`rtk`, `Understand-Anything`), and MCP servers (`chrome-devtools-mcp`,
`codebase-memory-mcp`, `context7`, `repomix`) — run against the
benchmark suites [`coder_eval`](https://github.com/UiPath/coder_eval)
and `terminal-bench` under a controlled `LLM_API` / `LLM_KEY` /
`LLM_MODEL` envelope.

## Repository layout

```
agents/                # Harness adapters (one class per CLI)
benchmarks/            # Benchmark adapters + the runner
configs/               # Preset YAMLs + JSON schema for run configs
mcp/                   # MCP server registry + launcher
metrics/               # Pass@1 / latency / token / cost collector + Markdown reporter
plugins/               # Plugin registry + loader
tests/                 # pytest suite
.github/workflows/     # Matrixed benchmark.yml + benchmark-report.yml
run_benchmark.py       # CLI entrypoint
```

## Quickstart (local)

```bash
# Install once
pip install -r requirements.txt

# Run the smoke preset against the bundled stub harness
python run_benchmark.py --config configs/presets/smoke_test.yaml \
    --harness stub --output-format markdown

# Run a real sweep over Claude Code x coder_eval x every MCP, 3 tasks each
python run_benchmark.py \
    --harness claude-code \
    --benchmark coder_eval \
    --plugins none \
    --mcp chrome-devtools-mcp,codebase-memory-mcp,context7,repomix \
    --tasks-limit 3 \
    --output-format github-summary
```

The runner writes per-run artefacts to `./runs/<run-id>/`:

* `result.json` — the full structured report
* `REPORT.md` — Markdown comparison table (when `--output-format markdown` or `github-summary`)
* `<harness>__<benchmark>__<task>.jsonl` — per-task raw results for drill-down

## Required environment

| Var | Purpose |
|---|---|
| `LLM_API` | LiteLLM / OpenAI-compatible base URL |
| `LLM_KEY` | API key for that endpoint |
| `LLM_MODEL` | Model identifier used for every cell of the matrix |
| `HARNESS_BENCH_MCP_REGISTRY` | Optional override for the MCP registry path (defaults to `mcp/mcp_registry.json`) |
| `HARNESS_BENCH_PLUGIN_REGISTRY` | Optional override for the plugin registry path |
| `HARNESS_BENCH_PRICING_JSON` | Optional JSON file overriding the model-pricing table |

## CI

The `.github/workflows/benchmark.yml` workflow:

1. Triggers on `workflow_dispatch`, push to `main` (only when relevant paths
   change), and a nightly cron at 04:07 UTC.
2. Expands the (harness x benchmark x plugin x MCP) matrix in a setup job
   so the YAML itself stays static.
3. Runs every cell in parallel, uploading `runs/**/result.json` as a
   per-cell artifact.
4. Aggregates the results in a `report` job and writes the comparison
   table to `$GITHUB_STEP_SUMMARY`.

The required repository secrets are `LLM_API`, `LLM_KEY`, and `LLM_MODEL`.

To dispatch a one-off cell:

> Actions → Benchmark → Run workflow → set `harness=claude-code`,
> `benchmark=coder_eval`, `plugins=none`, `mcp_servers=context7`,
> `task_limit=3`.

## Adding a new harness

1. Subclass `BaseAgentAdapter` (in `agents/base.py`) and implement the
   three `_on_*` hooks.
2. Map the harness name to your class in `agents/__init__.py`
   (`ADAPTERS["my-harness"] = MyAdapter`).
3. Add the harness to `.github/workflows/benchmark.yml`'s `setup-matrix`
   job's expansion list.

That's it — the runner, plugin loader, and MCP launcher are all harness-
agnostic.

## Adding a new MCP server

Append an entry to `mcp/mcp_registry.json`:

```json
{
  "servers": {
    "my-mcp": {
      "display_name": "My MCP",
      "command": "npx",
      "args": ["-y", "my-mcp"],
      "env": {},
      "transport": "stdio"
    }
  }
}
```

The launcher spawns it as a stdio subprocess; the adapter reads the same
entry when synthesizing its harness-specific MCP config.

## Adding a new plugin

Append an entry to `plugins/registry.json`:

```json
{
  "plugins": {
    "my-plugin": {
      "display_name": "My Plugin",
      "source_path": "review/claude-plugins/my-plugin",
      "format": "claude-plugin",
      "injects": ["commands"]
    }
  }
}
```

`source_path` must point at a directory on disk; the loader symlinks it
into the staging root the adapter consumes.

## Adding a new benchmark

1. Subclass `BaseBenchmark` (in `benchmarks/base.py`).
2. Register it in `benchmarks/__init__.py`'s `REGISTRY`.

## Tests

```bash
pytest
```

The suite covers schema validation, the plugin loader's dir synthesis,
the MCP launcher's start/stop lifecycle, and an end-to-end runner
dry-run against the `stub` adapter.