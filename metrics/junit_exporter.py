"""JUnit XML exporter for Harness Benchmark.

Produces standard JUnit XML reports compatible with GitHub Actions, Jenkins,
GitLab CI, and other CI/CD test visualizers.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.base import ExecutionResult


def export_junit_xml(
    results: list[ExecutionResult],
    output_path: Path,
    suite_name: str = "harness-benchmark",
) -> None:
    """Export benchmark execution results to a standard JUnit XML file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_tests = len(results)
    failures = sum(1 for r in results if not r.passed)
    total_time = sum(r.duration_seconds for r in results)

    testsuites = ET.Element("testsuites")
    testsuite = ET.SubElement(
        testsuites,
        "testsuite",
        attrib={
            "name": suite_name,
            "tests": str(total_tests),
            "failures": str(failures),
            "errors": "0",
            "time": f"{total_time:.3f}",
        },
    )

    for r in results:
        classname = f"{r.harness}.{r.benchmark}"
        testcase = ET.SubElement(
            testsuite,
            "testcase",
            attrib={
                "name": r.task_id,
                "classname": classname,
                "time": f"{r.duration_seconds:.3f}",
            },
        )

        if not r.passed:
            failure_msg = r.error or f"Task failed with exit code {r.exit_code}"
            failure = ET.SubElement(
                testcase,
                "failure",
                attrib={
                    "message": failure_msg,
                    "type": "TaskFailure",
                },
            )
            detail = []
            if r.error:
                detail.append(f"Error: {r.error}")
            if r.stderr:
                detail.append(f"Stderr:\n{r.stderr}")
            if r.stdout:
                detail.append(f"Stdout:\n{r.stdout}")
            failure.text = "\n\n".join(detail) if detail else failure_msg

        if r.stdout:
            sys_out = ET.SubElement(testcase, "system-out")
            sys_out.text = r.stdout

        if r.stderr:
            sys_err = ET.SubElement(testcase, "system-err")
            sys_err.text = r.stderr

    tree = ET.ElementTree(testsuites)
    ET.indent(tree, space="  ", level=0)
    tree.write(str(output_path), encoding="utf-8", xml_declaration=True)
