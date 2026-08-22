# Gemini CLI & Antigravity Developer Guide: Harness Benchmark 2.0

This guide contains operational instructions, configuration specifications, and workflow commands tailored for Google's **Gemini CLI** and **Antigravity** coding assistants.

---

## 1. Quick Commands

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run unit and integration tests
pytest -v

# 3. Test Antigravity adapter with a synthetic smoke run
python run_benchmark.py --preset smoke_test --scorecard

# 4. Run 5-Tier Ablation Benchmark for Gemini CLI & Antigravity
python run_benchmark.py \
  --harness gemini-cli,antigravity-cli \
  --benchmark coder_eval,terminal-bench \
  --preset ablation_5tier \
  --scorecard \
  --ab-test \
  --debug
```

---

## 2. Antigravity & Gemini CLI Adapters

### Antigravity Adapter ([`agents/antigravity_adapter.py`](agents/antigravity_adapter.py))
- **Workspace Materialization**:
  Generates `.antigravity/config.json` inside the hermetic test workspace with endpoint and model parameters (`LLM_API`, `LLM_MODEL`).
- **CLI Invocation**:
  Executes `antigravity run <prompt>` inside the isolated task directory with merged environment variables.
- **5-Tier Ablation Support**:
  Supports standalone baseline `tier_0_bare`, LSP diagnostic loop `tier_1_lsp`, custom rule extensions `tier_2_skills`, external MCP tools `tier_3_mcp`, and Full Stack `tier_4_full_stack`.

### Gemini CLI Adapter ([`agents/gemini_cli_adapter.py`](agents/gemini_cli_adapter.py))
- **REST Translation Bridge**:
  Automatically spawns a local translation bridge ([`agents/gemini_bridge.py`](agents/gemini_bridge.py)) on localhost translating Gemini SDK requests to the target `LLM_API` endpoint with clean SSE stream termination.
- **MCP Extension Synthesis**:
  Generates `gemini-extension.json` containing registered MCP server definitions (`command`, `args`, `env`).
- **Headless Invocation & Tool Materialization**:
  Executes `gemini -p <prompt> --output-format json` with non-interactive flags (`CI=1`, `NO_COLOR=1`, `GEMINI_CLI_TRUST_WORKSPACE=true`) and automatically materializes emitted file and shell actions in the hermetic workspace.

---

## 3. Environment & Configuration

| Variable | Description |
|---|---|
| `LLM_API` | Target API base URL (LiteLLM, Google AI Studio, Vertex AI, or OpenAI proxy) |
| `LLM_KEY` | Authentication API key |
| `LLM_MODEL` | Unified model identifier (e.g., `gemini-2.5-pro`, `gemini-2.5-flash`) |
| `HARNESS_BENCH_MCP_REGISTRY` | Path to `mcp/mcp_registry.json` |
| `HARNESS_BENCH_PLUGIN_REGISTRY` | Path to `plugins/registry.json` |

---

## 4. Verification & Artifacts

All run outputs are persisted to `./runs/<run-id>/`:
- `result.json`: Full machine-readable benchmark report with pass rates, latency metrics, and costs.
- `REPORT.md`: GitHub-Flavored Markdown summary table with Leaderboards and A/B Deltas.
- `<harness>__<benchmark>__<task>.jsonl`: Detailed per-task execution trace.
- `badges/`: SVG status badges for repository displays.
