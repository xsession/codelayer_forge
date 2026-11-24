from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStatus(str, Enum):
    QUEUED = "queued"
    CLAIMED = "claimed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class WorkerCapabilities:
    simulators: tuple[str, ...] = ()
    hardware: tuple[str, ...] = ()
    operating_system: str = "unknown"
    architecture: str = "unknown"
    max_parallel_jobs: int = 1
    labels: tuple[str, ...] = ()
    real_time: bool = False

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "WorkerCapabilities":
        return cls(
            simulators=tuple(sorted(set(raw.get("simulators") or ()))),
            hardware=tuple(sorted(set(raw.get("hardware") or ()))),
            operating_system=str(raw.get("operating_system", "unknown")),
            architecture=str(raw.get("architecture", "unknown")),
            max_parallel_jobs=max(1, int(raw.get("max_parallel_jobs", 1))),
            labels=tuple(sorted(set(raw.get("labels") or ()))),
            real_time=bool(raw.get("real_time", False)),
        )

    def matches(self, requirements: dict[str, Any]) -> bool:
        required_simulators = set(requirements.get("simulators") or ())
        required_hardware = set(requirements.get("hardware") or ())
        required_labels = set(requirements.get("labels") or ())
        if not required_simulators.issubset(self.simulators):
            return False
        if not required_hardware.issubset(self.hardware):
            return False
        if not required_labels.issubset(self.labels):
            return False
        if requirements.get("real_time") and not self.real_time:
            return False
        requested_os = requirements.get("operating_system")
        if requested_os and requested_os != self.operating_system:
            return False
        requested_arch = requirements.get("architecture")
        if requested_arch and requested_arch != self.architecture:
            return False
        return True


@dataclass
class WorkerRecord:
    worker_id: str
    name: str
    endpoint: str
    capabilities: WorkerCapabilities
    status: str = "online"
    registered_at: str = field(default_factory=utc_now)
    last_seen_at: str = field(default_factory=utc_now)
    active_jobs: int = 0

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["capabilities"] = asdict(self.capabilities)
        return value


@dataclass
class JobSpec:
    project_path: str
    arguments: dict[str, Any] = field(default_factory=dict)
    requirements: dict[str, Any] = field(default_factory=dict)
    experiment_id: str | None = None
    priority: int = 0
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
