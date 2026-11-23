from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RequirementResult:
    requirement_id: str
    title: str
    status: str
    actual: Any
    operator: str
    expected: Any
    evidence: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.requirement_id,
            "title": self.title,
            "status": self.status,
            "actual": self.actual,
            "operator": self.operator,
            "expected": self.expected,
            "evidence": self.evidence,
        }


def _lookup(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(path)
        current = current[part]
    return current


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "<=": return actual <= expected
    if operator == "<": return actual < expected
    if operator == ">=": return actual >= expected
    if operator == ">": return actual > expected
    if operator == "==": return actual == expected
    if operator == "!=": return actual != expected
    if operator == "between": return expected[0] <= actual <= expected[1]
    raise ValueError(f"unsupported requirement operator: {operator}")


def verify_requirements(requirements_path: Path, metrics_path: Path) -> dict[str, Any]:
    specification = yaml.safe_load(requirements_path.read_text(encoding="utf-8")) or {}
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    results: list[RequirementResult] = []
    for requirement in specification.get("requirements", []):
        requirement_id = str(requirement["id"])
        title = str(requirement.get("title", requirement_id))
        verification = dict(requirement["verification"])
        metric_path = str(verification["metric"])
        operator = str(verification.get("operator", "<="))
        expected = verification["value"]
        try:
            actual = _lookup(metrics, metric_path)
            status = "passed" if _compare(actual, operator, expected) else "failed"
        except (KeyError, TypeError, ValueError):
            actual = None
            status = "unresolved"
        evidence = [str(item) for item in requirement.get("evidence", [])]
        evidence.extend([str(requirements_path.resolve()), str(metrics_path.resolve())])
        results.append(RequirementResult(requirement_id, title, status, actual, operator, expected, evidence))
    counts = {status: sum(1 for item in results if item.status == status) for status in ("passed", "failed", "unresolved")}
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "requirements_source": str(requirements_path.resolve()),
        "metrics_source": str(metrics_path.resolve()),
        "summary": {**counts, "total": len(results)},
        "requirements": [item.to_dict() for item in results],
    }


def render_evidence_markdown(traceability: dict[str, Any], comparison: dict[str, Any] | None = None) -> str:
    lines = ["# Mechatronic Simulation Evidence Report", "", f"Generated: {traceability.get('generated_at', '')}", ""]
    summary = traceability.get("summary", {})
    lines += ["## Requirement Summary", "", f"- Passed: {summary.get('passed', 0)}", f"- Failed: {summary.get('failed', 0)}", f"- Unresolved: {summary.get('unresolved', 0)}", ""]
    if comparison:
        lines += ["## Simulation-to-Measurement Comparison", ""]
        lines.append(f"Aligned samples: {comparison.get('aligned_samples', 0)}")
        lines.append("")
        lines.append("| Signal | RMSE | MAE | Max error | Bias | NRMSE |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for signal, metrics in comparison.get("signals", {}).items():
            def cell(name: str) -> str:
                value = metrics.get(name)
                return f"{value:.6g}" if isinstance(value, (int, float)) else "n/a"
            lines.append(f"| {signal} | {cell('rmse')} | {cell('mae')} | {cell('max_abs_error')} | {cell('bias')} | {cell('nrmse')} |")
        lines.append("")
    lines += ["## Requirements", ""]
    for item in traceability.get("requirements", []):
        lines += [f"### {item['id']} — {item['title']}", "", f"**Status:** {item['status'].upper()}", "", f"Verification: `{item['actual']}` {item['operator']} `{item['expected']}`", ""]
        if item.get("evidence"):
            lines.append("Evidence:")
            lines.extend(f"- `{entry}`" for entry in item["evidence"])
            lines.append("")
    return "\n".join(lines)
