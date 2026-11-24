from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


SCHEMA_VERSION = 3

_MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS projects (
        project_revision TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        schema_version INTEGER NOT NULL,
        snapshot_path TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        project_revision TEXT NOT NULL,
        status TEXT NOT NULL,
        run_directory TEXT NOT NULL,
        manifest_path TEXT NOT NULL,
        created_at TEXT NOT NULL,
        completed_at TEXT,
        error TEXT,
        FOREIGN KEY(project_revision) REFERENCES projects(project_revision)
    );
    CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_runs_project_revision ON runs(project_revision);
    CREATE TABLE IF NOT EXISTS parameters (
        run_id TEXT NOT NULL,
        parameter_id TEXT NOT NULL,
        value REAL NOT NULL,
        unit TEXT NOT NULL,
        provenance_json TEXT NOT NULL,
        PRIMARY KEY(run_id, parameter_id),
        FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS artifacts (
        digest TEXT PRIMARY KEY,
        size INTEGER NOT NULL,
        media_type TEXT NOT NULL,
        original_name TEXT NOT NULL,
        storage_path TEXT NOT NULL,
        created_at TEXT NOT NULL,
        created_by TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS artifact_links (
        run_id TEXT NOT NULL,
        digest TEXT NOT NULL,
        role TEXT NOT NULL,
        logical_name TEXT NOT NULL,
        PRIMARY KEY(run_id, role, logical_name),
        FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
        FOREIGN KEY(digest) REFERENCES artifacts(digest)
    );
    CREATE TABLE IF NOT EXISTS telemetry_sets (
        run_id TEXT NOT NULL,
        domain TEXT NOT NULL,
        format TEXT NOT NULL,
        path TEXT NOT NULL,
        row_count INTEGER NOT NULL,
        schema_json TEXT NOT NULL,
        PRIMARY KEY(run_id, domain),
        FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
    );
    """
,
    """
    CREATE TABLE IF NOT EXISTS component_definitions (
        component_id TEXT NOT NULL, version TEXT NOT NULL, definition_json TEXT NOT NULL,
        PRIMARY KEY(component_id, version)
    );
    CREATE TABLE IF NOT EXISTS component_instances (
        project_revision TEXT NOT NULL, instance_id TEXT NOT NULL, definition_id TEXT, instance_json TEXT NOT NULL,
        PRIMARY KEY(project_revision, instance_id),
        FOREIGN KEY(project_revision) REFERENCES projects(project_revision) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS checkpoints (
        run_id TEXT NOT NULL, time_seconds REAL NOT NULL, digest TEXT NOT NULL, path TEXT NOT NULL,
        PRIMARY KEY(run_id, time_seconds),
        FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_checkpoints_run_time ON checkpoints(run_id, time_seconds);
    """,
    """
    CREATE TABLE IF NOT EXISTS digital_twin_datasets (
        dataset_id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        source_path TEXT NOT NULL,
        artifact_digest TEXT,
        metadata_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS calibrations (
        calibration_id TEXT PRIMARY KEY,
        project_revision TEXT,
        source_dataset_id TEXT,
        calibration_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS evidence_reports (
        report_id TEXT PRIMARY KEY,
        run_id TEXT,
        status TEXT NOT NULL,
        report_path TEXT NOT NULL,
        report_digest TEXT,
        summary_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE SET NULL
    );
    CREATE INDEX IF NOT EXISTS idx_twin_dataset_kind ON digital_twin_datasets(kind, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_evidence_run ON evidence_reports(run_id, created_at DESC);
    """
]


class MetadataDatabase:
    """SQLite metadata registry with explicit migrations and transactional updates."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        with self.connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
            for index, sql in enumerate(_MIGRATIONS, start=1):
                if index in applied:
                    continue
                connection.executescript(sql)
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (index, datetime.now(timezone.utc).isoformat()),
                )

    def register_project(self, revision: str, name: str, schema_version: int, snapshot_path: Path) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO projects(project_revision,name,schema_version,snapshot_path,created_at) VALUES(?,?,?,?,?)",
                (revision, name, schema_version, str(snapshot_path), datetime.now(timezone.utc).isoformat()),
            )

    def create_run(self, run_id: str, revision: str, directory: Path, manifest_path: Path) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO runs(run_id,project_revision,status,run_directory,manifest_path,created_at) VALUES(?,?,?,?,?,?)",
                (run_id, revision, "compiled", str(directory), str(manifest_path), now),
            )

    def update_run(self, run_id: str, status: str, error: str | None = None) -> None:
        completed_at = datetime.now(timezone.utc).isoformat() if status in {"completed", "failed", "cancelled"} else None
        with self.connect() as connection:
            connection.execute(
                "UPDATE runs SET status=?, completed_at=COALESCE(?,completed_at), error=? WHERE run_id=?",
                (status, completed_at, error, run_id),
            )

    def save_parameters(self, run_id: str, parameters: dict[str, dict[str, Any]]) -> None:
        with self.connect() as connection:
            for parameter_id, spec in parameters.items():
                provenance = spec.get("provenance") or [{"source": "project", "value": spec.get("value"), "unit": spec.get("unit", "")}]
                connection.execute(
                    "INSERT OR REPLACE INTO parameters(run_id,parameter_id,value,unit,provenance_json) VALUES(?,?,?,?,?)",
                    (run_id, parameter_id, float(spec["value"]), str(spec.get("unit", "")), json.dumps(provenance, sort_keys=True)),
                )

    def register_artifact(self, record: Any) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO artifacts(digest,size,media_type,original_name,storage_path,created_at,created_by) VALUES(?,?,?,?,?,?,?)",
                (record.digest, record.size, record.media_type, record.original_name, record.storage_path, record.created_at, record.created_by),
            )

    def link_artifact(self, run_id: str, digest: str, role: str, logical_name: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO artifact_links(run_id,digest,role,logical_name) VALUES(?,?,?,?)",
                (run_id, digest, role, logical_name),
            )

    def register_checkpoint(self, run_id: str, time_seconds: float, digest: str, path: Path) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO checkpoints(run_id,time_seconds,digest,path) VALUES(?,?,?,?)",
                (run_id, time_seconds, digest, str(path)),
            )

    def register_components(self, project_revision: str, definitions: dict[str, Any], instances: dict[str, Any]) -> None:
        with self.connect() as connection:
            for component_id, definition in definitions.items():
                version = str((definition or {}).get("version", "0.0.0"))
                connection.execute("INSERT OR REPLACE INTO component_definitions(component_id,version,definition_json) VALUES(?,?,?)",
                                   (component_id, version, json.dumps(definition, sort_keys=True)))
            for instance_id, instance in instances.items():
                connection.execute("INSERT OR REPLACE INTO component_instances(project_revision,instance_id,definition_id,instance_json) VALUES(?,?,?,?)",
                                   (project_revision, instance_id, (instance or {}).get("definition"), json.dumps(instance, sort_keys=True)))

    def register_telemetry(self, run_id: str, domain: str, format_name: str, path: Path, row_count: int, schema: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO telemetry_sets(run_id,domain,format,path,row_count,schema_json) VALUES(?,?,?,?,?,?)",
                (run_id, domain, format_name, str(path), row_count, json.dumps(schema, sort_keys=True)),
            )

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT run_id,project_revision,status,run_directory,manifest_path,created_at,completed_at,error FROM runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["parameters"] = [dict(item) for item in connection.execute("SELECT * FROM parameters WHERE run_id=? ORDER BY parameter_id", (run_id,))]
            result["artifacts"] = [dict(item) for item in connection.execute(
                "SELECT l.role,l.logical_name,a.* FROM artifact_links l JOIN artifacts a ON a.digest=l.digest WHERE l.run_id=? ORDER BY l.role,l.logical_name", (run_id,)
            )]
            result["telemetry"] = [dict(item) for item in connection.execute("SELECT * FROM telemetry_sets WHERE run_id=?", (run_id,))]
            result["checkpoints"] = [dict(item) for item in connection.execute("SELECT * FROM checkpoints WHERE run_id=? ORDER BY time_seconds", (run_id,))]
            return result
    def register_digital_twin_dataset(self, dataset_id: str, kind: str, source_path: Path, metadata: dict[str, Any], artifact_digest: str | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO digital_twin_datasets(dataset_id,kind,source_path,artifact_digest,metadata_json,created_at) VALUES(?,?,?,?,?,?)",
                (dataset_id, kind, str(source_path), artifact_digest, json.dumps(metadata, sort_keys=True), datetime.now(timezone.utc).isoformat()),
            )

    def register_calibration(self, calibration_id: str, calibration: dict[str, Any], project_revision: str | None = None, source_dataset_id: str | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO calibrations(calibration_id,project_revision,source_dataset_id,calibration_json,created_at) VALUES(?,?,?,?,?)",
                (calibration_id, project_revision, source_dataset_id, json.dumps(calibration, sort_keys=True), datetime.now(timezone.utc).isoformat()),
            )

    def register_evidence_report(self, report_id: str, report_path: Path, status: str, summary: dict[str, Any], run_id: str | None = None, report_digest: str | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO evidence_reports(report_id,run_id,status,report_path,report_digest,summary_json,created_at) VALUES(?,?,?,?,?,?,?)",
                (report_id, run_id, status, str(report_path), report_digest, json.dumps(summary, sort_keys=True), datetime.now(timezone.utc).isoformat()),
            )

    def list_evidence_reports(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT report_id,run_id,status,report_path,report_digest,summary_json,created_at FROM evidence_reports ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

