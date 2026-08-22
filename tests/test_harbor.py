"""Tests for the Harbor Task Format adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmarks.harbor_adapter import HarborBenchmark, HarborTaskDir
from agents.base import ExecutionResult


TASKS_DIR = Path(__file__).resolve().parents[1] / "tasks"


class TestHarborTaskDir:
    """Test HarborTaskDir parsing."""

    def test_parse_valid_task(self) -> None:
        task_dir = TASKS_DIR / "add-numbers"
        if not task_dir.exists():
            pytest.skip("tasks/ directory not found")
        htd = HarborTaskDir.from_directory(task_dir)
        assert htd is not None
        assert htd.task_id == "add-numbers"
        assert "Add Two Numbers" in htd.instruction
        assert "test.sh" in htd.test_script or "python3" in htd.test_script
        assert htd.verify_files is not None

    def test_parse_nonexistent_returns_none(self, tmp_path: Path) -> None:
        assert HarborTaskDir.from_directory(tmp_path / "nope") is None

    def test_parse_incomplete_dir_returns_none(self, tmp_path: Path) -> None:
        d = tmp_path / "incomplete"
        d.mkdir()
        (d / "instruction.md").write_text("# Task")
        # Missing test.sh
        assert HarborTaskDir.from_directory(d) is None

    def test_to_task_spec(self) -> None:
        task_dir = TASKS_DIR / "create-file"
        if not task_dir.exists():
            pytest.skip("tasks/ directory not found")
        htd = HarborTaskDir.from_directory(task_dir)
        assert htd is not None
        spec = htd.to_task_spec()
        assert spec.task_id == "create-file"
        assert "greeting.txt" in spec.prompt
        assert "test_script" in spec.expected
        assert "verify_files" in spec.expected


class TestHarborBenchmark:
    """Test HarborBenchmark task loading and grading."""

    def test_discover_all_tasks(self) -> None:
        if not TASKS_DIR.exists():
            pytest.skip("tasks/ directory not found")
        bench = HarborBenchmark(TASKS_DIR)
        tasks = list(bench.iter_tasks())
        assert len(tasks) >= 3, f"Expected at least 3 tasks, got {len(tasks)}"
        ids = {t.task_id for t in tasks}
        assert "add-numbers" in ids
        assert "create-file" in ids
        assert "sort-list" in ids

    def test_limit_tasks(self) -> None:
        if not TASKS_DIR.exists():
            pytest.skip("tasks/ directory not found")
        bench = HarborBenchmark(TASKS_DIR)
        tasks = list(bench.iter_tasks(limit=1))
        assert len(tasks) == 1

    def test_single_task_dir(self) -> None:
        task_dir = TASKS_DIR / "add-numbers"
        if not task_dir.exists():
            pytest.skip("tasks/ directory not found")
        bench = HarborBenchmark(task_dir)
        tasks = list(bench.iter_tasks())
        assert len(tasks) == 1
        assert tasks[0].task_id == "add-numbers"

    def test_grade_passes_on_exit_zero(self) -> None:
        result = ExecutionResult(
            task_id="test",
            harness="stub",
            benchmark="harbor",
            stdout="done",
            stderr="",
            exit_code=0,
            duration_seconds=1.0,
        )
        bench = HarborBenchmark(TASKS_DIR if TASKS_DIR.exists() else Path("."))
        expected = {"test_script": "echo OK", "verify_files": None}
        assert bench.grade(result, expected) is True

    def test_grade_fails_on_exit_nonzero(self) -> None:
        result = ExecutionResult(
            task_id="test",
            harness="stub",
            benchmark="harbor",
            stdout="",
            stderr="error",
            exit_code=1,
            duration_seconds=1.0,
        )
        bench = HarborBenchmark(TASKS_DIR if TASKS_DIR.exists() else Path("."))
        expected = {"test_script": "echo OK"}
        assert bench.grade(result, expected) is False

    def test_grade_file_state_check(self, tmp_path: Path) -> None:
        (tmp_path / "output.txt").write_text("hello world")
        result = ExecutionResult(
            task_id="test",
            harness="stub",
            benchmark="harbor",
            stdout="",
            stderr="",
            exit_code=0,
            duration_seconds=1.0,
        )
        bench = HarborBenchmark(tmp_path)
        expected = {
            "test_script": "echo OK",
            "verify_files": [
                {"path": "output.txt", "exists": True, "contains": "hello"},
            ],
        }
        assert bench.grade(result, expected, cwd=tmp_path) is True

    def test_grade_file_state_check_fails(self, tmp_path: Path) -> None:
        result = ExecutionResult(
            task_id="test",
            harness="stub",
            benchmark="harbor",
            stdout="",
            stderr="",
            exit_code=0,
            duration_seconds=1.0,
        )
        bench = HarborBenchmark(tmp_path)
        expected = {
            "test_script": "echo OK",
            "verify_files": [
                {"path": "missing.txt", "exists": True},
            ],
        }
        assert bench.grade(result, expected, cwd=tmp_path) is False
