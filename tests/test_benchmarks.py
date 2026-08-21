"""Tests for benchmark loaders, bundled datasets, and strict grading."""

from __future__ import annotations

from pathlib import Path

from agents.base import ExecutionResult
from benchmarks import CoderEvalAdapter, TerminalBenchAdapter, resolve_benchmark


def test_resolve_benchmarks() -> None:
    for name in ["coder_eval", "terminal-bench"]:
        bench = resolve_benchmark(name)
        assert bench.name == name


def test_coder_eval_bundled_tasks() -> None:
    bench = CoderEvalAdapter()
    tasks = list(bench.iter_tasks())
    assert len(tasks) >= 10
    task_ids = [t.task_id for t in tasks]
    assert "ce-py-001" in task_ids
    assert "ce-py-002" in task_ids


def test_terminal_bench_bundled_tasks() -> None:
    bench = TerminalBenchAdapter()
    tasks = list(bench.iter_tasks())
    assert len(tasks) >= 10
    task_ids = [t.task_id for t in tasks]
    assert "tb-sh-001" in task_ids
    assert "tb-sh-002" in task_ids


def test_coder_eval_strict_grading() -> None:
    bench = CoderEvalAdapter()

    # Pass: exit_code 0 and stdout contains expected
    res_pass = ExecutionResult(
        harness="stub",
        benchmark="coder_eval",
        task_id="ce-py-001",
        plugins=[],
        mcp_servers=[],
        exit_code=0,
        duration_seconds=1.0,
        stdout="The result is 55",
        stderr="",
    )
    assert bench.grade(res_pass, {"stdout_contains": "55"}) is True

    # Fail: crashed process with exit_code != 0 even if stdout contains expected
    res_crashed = ExecutionResult(
        harness="stub",
        benchmark="coder_eval",
        task_id="ce-py-001",
        plugins=[],
        mcp_servers=[],
        exit_code=2,
        duration_seconds=0.1,
        stdout="Error: 55 not found [65..85]",
        stderr="unknown command",
    )
    assert bench.grade(res_crashed, {"stdout_contains": "55"}) is False

    # Pass: model returned valid python code block satisfying the output
    res_code = ExecutionResult(
        harness="stub",
        benchmark="coder_eval",
        task_id="ce-py-001",
        plugins=[],
        mcp_servers=[],
        exit_code=0,
        duration_seconds=1.0,
        stdout="```python\ndef fib(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a\nprint(fib(10))\n```",
        stderr="",
    )
    assert bench.grade(res_code, {"stdout_contains": "55"}) is True


def test_terminal_bench_strict_grading() -> None:
    bench = TerminalBenchAdapter()

    res_pass = ExecutionResult(
        harness="stub",
        benchmark="terminal-bench",
        task_id="tb-sh-001",
        plugins=[],
        mcp_servers=[],
        exit_code=0,
        duration_seconds=0.5,
        stdout="Created",
        stderr="",
    )
    assert bench.grade(res_pass, {"verify_cmd": "echo 'ok' > /dev/null"}) is True

    res_fail = ExecutionResult(
        harness="stub",
        benchmark="terminal-bench",
        task_id="tb-sh-001",
        plugins=[],
        mcp_servers=[],
        exit_code=1,
        duration_seconds=0.5,
        stdout="",
        stderr="Error",
    )
    assert bench.grade(res_fail, {"verify_cmd": "echo 'ok' > /dev/null"}) is False
