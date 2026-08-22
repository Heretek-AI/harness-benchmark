# Harness Benchmark: Audit Assessment & Strategic Roadmap

> Synthesized from Gemini's "Technical Audit and Next-Generation Evaluation Architecture" (August 2026), cross-referenced against the live codebase state on `main`.

---

## 1. Audit Assessment — Claim-by-Claim Verification

| # | Audit Claim | Codebase Reality | Verdict |
|---|---|---|---|
| 1 | **bwrap sandboxing exists** (Agent 4.2) | `_wrap_with_bwrap()` in `agents/base.py:283` — toggle via `HARNESS_BENCH_USE_BWRAP`, graceful fallback if missing | ✅ EXISTS |
| 2 | **MCP/Plugin registries** (Agent 4.3) | `mcp/mcp_registry.json` (6 servers) + `plugins/registry.json` (8 plugins), both with JSON Schemas | ✅ EXISTS |
| 3 | **A/B testing with McNemar + bootstrap CI** (§4.4) | `evaluation/statistics.py` has `mcnemar_test()` + `bootstrap_ci()`. `--ab-test` flag in `run_benchmark.py`. `AblationRunner` does 5-tier paired comparisons. | ✅ EXISTS |
| 4 | **Token usage extraction** | `extract_token_usage()` in `agents/base.py:412`, parses JSONL streams. `metrics/collector.py` aggregates. | ✅ EXISTS |
| 5 | **5-tier deterministic ablation** (§4.5) | `AblationRunner` in `evaluation/ablation_runner.py` — `tier_0_bare` through `tier_4_full_stack` with plugins/mcp/lsp toggles | ✅ EXISTS |
| 6 | **Grafana dashboards, PTY monitoring** (Agent 4.2) | No Grafana integration found. No PTY-level process monitoring. Token telemetry is basic aggregate counts only. | ❌ MISSING |
| 7 | **Host OS PTY execution with kernel-level monitoring** (Agent 4.1) | The harness runs `subprocess.Popen`, not PTY allocation. No `openpty`/`pty.` usage. The audit conflates this repo with the broader Heretek ecosystem (heretek-claude-harness, herdr). | ⚠️ PARTIALLY ACCURATE — describes the ecosystem, not this repo |
| 8 | **Outcome-driven verification beyond exit codes** (§3.1.2) | `OracleEvaluator` does Python assert injection + shell verify commands. But: no file-system state inspection, no container state checks, no chained rubrics. | ⚠️ PARTIALLY EXISTS — basic oracle exists, advanced verification missing |
| 9 | **Harbor Task Standard** (§5.1) | No `tasks/` directory exists. Task definitions are inline in `BenchmarkSuite` subclasses (`terminal_bench_adapter.py`, `coder_eval_adapter.py`). No `instruction.md` / `Dockerfile` / `test.sh` format. | ❌ MISSING |
| 10 | **Network egress / iptables rules** (§3.1.3) | No iptables, no network isolation, no egress controls. bwrap exists but doesn't configure network namespaces. | ❌ MISSING |
| 11 | **Chained rubric interpreter** (§5.3) | Not implemented. `OracleEvaluator` is single-pass assert/shell only. | ❌ MISSING |
| 12 | **Model-as-a-judge layer** (§5.3) | Not implemented. `mcp_security_adapter.py` has a basic security scorer, but no general LLM-judge wrapper. | ❌ MISSING |
| 13 | **AST verification pipelines** (§5.3) | Not implemented. No tree-sitter or AST parsing for code structure validation. | ❌ MISSING |
| 14 | **Context-window management / truncation** (§3.1.4) | No truncation, compaction, or dynamic context management. The `headroom` plugin is referenced but lives in `review/` (not active). | ❌ MISSING |
| 15 | **8-12 hour task schedulers** (§5.4) | `timeout` param exists but default is 120s. No long-horizon scheduling infrastructure. | ❌ MISSING |
| 16 | **e2b micro-VMs / Docker containers** (§5.2) | No e2b SDK integration. No Docker orchestration. Only bwrap (namespace-based, not container-based). | ❌ MISSING |
| 17 | **Benchmark taxonomy accuracy** (§3.2) | The table of 11 benchmarks (Terminal-Bench, SWE-bench Pro, NL2Repo, etc.) with SOTA scores appears well-researched and matches public leaderboards. | ✅ ACCURATE |

### Summary Scorecard

