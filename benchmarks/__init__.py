"""Re-exports."""

from benchmarks.base import BaseBenchmark, JSONManifestBenchmark, TaskSpec
from benchmarks.coder_eval_adapter import CoderEvalAdapter
from benchmarks.terminal_bench_adapter import TerminalBenchAdapter

REGISTRY: dict[str, type[BaseBenchmark]] = {
    "coder_eval": CoderEvalAdapter,
    "terminal-bench": TerminalBenchAdapter,
}


def resolve_benchmark(name: str) -> BaseBenchmark:
    try:
        return REGISTRY[name]()
    except KeyError as exc:
        raise KeyError(f"unknown benchmark {name!r}; known: {sorted(REGISTRY)}") from exc


__all__ = [
    "REGISTRY",
    "BaseBenchmark",
    "CoderEvalAdapter",
    "JSONManifestBenchmark",
    "TaskSpec",
    "TerminalBenchAdapter",
    "resolve_benchmark",
]
