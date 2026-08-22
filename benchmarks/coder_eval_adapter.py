"""Adapter for the ``coder_eval`` benchmark suite.

Evaluates coding capabilities against coding problem manifests (derived from
https://github.com/UiPath/coder_eval). Each task provides a natural-language
prompt and assertion criteria.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from agents.base import ExecutionResult
from benchmarks.base import JSONManifestBenchmark, TaskSpec


class CoderEvalAdapter(JSONManifestBenchmark):
    name = "coder_eval"
    source_path = Path(__file__).parent / "data" / "coder_eval"

    def _synthetic_tasks(self) -> list[TaskSpec]:
        return [
            TaskSpec(
                task_id="ce-py-smoke-001",
                prompt=(
                    "Write a Python function `add(a, b)` that returns the "
                    "sum of a and b. Print the result of add(2, 3)."
                ),
                expected={"stdout_contains": "5"},
            )
        ]

    def _grade_expected(
        self,
        result: ExecutionResult,
        expected: dict,
        cwd: Path | None = None,
    ) -> bool:
        if result.exit_code != 0:
            return False

        stdout = result.stdout or ""

        # Rigorous Oracle Unit Test Assertions
        if "test_asserts" in expected:
            asserts = expected["test_asserts"].strip()
            fn_name = expected.get("function_name")

            # Gather candidate Python implementations from workspace files & stdout
            candidates: list[str] = []

            # 1. Any Python files created in workspace cwd
            if cwd is not None and cwd.exists():
                for py_file in cwd.glob("**/*.py"):
                    try:
                        content = py_file.read_text()
                        if fn_name is None or f"def {fn_name}" in content:
                            candidates.append(content)
                    except Exception:
                        pass

            # 2. Markdown Python code blocks in stdout
            code_blocks = re.findall(r"```(?:python|py)?\s*([\s\S]*?)```", stdout)
            for block in code_blocks:
                b = block.strip()
                if b and (fn_name is None or f"def {fn_name}" in b):
                    candidates.append(b)

            # 3. XML file write content blocks (e.g. <content>...</content>)
            xml_blocks = re.findall(r"<content>([\s\S]*?)</content>", stdout)
            for block in xml_blocks:
                b = block.strip()
                if b and (fn_name is None or f"def {fn_name}" in b):
                    candidates.append(b)

            # 4. Raw stdout as fallback if it defines the function
            if fn_name and f"def {fn_name}" in stdout:
                candidates.append(stdout)

            # Execute test assertions against each candidate implementation in an isolated subprocess
            for code in candidates:
                test_script = f"{code}\n\n{asserts}\n"
                try:
                    proc = subprocess.run(
                        [sys.executable, "-c", test_script],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        cwd=cwd,
                    )
                    if proc.returncode == 0:
                        return True
                except (subprocess.TimeoutExpired, Exception):
                    continue

            return False

        if "stdout_contains" in expected:
            target = str(expected["stdout_contains"]).strip()
            # If target in stdout, check if code runs correctly
            code_blocks = re.findall(r"```(?:python|py)?\s*([\s\S]*?)```", stdout)
            for code in code_blocks:
                try:
                    proc = subprocess.run(
                        [sys.executable, "-c", code.strip()],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if proc.returncode == 0 and target in proc.stdout:
                        return True
                except Exception:
                    continue
            return target in stdout

        if "exit_code" in expected:
            return result.exit_code == expected["exit_code"]

        return result.exit_code == 0