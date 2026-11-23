from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any, Iterable
import math
import uuid
import yaml

from .models import JobSpec


@dataclass(frozen=True)
class ExperimentExpansion:
    experiment_id: str
    name: str
    jobs: tuple[JobSpec, ...]
    source: dict[str, Any]


def _range_values(spec: dict[str, Any]) -> list[float]:
    start = float(spec["start"])
    stop = float(spec["stop"])
    count = int(spec["count"])
    if count < 1:
        raise ValueError("experiment range count must be positive")
    if count == 1:
        return [start]
    scale = str(spec.get("scale", "linear"))
    if scale == "linear":
        return [start + (stop - start) * i / (count - 1) for i in range(count)]
    if scale == "logarithmic":
        if start <= 0 or stop <= 0:
            raise ValueError("logarithmic ranges require positive bounds")
        lo, hi = math.log(start), math.log(stop)
        return [math.exp(lo + (hi - lo) * i / (count - 1)) for i in range(count)]
    raise ValueError(f"unsupported experiment range scale: {scale}")


def _variable_values(spec: Any) -> list[Any]:
    if isinstance(spec, dict) and "values" in spec:
        values = list(spec["values"])
    elif isinstance(spec, dict) and "range" in spec:
        values = _range_values(dict(spec["range"]))
    else:
        raise ValueError("experiment variable requires values or range")
    if not values:
        raise ValueError("experiment variable values cannot be empty")
    return values


def expand_experiment(raw: dict[str, Any], source_path: Path | None = None) -> ExperimentExpansion:
    name = str(raw.get("name", "experiment"))
    experiment_id = str(raw.get("experiment_id") or uuid.uuid4().hex)
    variables = dict(raw.get("variables") or {})
    names = sorted(variables)
    value_sets = [_variable_values(variables[name]) for name in names]
    combinations: Iterable[tuple[Any, ...]] = product(*value_sets) if names else [()]
    project_path = str(raw.get("project") or raw.get("base_project") or "")
    if source_path and project_path and not Path(project_path).is_absolute():
        project_path = str((source_path.parent / project_path).resolve())
    if not project_path:
        raise ValueError("experiment requires project or base_project")
    requirements = dict(raw.get("requirements") or {})
    base_arguments = dict(raw.get("arguments") or {})
    priority = int(raw.get("priority", 0))
    jobs = []
    for index, values in enumerate(combinations):
        overrides = dict(zip(names, values))
        arguments = dict(base_arguments)
        arguments["parameter_overrides"] = overrides
        arguments["experiment_index"] = index
        if raw.get("metrics"):
            arguments["metrics"] = [str(name) for name in raw["metrics"]]
        jobs.append(JobSpec(
            project_path=project_path,
            arguments=arguments,
            requirements=requirements,
            experiment_id=experiment_id,
            priority=priority,
        ))
    max_jobs = int(raw.get("max_jobs", 10000))
    if len(jobs) > max_jobs:
        raise ValueError(f"experiment expands to {len(jobs)} jobs, exceeding max_jobs={max_jobs}")
    return ExperimentExpansion(experiment_id, name, tuple(jobs), raw)


def load_experiment(path: Path) -> ExperimentExpansion:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return expand_experiment(raw, path.resolve())
