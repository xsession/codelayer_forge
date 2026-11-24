import json
from pathlib import Path

from embeddyn.mechatronics.compiler import ProjectCompiler
from embeddyn.mechatronics.factory import build_adapters
from embeddyn.mechatronics.model import MechatronicProject
from embeddyn.mechatronics.orchestrator import CoSimulationOrchestrator
from embeddyn.mechatronics.storage import (
    ContentAddressedStore,
    MetadataDatabase,
    TelemetryWriter,
    export_telemetry_csv,
    read_telemetry_rows,
)

ROOT = Path(__file__).resolve().parents[2]


def test_content_addressed_store_deduplicates_and_verifies(tmp_path):
    source = tmp_path / "firmware.bin"
    source.write_bytes(b"same-content")
    store = ContentAddressedStore(tmp_path / "artifacts")
    first = store.add_file(source, created_by="test")
    second = store.add_bytes(b"same-content", "copy.bin", created_by="test")
    assert first.digest == second.digest
    assert store.verify(first.digest)
    assert len(store.verify_all()) == 1


def test_database_registers_run_parameters_and_artifacts(tmp_path):
    project = MechatronicProject.load(ROOT / "examples/mechatronics/dc-motor.yaml")
    compiled = ProjectCompiler().compile(project, tmp_path / ".vsd" / "runs")
    database = MetadataDatabase(compiled.database_path)
    record = database.get_run(compiled.run_id)
    assert record is not None
    assert record["status"] == "compiled"
    assert record["artifacts"][0]["logical_name"] == "project_snapshot"


def test_streaming_telemetry_roundtrip_and_csv_export(tmp_path):
    writer = TelemetryWriter(tmp_path / "telemetry", flush_rows=2)
    writer.append({"time": 0.0, "signal": 1.0})
    writer.append({"time": 0.1, "signal": 2.0})
    writer.append({"time": 0.2, "signal": 3.0})
    writer.close()
    rows = read_telemetry_rows(writer.path)
    assert len(rows) == 3
    destination = export_telemetry_csv(writer.path, tmp_path / "telemetry.csv")
    assert destination.read_text(encoding="utf-8").startswith("time,signal")


def test_run_persists_telemetry_metadata(tmp_path):
    project = MechatronicProject.load(ROOT / "examples/mechatronics/dc-motor.yaml")
    project.duration_seconds = 0.003
    compiled = ProjectCompiler().compile(project, tmp_path / ".vsd" / "runs")
    writer = TelemetryWriter(compiled.directory / "signals" / "telemetry", flush_rows=2)
    rows = CoSimulationOrchestrator(project, build_adapters(project, mock=True)).run(telemetry_writer=writer)
    database = MetadataDatabase(compiled.database_path)
    database.register_telemetry(compiled.run_id, "combined", writer.format, writer.path, writer.row_count, writer.schema)
    database.update_run(compiled.run_id, "completed")
    record = database.get_run(compiled.run_id)
    assert record is not None
    assert record["status"] == "completed"
    assert record["telemetry"][0]["row_count"] == len(rows)
