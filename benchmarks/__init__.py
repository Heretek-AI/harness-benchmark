"""Re-exports."""

from pathlib import Path

from benchmarks.base import BaseBenchmark, JSONManifestBenchmark, TaskSpec
from benchmarks.coder_eval_adapter import CoderEvalAdapter
from benchmarks.harbor_adapter import HarborBenchmark
from benchmarks.mcp_security_adapter import MCPSecurityAdapter
from benchmarks.terminal_bench_adapter import TerminalBenchAdapter

# Harbor requires a path, so it's registered separately.
HARBOR_DEFAULT_PATH = Path(__file__).parent.parent / "tasks"

REGISTRY: dict[str, type[BaseBenchmark]] = {
    "coder_eval": CoderEvalAdapter,
    "terminal-bench": TerminalBenchAdapter,
    "mcp-security": MCPSecurityAdapter,
}


def resolve_benchmark(name: str, dataset_path: str | Path | None = None) -> BaseBenchmark:
    if name == "harbor":
        path = Path(dataset_path) if dataset_path else HARBOR_DEFAULT_PATH
        return HarborBenchmark(path)
    try:
        return REGISTRY[name]()
    except KeyError as exc:
        raise KeyError(f"unknown benchmark {name!r}; known: {sorted(REGISTRY)}") from exc


__all__ = [
    "REGISTRY",
    "BaseBenchmark",
    "CoderEvalAdapter",
    "HarborBenchmark",
    "JSONManifestBenchmark",
    "MCPSecurityAdapter",
    "TaskSpec",
    "TerminalBenchAdapter",
    "resolve_benchmark",
]
