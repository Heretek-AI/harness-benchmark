# AI Coding Agent Guidelines for Harness Benchmark 2.0

This document provides architectural context, operational standards, and development guidelines for autonomous AI coding agents (such as Google Antigravity, Claude Code, Cursor, Windsurf, Aider, OpenCode, or Devin) operating within or extending this repository.

---

## 1. System Overview & Architecture

`harness-benchmark` is a standardized, matrix-based evaluation framework and turnkey GitHub Action designed to benchmark AI coding harnesses, Model Context Protocol (MCP) servers, Language Server Protocol (LSP) diagnostics, and plugin extensions under controlled LLM configurations (`LLM_API`, `LLM_KEY`, `LLM_MODEL`).

### Core Subsystems

```text
├── core/               # Core types (TaskSpec, ExecutionResult, AblationTier), logger, LSP diagnostics
├── extensions/         # UnifiedExtensionManager for plugins, skills, and MCP servers (stdio/SSE)
├── evaluation/         # Deterministic OracleEvaluator (coder_eval assertions & terminal_bench verifications), AblationEngine
├── reporting/          # Model Scorecards, A/B Delta Engine, Date-Labeled GitHub Issue Publisher, JUnit XML
├── agents/             # Harness adapters implementing BaseAgentAdapter lifecycle
├── benchmarks/         # Benchmark adapters (coder_eval, terminal-bench) & BenchmarkRunner
├── configs/            # JSON Schema and preset matrix configurations (YAML)
├── metrics/            # Metric collection (Pass@1, latency, tokens, cost, failures) & SVG Badges
└── run_benchmark.py    # Main CLI entrypoint
```

---

## 2. The 5-Tier Deterministic Ablation Model

When designing evaluation matrices, always consider the 5 standard ablation tiers:

1. **`tier_0_bare` (Bare Agent Baseline)**: Pure model reasoning without external tools, skills, LSP, or MCP.
2. **`tier_1_lsp` (+ Language Server Protocol)**: Deterministic compiler/language server AST diagnostic feedback loops enabled (`core/lsp.py`).
3. **`tier_2_skills` (+ Skills / Plugins)**: Static prompt modules, rule harnesses, and local utility plugins enabled (`plugins/`).
4. **`tier_3_mcp` (+ Model Context Protocol)**: Isolated external dynamic tools (e.g., `repomix`, `context7`, `github-mcp`) enabled (`mcp/`).
5. **`tier_4_full_stack` (Full Stack Augmentation)**: Combined Tier 1 + Tier 2 + Tier 3 configuration.

---

## 2.5 Prerequisites — the `review/` workspace

The plugin and MCP catalogs (`plugins/registry.json`, `mcp/mcp_registry.json`) reference source paths under a gitignored `review/` workspace. Clone the upstream repos into `review/` before running matrix sweeps that load real plugins/MCPs. The `smoke_test` preset and `stub` / `agent-engine` harnesses do **not** require this workspace. Example clone commands live in the README's `## ⚙️ Prerequisites` section.

## 3. Engineering Conventions & Standards
- Use Python 3.11+ type hints (`from __future__ import annotations`).
- Use `pydantic.BaseModel` for data contracts that serialize to/from JSON artifacts (`ExecutionResult`, `TaskSpec`, `MetricSummary`, `ABComparisonResult`, `MultiTierAblationReport`).
- Ensure all public functions and methods include descriptive docstrings and precise type signatures.

### Subprocess Safety & Process Hygiene
- Always track child process PIDs inside `AdapterContext.child_pids` or `MCPServerHandle`.
- In `teardown()`, terminate subprocesses gracefully before escalating to `SIGKILL` (`kill(9)`).
- Handle `subprocess.TimeoutExpired` and `FileNotFoundError` gracefully, returning an `ExecutionResult` with `exit_code=-1` and `failure_category="command_timeout"` rather than crashing the benchmark orchestrator.

### Hermetic Workspaces
- Never execute harness tasks or write temporary configs inside the repository root.
- Always use `tempfile.mkdtemp(prefix="hb-...")` for adapter staging directories and clean them up in `teardown()`.

---

## 4. Common Development Commands

### Running Unit & Integration Tests
```bash
pytest -v
```

### Running Test Presets Locally
```bash
# Smoke test preset with mock stub adapter (no API keys required)
python run_benchmark.py --preset smoke_test --scorecard

# Multi-benchmark execution with 5-tier ablation matrix
python run_benchmark.py --preset ablation_5tier --ab-test --debug
```

### Code Style & Linting
```bash
ruff check .
ruff format --check .
```

---

## 5. How to Extend the Benchmark Suite

### Adding a New Harness
1. Create `agents/<harness>_adapter.py` subclassing `BaseAgentAdapter`.
2. Implement `_on_setup`, `_build_command`, and `resolve_cli`.
3. Register the adapter in `agents/__init__.py` (`ADAPTERS["<harness>"] = ...`).
4. Add unit tests in `tests/test_adapters.py`.

### Adding a New MCP Server
1. Append the server specification to `mcp/mcp_registry.json`.
2. Specify `command`, `args`, `env`, and `transport` (`stdio` or `sse`).
3. Verify with `pytest tests/test_mcp_launcher.py`.

### Adding a New Plugin / Skill
1. Append the plugin metadata to `plugins/registry.json`.
2. Specify `source_path`, `format`, and `injects` (`commands`, `agents`, `hooks`).
3. Verify directory staging with `pytest tests/test_plugin_loader.py`.