| Category | Status |
|---|---|
| Core ablation engine | ✅ Solid — 5-tier, paired A/B, McNemar + bootstrap |
| MCP/Plugin infrastructure | ✅ Solid — registries, schemas, dynamic loading |
| Token metrics & cost tracking | ✅ Solid — collector, cost table, composite scoring |
| Process execution isolation | ⚠️ Partial — bwrap exists, but no network/PTY isolation |
| Verification depth | ⚠️ Basic — Python/shell oracles only |
| Task standardization | ❌ No Harbor format, tasks are code-defined |
| Observability stack | ❌ No Grafana, no structured telemetry export |
| Model-as-judge / rubric engine | ❌ Not started |
| Long-horizon support | ❌ Not started |

---

## 2. Strategic Roadmap

The audit's three-phase structure is sound. Below is a concrete, prioritized roadmap that adapts it to the actual codebase state — building on what exists rather than rewriting from scratch.

---

### Phase 1: Hardening & Task Standardization (4-6 weeks)

**Goal:** Fix the foundation. Make the existing engine reproducible and prepare it for multi-domain benchmarks.

| Priority | Work Item | Effort | Depends On |
|---|---|---|---|
| P0 | **Harbor Task Format Loader** — Parse `instruction.md` + `Dockerfile` + `test.sh` + oracle from a directory. Add `tasks/` directory with 3-5 sample tasks in Harbor format. Register in `benchmarks/`. | 2 weeks | — |
| P0 | **Network Isolation via bwrap** — Extend `_wrap_with_bwrap()` to optionally add `--unshare-net` for network-namespace isolation. Add `--ro-bind /usr` + `--tmpfs /tmp` hardening. Env toggle: `HARNESS_BENCH_NETWORK_ISOLATION=1`. | 1 week | — |
| P0 | **Oracle Evaluator v2** — Add file-system state verification (check file existence, content hash, directory structure post-run). Add `verify_files: [...]` spec to Harbor tasks. | 1 week | Harbor format |
| P1 | **Structured Telemetry Export** — Emit per-task JSONL events: `task_start`, `tool_use`, `token_usage`, `task_end`. Write to `results/<run-id>/telemetry.jsonl`. No Grafana yet — just structured logs that a future Grafana pipeline can consume. | 1 week | — |
| P1 | **Deterministic Constraint Checker** — Text auditor for IFBench-style tasks: regex match, word-count bounds, forbidden-token lists. Integrates into `OracleEvaluator`. | 1 week | — |
| P2 | **Process Tree Monitoring** — Replace `subprocess.Popen` with PTY-aware execution (Python `pty` module or `script`). Capture TTY output separately from stdout. Enables terminal-state categorization (running/blocked/errored). | 2 weeks | — |

**Exit criteria:** 5 Harbor-format tasks passing. Network-isolated bwrap runs. File-state verification operational. Structured telemetry emitted.

---

### Phase 2: Multi-Domain Verification Engine (6-8 weeks)

**Goal:** Enable the harness to evaluate across diverse benchmark domains (coding, reasoning, office tasks, instruction following).

| Priority | Work Item | Effort | Depends On |
|---|---|---|---|
| P0 | **Chained Rubric Interpreter** — DAG-based evaluator for JobBench-style tasks. Each node is a binary rule; failure at node C_i zero-scores all downstream C_{i+k}. Config: `rubric.yaml` per task. | 2 weeks | Harbor format |
| P0 | **Model-as-a-Judge Wrapper** — `evaluation/judge.py`: call a separate LLM (configurable: Claude Opus, GPT-4o, etc.) to grade free-form outputs against a rubric. Returns score + rationale. Supports CoWorkBench, HLE, NL2Repo grading. | 2 weeks | — |
| P1 | **AST Verification Pipeline** — Tree-sitter based code structure validator. For NL2Repo tasks: verify that generated code has expected classes/functions/imports, compiles, and passes `ast.parse()`. | 1-2 weeks | — |
| P1 | **Hybrid Verification Router** — Auto-select verification strategy per task: Harbor shell tests for terminal tasks, AST + build for repo tasks, rubric interpreter for office tasks, model-judge for reasoning tasks. Config-driven via task manifest. | 1 week | All above |
| P2 | **CLI: `harness-bench ab-test --plugin <path>`** — Expose A/B testing as a standalone CLI command (currently buried in `run_benchmark.py` with `--ab-test`). Outputs McNemar p-value + bootstrap CI + iso-cost efficiency ratio. | 1 week | Existing stats module |

**Exit criteria:** Can evaluate Terminal-Bench (shell), NL2Repo (AST), JobBench (rubric), and CoWorkBench (judge) tasks in a single run. CLI for plugin A/B testing works.

---

### Phase 3: Observability, Long-Horizon & Enterprise Readiness (8-10 weeks)

