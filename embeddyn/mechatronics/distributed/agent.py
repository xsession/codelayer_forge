from __future__ import annotations

import json
import subprocess
import sys
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
        output_root = (self.output_root / job_id).resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable, "-m", "vsd", "mechatronics", "run",
            job["project_path"], "--output-root", str(output_root),
        ]
        arguments = job.get("arguments") or {}
        if arguments.get("mock"):
            command.append("--mock")
        if arguments.get("isolate_adapters"):
            command.append("--isolate-adapters")
        try:
            completed = subprocess.run(command, check=False, capture_output=True, text=True)
            result = {
                "command": command,
                "returncode": completed.returncode,
                "stdout": completed.stdout[-100000:],
                "stderr": completed.stderr[-100000:],
                "output_root": str(output_root),
                "parameter_overrides": arguments.get("parameter_overrides", {}),
            }
            if completed.returncode == 0:
                self.coordinator.complete_job(job_id, self.worker_id, result)
            else:
                self.coordinator.fail_job(job_id, self.worker_id, completed.stderr[-10000:] or "worker command failed")
            return self.coordinator.get_job(job_id)
        except Exception as exc:
            self.coordinator.fail_job(job_id, self.worker_id, str(exc))
            raise

    def serve(self, once: bool = False) -> None:
        while True:
            job = self.execute_once()
            if once:
                return
            if job is None:
                time.sleep(self.poll_interval_seconds)
