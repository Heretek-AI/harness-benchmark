"""Tests for safety and robustness testing modules."""

from __future__ import annotations

from pathlib import Path

from benchmarks.safety_adapter import SafetyTestSuite, SafetyTask, ALL_SAFETY_TASKS
from evaluation.network_monitor import NetworkMonitor, NetworkEvent
from evaluation.file_audit import FileAudit, FileAccess


def test_safety_suite_task_count() -> None:
    suite = SafetyTestSuite()
    assert len(suite.tasks) >= 10


def test_safety_suite_categories() -> None:
    suite = SafetyTestSuite()
    categories = {t.category for t in suite.tasks}
    assert "injection" in categories
    assert "exfiltration" in categories
    assert "privilege" in categories
    assert "data_leak" in categories


def test_safety_suite_filter_category() -> None:
    suite = SafetyTestSuite()
    injection = suite.get_tasks_by_category("injection")
    assert len(injection) >= 3
    assert all(t.category == "injection" for t in injection)


def test_safety_suite_filter_severity() -> None:
    suite = SafetyTestSuite()
    critical = suite.get_tasks_by_severity("critical")
    assert len(critical) >= 2


def test_safety_suite_iter_tasks() -> None:
    suite = SafetyTestSuite()
    tasks = list(suite.iter_tasks())
    assert len(tasks) >= 10
    assert all(isinstance(t[0], str) for t in tasks)
    assert all(isinstance(t[2], SafetyTask) for t in tasks)


def test_network_monitor_init() -> None:
    monitor = NetworkMonitor(
        allowed_destinations=["example.com"],
        blocked_destinations=["evil.com"],
    )
    assert "example.com" in monitor.allowed_destinations
    assert "evil.com" in monitor.blocked_destinations


def test_network_monitor_analyze_empty() -> None:
    monitor = NetworkMonitor()
    report = monitor.analyze()
    assert report.total_events == 0
    assert report.passed


def test_network_monitor_suspicious() -> None:
    monitor = NetworkMonitor(blocked_destinations=["evil.com"])
    monitor.add_event(NetworkEvent(
        timestamp=0.0,
        event_type="http",
        source="agent",
        destination="evil.com:443",
        protocol="https",
    ))
    report = monitor.analyze()
    assert not report.passed
    assert len(report.suspicious_connections) == 1


def test_network_monitor_parse_iptables() -> None:
    monitor = NetworkMonitor()
    log = 'SRC=10.0.0.1 DST=93.184.216.34 SPT=43210 DPT=443'
    events = monitor.parse_iptables_log(log)
    assert len(events) == 1
    assert events[0].destination == "93.184.216.34:443"


def test_file_audit_init() -> None:
    audit = FileAudit(workspace_path=Path("/tmp/test-workspace"))
    assert audit.workspace_path == Path("/tmp/test-workspace").resolve()


def test_file_audit_analyze_clean() -> None:
    audit = FileAudit(workspace_path=Path("/tmp/test-workspace"))
    report = audit.analyze()
    assert report.passed
    assert report.violations == []


def test_file_audit_violation() -> None:
    audit = FileAudit(workspace_path=Path("/tmp/test-workspace"))
    audit.extra_allowed = [Path("/tmp")]
    # Simulate strace output accessing a file outside workspace
    strace = 'open("/etc/passwd", O_RDONLY) = 3'
    report = audit.analyze(strace_output=strace)
    assert not report.passed
    assert len(report.violations) >= 1


def test_file_audit_sensitive_detection() -> None:
    audit = FileAudit(workspace_path=Path("/tmp/test-workspace"))
    strace = 'open("/root/.ssh/id_rsa", O_RDONLY) = 3'
    report = audit.analyze(strace_output=strace)
    assert len(report.sensitive_files_accessed) >= 1


def test_safety_task_dataclass() -> None:
    task = SafetyTask(
        task_id="test-001",
        name="Test task",
        category="injection",
        prompt="Do something bad",
        expected_behavior="refuse",
    )
    assert task.severity == "high"  # default
    assert task.task_id == "test-001"
