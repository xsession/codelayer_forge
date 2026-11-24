from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .coordinator import DistributedCoordinator


@dataclass
class WorkerAgent:
    coordinator: DistributedCoordinator
    worker_id: str
    output_root: Path = Path(".embeddyn/worker-runs")
    poll_interval_seconds: float = 1.0

    def execute_once(self) -> dict[str, Any] | None:
        self.coordinator.heartbeat(self.worker_id)
        job = self.coordinator.claim_job(self.worker_id)
        if job is None:
            return None
        job_id = job["job_id"]
        self.coordinator.start_job(job_id, self.worker_id)
        worker_root = self.output_root.resolve()
        output_root = (worker_root / job_id).resolve()
        if output_root != worker_root and worker_root not in output_root.parents:
            self.coordinator.fail_job(job_id, self.worker_id, "job id resolves outside the worker output root")
            return self.coordinator.get_job(job_id)
        output_root.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable, "-m", "embeddyn", "mechatronics", "run",
            job["project_path"], "--output-root", str(output_root),
        ]
        arguments = job.get("arguments") or {}
        if arguments.get("mock"):
            command.append("--mock")
        if arguments.get("isolate_adapters"):
            command.append("--isolate-adapters")
        overrides = arguments.get("parameter_overrides") or {}
        if overrides:
            if not isinstance(overrides, dict):
                self.coordinator.fail_job(job_id, self.worker_id, "parameter_overrides must be an object")
                return self.coordinator.get_job(job_id)
            command.extend(["--parameter-overrides", json.dumps(overrides, sort_keys=True, separators=(",", ":"))])
        try:
            with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as stdout_file, tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as stderr_file:
                process = subprocess.Popen(command, stdout=stdout_file, stderr=stderr_file, text=True)
                sleep_interval = min(5.0, max(0.1, self.poll_interval_seconds))
                cancelled = False
                while process.poll() is None:
                    self.coordinator.heartbeat(self.worker_id)
                    if self.coordinator.cancellation_requested(job_id):
                        cancelled = True
                        process.terminate()
                        try:
                            process.wait(timeout=5.0)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5.0)
                        break
                    time.sleep(sleep_interval)
                returncode = process.wait()
                stdout_file.seek(0)
                stderr_file.seek(0)
                stdout = stdout_file.read()[-100000:]
                stderr = stderr_file.read()[-100000:]
            result = {
                "command": command,
                "returncode": returncode,
                "stdout": stdout,
                "stderr": stderr,
                "output_root": str(output_root),
                "parameter_overrides": arguments.get("parameter_overrides", {}),
            }
            if returncode == 0 and not cancelled:
                result["metrics"] = _run_metrics(stdout, arguments.get("metrics"))
            if cancelled:
                self.coordinator.cancel_job(job_id, self.worker_id, result)
            elif returncode == 0:
                self.coordinator.complete_job(job_id, self.worker_id, result)
            else:
                self.coordinator.fail_job(job_id, self.worker_id, stderr[-10000:] or "worker command failed")
            return self.coordinator.get_job(job_id)
        except Exception as exc:
            current = self.coordinator.get_job(job_id)
            if current and current["status"] in {"claimed", "running"}:
                self.coordinator.fail_job(job_id, self.worker_id, str(exc))
            raise

    def serve(self, once: bool = False) -> None:
        while True:
            job = self.execute_once()
            if once:
                return
            if job is None:
                time.sleep(self.poll_interval_seconds)


def _run_metrics(stdout: str, wanted: Any) -> dict[str, Any]:
    """Metrics from the JSON summary `mechatronics run` prints last, optionally
    narrowed to the experiment's declared metric names."""
    start = 0 if stdout.lstrip().startswith("{") else stdout.rfind("\n{") + 1
    try:
        summary = json.loads(stdout[start:])
    except (ValueError, TypeError):
        return {}
    metrics = dict(summary.get("metrics") or {}) if isinstance(summary, dict) else {}
    if not wanted:
        return metrics
    from ..metrics import select_metrics
    selected: dict[str, Any] = {}
    for name in wanted:
        try:
            selected.update(select_metrics(metrics, [name]))
        except KeyError as error:
            selected[name] = None
            selected.setdefault("_errors", []).append(str(error.args[0]))
    return selected

