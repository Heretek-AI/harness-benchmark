"""Rich real-time execution logger for Harness Benchmark 2.0."""

from __future__ import annotations

import datetime
import os
import sys


class BenchmarkLogger:
    """Colored, structured terminal logger for benchmark execution."""

    # ANSI Colors
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    def __init__(self, debug: bool = False, quiet: bool = False) -> None:
        self.debug_mode = debug or (os.environ.get("HARNESS_BENCH_DEBUG") == "1")
        self.quiet = quiet
        self.no_color = os.environ.get("NO_COLOR") == "1" or not sys.stdout.isatty()

    def _c(self, text: str, color: str) -> str:
        if self.no_color:
            return text
        return f"{color}{text}{self.RESET}"

    def _ts(self) -> str:
        now = datetime.datetime.now().strftime("%H:%M:%S")
        return self._c(f"[{now}]", self.DIM)

    def banner(self, title: str) -> None:
        if self.quiet:
            return
        line = "═" * 70
        print(f"\n{self._c(line, self.CYAN)}")
        print(f" {self._c(self.BOLD + title, self.WHITE)}")
        print(f"{self._c(line, self.CYAN)}\n")

    def cell_start(self, harness: str, benchmark: str, plugins: list[str], mcp: list[str], tasks_count: int) -> None:
        if self.quiet:
            return
        p_str = ",".join(plugins) if plugins else "none"
        m_str = ",".join(mcp) if mcp else "none"
        msg = f"CELL: {self._c(harness, self.BOLD + self.CYAN)} | {self._c(benchmark, self.YELLOW)} | plugins=[{p_str}] mcp=[{m_str}] | tasks={tasks_count}"
        print(f"{self._ts()} 🚀 {msg}")

    def task_start(self, task_id: str, prompt: str) -> None:
        if self.quiet:
            return
        prompt_snippet = prompt.replace("\n", " ")[:80] + ("..." if len(prompt) > 80 else "")
        print(f'{self._ts()}   ▶ Task {self._c(task_id, self.BOLD + self.WHITE)}: "{prompt_snippet}"')

    def agent_turn(self, turn: int, tool_name: str | None = None, args_summary: str | None = None) -> None:
        if not self.debug_mode or self.quiet:
            return
        if tool_name:
            args_str = f"({args_summary})" if args_summary else "()"
            print(f"{self._ts()}     🤖 Turn {turn}: Invoked tool {self._c(tool_name + args_str, self.BLUE)}")
        else:
            print(f"{self._ts()}     🤖 Turn {turn}: Model reasoning")

    def oracle_check(self, task_id: str, result: bool, detail: str | None = None) -> None:
        if not self.debug_mode or self.quiet:
            return
        status = self._c("PASSED", self.GREEN) if result else self._c("FAILED", self.RED)
        d_str = f" ({detail})" if detail else ""
        print(f"{self._ts()}     ⚖️  Oracle evaluation: {status}{d_str}")

    def task_finish(
        self,
        task_id: str,
        passed: bool,
        duration: float,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        tool_calls: int = 0,
    ) -> None:
        if self.quiet:
            return
        status_tag = self._c("PASS", self.BOLD + self.GREEN) if passed else self._c("FAIL", self.BOLD + self.RED)
        tok_str = f"{tokens_in or 0}/{tokens_out or 0} toks"
        print(
            f"{self._ts()}   🏁 Task {self._c(task_id, self.WHITE)} -> {status_tag} "
            f"({duration:.2f}s, {tok_str}, {tool_calls} tools)"
        )

    def debug(self, msg: str) -> None:
        if self.debug_mode and not self.quiet:
            print(f"{self._ts()} {self._c('[DEBUG]', self.MAGENTA)} {msg}")

    def info(self, msg: str) -> None:
        if not self.quiet:
            print(f"{self._ts()} {self._c('[INFO]', self.CYAN)} {msg}")

    def warning(self, msg: str) -> None:
        print(f"{self._ts()} {self._c('⚠️  [WARN]', self.YELLOW)} {msg}")

    def error(self, msg: str) -> None:
        print(f"{self._ts()} {self._c('❌ [ERROR]', self.RED)} {msg}", file=sys.stderr)


# Global default logger instance
logger = BenchmarkLogger()
