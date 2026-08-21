# AI Coding Agent Guidelines for Harness Benchmark

This document provides architectural context, development standards, and operational guidelines for autonomous AI coding agents (such as Google Antigravity, Claude Code, Cursor, Windsurf, Aider, OpenCode, or Devin) working within this repository.

---

## 1. System Overview & Architecture

`harness-benchmark` is a standardized, matrix-based evaluation framework designed to benchmark AI coding harnesses, Model Context Protocol (MCP) servers, and plugin extensions under controlled LLM configurations (`LLM_API`, `LLM_KEY`, `LLM_MODEL`).

### Core Subsystems

```text
├── agents/             # Harness adapters implementing BaseAgentAdapter lifecycle
├── benchmarks/         # Benchmark adapters (coder_eval, terminal-bench) & BenchmarkRunner
├── plugins/            # Catalog (registry.json) & staging synthesis (PluginLoader)
├── mcp/                # Server catalog (mcp_registry.json) & process manager (MCPLauncher)
├── configs/            # JSON Schema and preset matrix configurations (YAML)
├── metrics/            # Metric collection (Pass@1, latency, tokens, cost) & Markdown reporting
├── tests/              # Pytest unit, integration, and schema validation test suite
└── run_benchmark.py    # Main CLI entrypoint
```

### Execution Flow

1. **CLI / Config Resolution**: `run_benchmark.py` parses CLI flags or loads a preset YAML (`configs/presets/*.yaml`).
2. **Matrix Expansion**: `BenchmarkRunner` computes the cartesian product of `(harness x benchmark x plugins x mcp_servers)`.
3. **Setup Phase**:
   - `PluginLoader.synthesize_agent_config()` builds a hermetic staging root of requested plugins.
   - `MCPLauncher.launch()` spawns requested stdio/SSE MCP subprocesses.
   - `BaseAgentAdapter.setup()` initializes a temporary workspace and materializes harness-specific configs.
4. **Execution & Grading Phase**:
   - `BaseBenchmark.iter_tasks()` yields tasks with prompts and evaluation criteria.
   - `BaseAgentAdapter.execute_task()` invokes the harness subprocess with timeout tracking.
   - `BaseBenchmark.grade()` evaluates the outcome against expected criteria.
   - `MetricCollector.record()` aggregates latency, exit codes, token usage, and tool invocations.
5. **Teardown & Reporting**:
   - `BaseAgentAdapter.teardown()` cleans up scratch files and child processes.
   - `MCPLauncher.terminate()` safely kills MCP server subprocesses.
   - Results are written to `runs/<run-id>/result.json`, `REPORT.md`, and per-task `.jsonl` files.

---

## 2. Engineering Conventions & Standards

### Type Safety & Validation
- Use Python 3.11+ type hints (`from __future__ import annotations`).
- Use `pydantic.BaseModel` for data contracts that serialize to/from JSON artifacts (`ExecutionResult`, `TaskSpec`, `PluginSpec`).
- Ensure all public functions and methods include descriptive docstrings and precise type signatures.

### Subprocess Safety & Process Hygiene
- Always track child process PIDs inside `AdapterContext.child_pids` or `MCPServerHandle`.
- In `teardown()`, terminate subprocesses gracefully before escalating to `SIGKILL` (`kill(9)`).
- Handle `subprocess.TimeoutExpired` and `FileNotFoundError` gracefully, returning an `ExecutionResult` with `exit_code=-1` rather than crashing the benchmark orchestrator.

### Hermetic Workspaces
- Never execute harness tasks or write temporary configs inside the repository root.
- Always use `tempfile.mkdtemp(prefix="hb-...")` for adapter staging directories and cleans them up in `teardown()`.

---

## 3. Common Development Commands

### Running Unit & Integration Tests
```bash
pytest -v
```

### Running Test Presets Locally
```bash
# Smoke test preset with mock stub adapter (no API keys required)
python run_benchmark.py --config configs/presets/smoke_test.yaml --harness stub --output-format markdown

# Multi-benchmark execution with stub adapter
python run_benchmark.py --harness stub --benchmark coder_eval,terminal-bench --plugins none --mcp none --tasks-limit 1 --output-format json
```

### Code Style & Linting
```bash
ruff check .
ruff format --check .
```

---

## 4. How to Extend the Benchmark Suite

### Adding a New Harness
1. Create `agents/<harness>_adapter.py` subclassing `BaseAgentAdapter`.
2. Implement `_on_setup`, `_build_command`, and `resolve_cli`.
3. Register the adapter in `agents/__init__.py` (`ADAPTERS["<harness>"] = ...`).
4. Add unit tests in `tests/test_adapters.py`.

### Adding a New MCP Server
1. Append the server specification to `mcp/mcp_registry.json`.
2. Specify `command`, `args`, `env`, and `transport` (`stdio` or `sse`).
3. Verify with `pytest tests/test_mcp_launcher.py`.

### Adding a New Plugin
1. Append the plugin metadata to `plugins/registry.json`.
2. Specify `source_path`, `format`, and `injects` (`commands`, `agents`, `hooks`).
3. Verify directory staging with `pytest tests/test_plugin_loader.py`.
