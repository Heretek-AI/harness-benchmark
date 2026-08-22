"""JUnit XML Exporter for Harness Benchmark 2.0."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from core.types import BenchmarkReport, ExecutionResult


class JUnitExporter:
    """Exports benchmark execution results to standard JUnit XML format."""

    @staticmethod
    def export(report: BenchmarkReport, output_path: Path) -> Path:
        """Serialize a BenchmarkReport to a JUnit XML file."""
        testsuites = ET.Element(
            "testsuites",
            name=f"HarnessBenchmark-{report.run_id}",
            tests=str(len(report.results)),
            failures=str(sum(1 for r in report.results if not r.passed)),
            errors=str(sum(1 for r in report.results if r.exit_code != 0)),
            time=f"{sum(r.duration_seconds for r in report.results):.2f}",
        )

        # Group by harness + benchmark
        grouped: dict[str, list[ExecutionResult]] = {}
        for r in report.results:
            key = f"{r.harness}.{r.benchmark}"
            grouped.setdefault(key, []).append(r)

        for suite_name, results in grouped.items():
            ts = ET.SubElement(
                testsuites,
                "testsuite",
                name=suite_name,
                tests=str(len(results)),
                failures=str(sum(1 for r in results if not r.passed)),
                errors=str(sum(1 for r in results if r.exit_code != 0)),
                time=f"{sum(r.duration_seconds for r in results):.2f}",
            )
            for r in results:
                tc = ET.SubElement(
                    ts,
                    "testcase",
                    name=r.task_id,
                    classname=suite_name,
                    time=f"{r.duration_seconds:.2f}",
                )
                if not r.passed:
                    failure_msg = r.error or f"Exit code {r.exit_code}"
                    failure = ET.SubElement(
                        tc,
                        "failure",
                        message=failure_msg,
                        type="AssertionError" if r.exit_code == 0 else "ExecutionError",
                    )
                    failure.text = (r.oracle_log or "") + "\n" + (r.stderr or "")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        tree = ET.ElementTree(testsuites)
        ET.indent(tree, space="  ", level=0)
        tree.write(str(output_path), encoding="utf-8", xml_declaration=True)
        return output_path