**Goal:** Production-grade telemetry, extended execution support, and continuous validation.

| Priority | Work Item | Effort | Depends On |
|---|---|---|---|
| P0 | **Grafana Observability Pipeline** — Export structured telemetry (from Phase 1) to Grafana via OpenTelemetry or direct Prometheus push. Dashboards: token burn rate, tool-call latency, task success rate, cost per task. | 2-3 weeks | Structured telemetry |
| P0 | **Long-Horizon Task Scheduler** — Support 8-12 hour tasks. Implement checkpoint/resume: save intermediate state to disk, allow restart from last checkpoint. Heartbeat-based liveness detection. | 2-3 weeks | — |
| P1 | **Context-Window Management** — Implement truncation strategy: when context exceeds configurable threshold (e.g., 200K tokens), summarize older turns and inject summary as system message. Mode: `truncate`, `summarize`, `sliding_window`. | 2 weeks | — |
| P1 | **Continuous Validation Pipeline** — CI-integrated loop: run benchmark suite on schedule, flag tasks with high variance across repeat runs (avg@3 or avg@10), detect upstream dependency breaks. | 1-2 weeks | — |
| P2 | **e2b / Docker Sandbox Option** — Optional container-based isolation for tasks that need stronger guarantees than bwrap. Adds `execution_backend: bwrap | docker | e2b` to task manifest. | 2-3 weeks | Harbor format |
| P2 | **Differential Pass Rate Reporting** — Per-task ΔP tables with confidence intervals in the PDF report. Show which tasks improved/regressed between configurations. | 1 week | Existing statistics |

**Exit criteria:** Grafana dashboards live. 8-hour tasks run reliably. Context management prevents token overflow. CI pipeline catches regression within 24h.

---

## 3. Audit Critique — What Gemini Got Right and Wrong

### What the audit got right
1. **Accurate benchmark taxonomy** — The table of 11 modern benchmarks (Terminal-Bench 2.1, SWE-bench Pro, NL2Repo-Bench, DeepSWE 1.1, CoWorkBench, JobBench, IFBench, GPQA Diamond, HLE, LiveCodeBench v6) with SOTA scores and infrastructure requirements is well-researched and matches public data.
2. **Correct identification of the A/B testing methodology** — McNemar's test + bootstrap CI is the right statistical framework, and we already have it.
3. **The modular plugin/MCP architecture spec** is sound and aligns with what the codebase already does.
4. **The three-phase roadmap structure** is reasonable.

### What the audit got wrong or overstated
1. **"PTY allocation and kernel-level process monitoring"** — This describes the broader Heretek ecosystem (heretek-claude-harness, herdr), not this repo. The harness uses `subprocess.Popen`, not PTY.
2. **"Grafana dashboards"** — Referenced as if they exist. They don't. The telemetry is basic JSON aggregation.
3. **"Host environment contamination"** — Overstated. The hermetic workspace (`/tmp/hb-claude-code-<id>`) + bwrap provide reasonable isolation for most tasks. It's not container-grade, but it's not "unpinned dependency drift" either.
4. **"Reward hacking"** — Valid concern but theoretical. No iptables needed for v1 — bwrap `--unshare-net` is sufficient for the current task set.
5. **Conflation of repos** — The audit mixes up features from `heretek-claude-harness` (the CLI multiplexer), `hermes-agent`, and this repo. The harness-benchmark is a benchmark runner, not the full Heretek runtime.

### Missing from the audit
- No mention of the existing `AblationRunner` 5-tier matrix — the audit treats ablation as something to build, but it already exists.
- No discussion of `evaluation/statistics.py` — McNemar + bootstrap are already implemented.
- No mention of `metrics/cost_table.py` or the composite scoring system.
- No assessment of test coverage (131 tests passing).

---

## 4. Recommended Priority Order

For maximum impact with minimum rework:

1. **Harbor Task Format** — Unlocks everything downstream. Without standardized tasks, verification engines have nothing to evaluate against.
2. **Network isolation** — Quick win. bwrap `--unshare-net` is 20 lines of code.
3. **Oracle v2 (file-state)** — High value. Current oracle is too basic for real benchmarks.
4. **Structured telemetry** — Enables all Phase 3 observability work.
5. **Model-as-judge** — Opens up 4+ benchmark domains (CoWorkBench, HLE, NL2Repo quality grading).
6. **Grafana pipeline** — Important for adoption but not blocking.

Defer: e2b/Docker (complexity not justified until bwrap proves insufficient), long-horizon scheduling (niche use case), context-window management (address when actual token overflow is observed).
