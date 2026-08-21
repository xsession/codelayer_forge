from __future__ import annotations

import json
from pathlib import Path

import yaml

from embeddyn.mechatronics.digital_twin import (
    align_datasets,
    calculate_metrics,
    create_state_snapshot,
    fit_all,
    render_evidence_markdown,
    run_uncertainty,
    verify_requirements,
)
from embeddyn.mechatronics.storage.database import MetadataDatabase, SCHEMA_VERSION


def sample_rows():
    simulated = [
        {"time_seconds": 0.0, "speed": 0.0, "current": 1.0},
        {"time_seconds": 1.0, "speed": 10.0, "current": 2.0},
        {"time_seconds": 2.0, "speed": 20.0, "current": 3.0},
    ]
    measured = [
        {"time_seconds": 0.5, "speed": 6.0, "current": 1.5},
        {"time_seconds": 1.5, "speed": 16.0, "current": 2.5},
    ]
    return simulated, measured


def test_alignment_metrics_and_calibration():
    simulated, measured = sample_rows()
    aligned = align_datasets(simulated, measured)
    assert len(aligned) == 2
    metrics = calculate_metrics(aligned)
    assert metrics["speed"].rmse == 1.0
    calibration = fit_all(aligned)["speed"]
    assert abs(calibration.scale - 1.0) < 1e-12
    assert abs(calibration.offset - 1.0) < 1e-12
    assert calibration.after_rmse < calibration.before_rmse


def test_state_snapshot(tmp_path: Path):
    path = tmp_path / "measurements.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in sample_rows()[1]), encoding="utf-8")
    snapshot = create_state_snapshot(path)
    assert snapshot["source_time"] == 1.5
    assert snapshot["state"]["speed"] == 16.0


def test_uncertainty_is_deterministic(tmp_path: Path):
    spec = tmp_path / "uncertainty.yaml"
    spec.write_text(yaml.safe_dump({"parameters": {
        "motor.resistance": {"distribution": "normal", "mean": 2.0, "sigma": 0.1},
        "load.torque": {"distribution": "uniform", "minimum": 0.1, "maximum": 0.5},
    }}), encoding="utf-8")
    first = run_uncertainty(spec, 100, 42)
    second = run_uncertainty(spec, 100, 42)
    assert first["sample_set"] == second["sample_set"]
    assert first["parameters"]["motor.resistance"]["p95"] > first["parameters"]["motor.resistance"]["p05"]


def test_requirements_and_report(tmp_path: Path):
    requirements = tmp_path / "requirements.yaml"
    requirements.write_text(yaml.safe_dump({"requirements": [
        {"id": "REQ-001", "title": "Speed model accuracy", "verification": {"metric": "signals.speed.rmse", "operator": "<=", "value": 1.1}},
        {"id": "REQ-002", "title": "Current model accuracy", "verification": {"metric": "signals.current.rmse", "operator": "<=", "value": 0.1}},
    ]}), encoding="utf-8")
    metrics = tmp_path / "metrics.json"
    metrics.write_text(json.dumps({"signals": {"speed": {"rmse": 1.0}, "current": {"rmse": 0.0}}}), encoding="utf-8")
    result = verify_requirements(requirements, metrics)
    assert result["summary"] == {"passed": 2, "failed": 0, "unresolved": 0, "total": 2}
    report = render_evidence_markdown(result, json.loads(metrics.read_text()))
    assert "REQ-001" in report
    assert "PASSED" in report


def test_phase6_database_migration(tmp_path: Path):
    database = MetadataDatabase(tmp_path / "metadata.sqlite3")
    assert SCHEMA_VERSION == 3
    database.register_digital_twin_dataset("dataset-1", "measurement", tmp_path / "input.csv", {"source": "test"})
    database.register_calibration("cal-1", {"models": {}})
    database.register_evidence_report("report-1", tmp_path / "report.md", "passed", {"passed": 1})
    reports = database.list_evidence_reports()
    assert reports[0]["report_id"] == "report-1"
