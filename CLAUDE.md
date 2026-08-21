# Claude Code Developer Guide: Harness Benchmark

This guide contains project context, architectural specifics, and workflow commands tailored for Anthropic's **Claude Code** CLI and related Anthropic assistant tooling.

---

## 1. Fast Reference & Commands

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the test suite
pytest -v

# 3. Run a quick smoke benchmark (hermetic stub, no LLM keys needed)
python run_benchmark.py --config configs/presets/smoke_test.yaml --harness stub --output-format markdown

# 4. Run a Claude Code evaluation against coder_eval with an MCP server
python run_benchmark.py \
  --harness claude-code \
  --benchmark coder_eval \
  --plugins none \
  --mcp chrome-devtools-mcp,context7,repomix \
  --tasks-limit 3 \
  --output-format github-summary
```

---

## 2. Claude Code Adapter Specifics

The adapter is implemented in [`agents/claude_code_adapter.py`](agents/claude_code_adapter.py).

### Key Mechanics:
- **Dynamic MCP Injection**:
  When `mcp_servers` are requested, the adapter dynamically builds a `mcp-config.json` file in the staging directory and invokes Claude Code with `--mcp-config <path>`.
- **Dynamic Plugin Mounting**:
  When Claude plugins (`caveman`, `claude-mem`, `ECC`, `graphify`, `headroom`, `ponytail`, `rtk`, `Understand-Anything`) are requested, `PluginLoader` stages them into a single directory passed via `--plugin-dir <path>`.
- **Verbose Log & Event Parsing**:
  Claude Code is invoked with `--verbose --print --output-format json`. The adapter parses the resulting JSONL stream:
  - `{"type": "usage", "input_tokens": ..., "output_tokens": ...}` -> extracted as `tokens_input` and `tokens_output`.
  - `{"type": "tool_use", "name": "..."}` -> aggregated into `tool_calls` dictionary.
- **Hermetic Lifecycle**:
  Every run receives a dedicated temporary workspace in `/tmp/hb-claude-code-<id>` which is cleaned up in `teardown()`.

---

## 3. Environment Variables

When running real benchmarks with Claude Code:
- `LLM_API`: LiteLLM or OpenAI-compatible endpoint URL.
- `LLM_KEY`: API Key for the target provider.
- `LLM_MODEL`: Model identifier (e.g., `claude-sonnet-4`, `claude-haiku-4-5`, `deepseek-chat`).
- `HARNESS_BENCH_MCP_REGISTRY`: Optional custom path to MCP server registry.
- `HARNESS_BENCH_PLUGIN_REGISTRY`: Optional custom path to plugin registry.
- `HARNESS_BENCH_PRICING_JSON`: Optional custom token pricing JSON file.

---

## 4. Code Conventions
- Python 3.11+ syntax with strict typing.
- Always use `pydantic.BaseModel` for persistent serializable data schemas.
- When adding new tests, place them under `tests/` and mirror existing module naming (`test_<module>.py`).
