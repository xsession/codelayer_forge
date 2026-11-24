from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from .models import JobSpec, JobStatus, WorkerCapabilities, WorkerRecord, utc_now


class DistributedCoordinator:
    """Persistent local/server-neutral worker and job coordinator.

    SQLite is used for the local deployment. The API intentionally keeps SQL
    details behind this class so a PostgreSQL implementation can replace it.
    """

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _migrate(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS distributed_workers (
                    worker_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    capabilities_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    registered_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    active_jobs INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS distributed_jobs (
                    job_id TEXT PRIMARY KEY,
                    experiment_id TEXT,
                    project_path TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    requirements_json TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    assigned_worker_id TEXT,
                    created_at TEXT NOT NULL,
                    claimed_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    result_json TEXT,
                    error TEXT,
                    cancellation_requested INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(assigned_worker_id) REFERENCES distributed_workers(worker_id)
                );
                CREATE INDEX IF NOT EXISTS idx_distributed_jobs_queue
                    ON distributed_jobs(status, priority DESC, created_at ASC);
                CREATE INDEX IF NOT EXISTS idx_distributed_workers_status
                    ON distributed_workers(status, last_seen_at DESC);
                CREATE TABLE IF NOT EXISTS distributed_experiments (
                    experiment_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    specification_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                );
                """
            )

    def register_worker(self, worker: WorkerRecord) -> WorkerRecord:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO distributed_workers(
                    worker_id,name,endpoint,capabilities_json,status,registered_at,last_seen_at,active_jobs
                ) VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(worker_id) DO UPDATE SET
                    name=excluded.name, endpoint=excluded.endpoint,
                    capabilities_json=excluded.capabilities_json,
                    status='online', last_seen_at=excluded.last_seen_at, active_jobs=excluded.active_jobs
                """,
                (
                    worker.worker_id, worker.name, worker.endpoint,
                    json.dumps(worker.to_dict()["capabilities"], sort_keys=True),
                    worker.status, worker.registered_at, worker.last_seen_at,
                    worker.active_jobs,
                ),
            )
        return worker

    def heartbeat(self, worker_id: str, active_jobs: int | None = None) -> None:
        with self._connect() as conn:
            if active_jobs is None:
                cursor = conn.execute(
                    "UPDATE distributed_workers SET last_seen_at=?,status='online' WHERE worker_id=?",
                    (utc_now(), worker_id),
                )
            else:
                cursor = conn.execute(
                    "UPDATE distributed_workers SET last_seen_at=?,status='online',active_jobs=? WHERE worker_id=?",
                    (utc_now(), max(0, active_jobs), worker_id),
                )
            if cursor.rowcount == 0:
                raise KeyError(f"unknown worker: {worker_id}")

    def mark_stale_workers(self, timeout_seconds: float = 60.0) -> int:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)).isoformat()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            stale = conn.execute(
                "SELECT worker_id FROM distributed_workers WHERE last_seen_at < ? AND status='online'",
                (cutoff,),
            ).fetchall()
            now = utc_now()
            for row in stale:
                worker_id = row["worker_id"]
                conn.execute(
                    """UPDATE distributed_jobs
                       SET status=?,completed_at=?
                       WHERE assigned_worker_id=? AND status IN (?,?) AND cancellation_requested=1""",
                    (JobStatus.CANCELLED.value, now, worker_id, JobStatus.CLAIMED.value, JobStatus.RUNNING.value),
                )
                conn.execute(
                    """UPDATE distributed_jobs
                       SET status=?,assigned_worker_id=NULL,claimed_at=NULL,started_at=NULL,
                           error='requeued after worker heartbeat timeout'
                       WHERE assigned_worker_id=? AND status IN (?,?) AND cancellation_requested=0""",
                    (JobStatus.QUEUED.value, worker_id, JobStatus.CLAIMED.value, JobStatus.RUNNING.value),
                )
                conn.execute(
                    "UPDATE distributed_workers SET status='offline',active_jobs=0 WHERE worker_id=?",
                    (worker_id,),
                )
            return len(stale)

    def list_workers(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM distributed_workers ORDER BY name,worker_id").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["capabilities"] = json.loads(item.pop("capabilities_json"))
            result.append(item)
        return result

    def submit_job(self, spec: JobSpec) -> str:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO distributed_jobs(
                    job_id,experiment_id,project_path,arguments_json,requirements_json,
                    priority,status,created_at
                ) VALUES(?,?,?,?,?,?,?,?)""",
                (
                    spec.job_id, spec.experiment_id, spec.project_path,
                    json.dumps(spec.arguments, sort_keys=True),
                    json.dumps(spec.requirements, sort_keys=True),
                    spec.priority, JobStatus.QUEUED.value, spec.created_at,
                ),
            )
        return spec.job_id

    def claim_job(self, worker_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            worker_row = conn.execute(
                "SELECT * FROM distributed_workers WHERE worker_id=? AND status='online'",
                (worker_id,),
            ).fetchone()
            if worker_row is None:
                raise KeyError(f"unknown or offline worker: {worker_id}")
            caps = WorkerCapabilities.from_dict(json.loads(worker_row["capabilities_json"]))
            if worker_row["active_jobs"] >= caps.max_parallel_jobs:
                return None
            candidates = conn.execute(
                """SELECT * FROM distributed_jobs
                   WHERE status=? AND cancellation_requested=0
                   ORDER BY priority DESC, created_at ASC""",
                (JobStatus.QUEUED.value,),
            ).fetchall()
            selected = None
            for row in candidates:
                if caps.matches(json.loads(row["requirements_json"])):
                    selected = row
                    break
            if selected is None:
                return None
            now = utc_now()
            updated = conn.execute(
                """UPDATE distributed_jobs SET status=?,assigned_worker_id=?,claimed_at=?
                   WHERE job_id=? AND status=?""",
                (JobStatus.CLAIMED.value, worker_id, now, selected["job_id"], JobStatus.QUEUED.value),
            )
            if updated.rowcount != 1:
                return None
            conn.execute(
                "UPDATE distributed_workers SET active_jobs=active_jobs+1,last_seen_at=? WHERE worker_id=?",
                (now, worker_id),
            )
            return self.get_job(selected["job_id"], connection=conn)

    def start_job(self, job_id: str, worker_id: str) -> None:
        with self._connect() as conn:
            cursor = conn.execute(
                """UPDATE distributed_jobs SET status=?,started_at=?
                   WHERE job_id=? AND assigned_worker_id=? AND status=?""",
                (JobStatus.RUNNING.value, utc_now(), job_id, worker_id, JobStatus.CLAIMED.value),
            )
            if cursor.rowcount != 1:
                raise ValueError("job cannot be started by this worker")

    def complete_job(self, job_id: str, worker_id: str, result: dict[str, Any]) -> None:
        self._finish_job(job_id, worker_id, JobStatus.COMPLETED, result=result)

    def fail_job(self, job_id: str, worker_id: str, error: str) -> None:
        self._finish_job(job_id, worker_id, JobStatus.FAILED, error=error)

    def cancel_job(self, job_id: str, worker_id: str, result: dict[str, Any] | None = None) -> None:
        self._finish_job(job_id, worker_id, JobStatus.CANCELLED, result=result)

    def cancellation_requested(self, job_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT cancellation_requested,status FROM distributed_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
        if row is None:
            raise KeyError(job_id)
        return bool(row["cancellation_requested"]) or row["status"] == JobStatus.CANCELLED.value

    def _finish_job(
        self,
        job_id: str,
        worker_id: str,
        status: JobStatus,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                """UPDATE distributed_jobs SET status=?,completed_at=?,result_json=?,error=?
                   WHERE job_id=? AND assigned_worker_id=? AND status IN (?,?)""",
                (
                    status.value, utc_now(), json.dumps(result or {}, sort_keys=True), error,
                    job_id, worker_id, JobStatus.CLAIMED.value, JobStatus.RUNNING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("job cannot be completed by this worker")
            conn.execute(
                "UPDATE distributed_workers SET active_jobs=MAX(0,active_jobs-1),last_seen_at=? WHERE worker_id=?",
                (utc_now(), worker_id),
            )

    def request_cancel(self, job_id: str) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT status FROM distributed_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            if row["status"] == JobStatus.QUEUED.value:
                conn.execute(
                    "UPDATE distributed_jobs SET status=?,completed_at=?,cancellation_requested=1 WHERE job_id=?",
                    (JobStatus.CANCELLED.value, utc_now(), job_id),
                )
            elif row["status"] not in {JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value}:
                conn.execute("UPDATE distributed_jobs SET cancellation_requested=1 WHERE job_id=?", (job_id,))

    def get_job(self, job_id: str, connection: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        owns = connection is None
        conn = connection or self._connect()
        try:
            row = conn.execute("SELECT * FROM distributed_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                return None
            item = dict(row)
            item["arguments"] = json.loads(item.pop("arguments_json"))
            item["requirements"] = json.loads(item.pop("requirements_json"))
            item["result"] = json.loads(item.pop("result_json")) if item.get("result_json") else None
            return item
        finally:
            if owns:
                conn.close()

    def list_jobs(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 10000))
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT job_id FROM distributed_jobs WHERE status=? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT job_id FROM distributed_jobs ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [self.get_job(row["job_id"], connection=conn) for row in rows]

    def register_experiment(self, experiment_id: str, name: str, specification: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO distributed_experiments(experiment_id,name,specification_json,status,created_at) VALUES(?,?,?,?,?)",
                (experiment_id, name, json.dumps(specification, sort_keys=True), "queued", utc_now()),
            )

    def experiment_status(self, experiment_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM distributed_experiments WHERE experiment_id=?", (experiment_id,)).fetchone()
            if row is None:
                return None
            counts = conn.execute(
                "SELECT status,COUNT(*) AS count FROM distributed_jobs WHERE experiment_id=? GROUP BY status",
                (experiment_id,),
            ).fetchall()
            jobs = {r["status"]: r["count"] for r in counts}
            active = jobs.get(JobStatus.CLAIMED.value, 0) + jobs.get(JobStatus.RUNNING.value, 0)
            if active:
                derived = "running"
            elif jobs.get(JobStatus.QUEUED.value, 0):
                derived = "queued"
            elif jobs.get(JobStatus.FAILED.value, 0):
                derived = "failed"
            elif jobs and jobs.get(JobStatus.CANCELLED.value, 0) == sum(jobs.values()):
                derived = "cancelled"
            elif jobs:
                derived = "completed"
            else:
                derived = "queued"
            completed_at = utc_now() if derived in {"completed", "failed", "cancelled"} and not row["completed_at"] else row["completed_at"]
            if row["status"] != derived or row["completed_at"] != completed_at:
                conn.execute(
                    "UPDATE distributed_experiments SET status=?,completed_at=? WHERE experiment_id=?",
                    (derived, completed_at, experiment_id),
                )
            item = dict(row)
            item["status"] = derived
            item["completed_at"] = completed_at
            item["specification"] = json.loads(item.pop("specification_json"))
            item["jobs"] = jobs
            return item
