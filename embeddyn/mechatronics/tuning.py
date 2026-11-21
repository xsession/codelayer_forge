"""Parameter tuning: run the co-simulation repeatedly and minimise a metric objective.

```yaml
project: ../dc-motor.yaml
mock: false                     # true forces the built-in simulators
duration: 1.0                   # optional: override the project duration
parameters:                     # project parameters (they reach adapters as inputs)
  controller.kp: {initial: 0.12, min: 0.01, max: 2.0, scale: log}
  controller.ki: {initial: 0.8, min: 0.05, max: 20.0, scale: log}
objective:                      # minimise sum(weight * metric)
  - {metric: speed.itae, weight: 1.0}
constraints:                    # violations add a penalty (missing value = violated)
  - {metric: speed.overshoot, max: 5.0}
  - {metric: speed.settling_time, max: 0.6}
max_evaluations: 40
```

The optimiser is a bounded Nelder-Mead in a normalised space (0..1 per
parameter, logarithmic when `scale: log`). It is deterministic: the same file
gives the same evaluation sequence. Every evaluation is a full co-simulation,
so firmware gains can be tuned in real Renode firmware through bindings to the
parameter names.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import yaml

from .factory import build_adapters
from .metrics import compute_metrics, parse_metric_specs, select_metrics
from .model import MechatronicProject
from .orchestrator import CoSimulationOrchestrator

CONSTRAINT_PENALTY = 1e3      # per unit of normalised violation
MISSING_PENALTY = 1e6         # metric not computed (e.g. never settles)


@dataclass(frozen=True)
class TunedParameter:
    name: str
    initial: float
    minimum: float
    maximum: float
    log: bool = False

    def to_unit(self, value: float) -> float:
        value = min(max(value, self.minimum), self.maximum)
        if self.log:
            return (math.log(value) - math.log(self.minimum)) / (math.log(self.maximum) - math.log(self.minimum))
        return (value - self.minimum) / (self.maximum - self.minimum)

    def from_unit(self, unit: float) -> float:
        unit = min(max(unit, 0.0), 1.0)
        if self.log:
            return math.exp(math.log(self.minimum) + unit * (math.log(self.maximum) - math.log(self.minimum)))
        return self.minimum + unit * (self.maximum - self.minimum)


@dataclass(frozen=True)
class ObjectiveTerm:
    metric: str
    weight: float = 1.0


@dataclass(frozen=True)
class Constraint:
    metric: str
    minimum: float | None = None
    maximum: float | None = None


@dataclass
class TuningSpec:
    project: Path
    parameters: list[TunedParameter]
    objective: list[ObjectiveTerm]
    constraints: list[Constraint] = field(default_factory=list)
    mock: bool = False
    duration: float | None = None
    max_evaluations: int = 40
    tolerance: float = 1e-4


def load_tuning_spec(path: Path) -> TuningSpec:
    path = path.resolve()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    project = Path(str(raw.get("project", "")))
    if not str(project):
        raise ValueError("tuning spec needs 'project'")
    if not project.is_absolute():
        project = (path.parent / project).resolve()
    parameters = []
    for name, entry in dict(raw.get("parameters") or {}).items():
        entry = dict(entry or {})
        minimum, maximum = float(entry["min"]), float(entry["max"])
        log = str(entry.get("scale", "linear")).lower() in {"log", "logarithmic"}
        if not minimum < maximum or (log and minimum <= 0):
            raise ValueError(f"parameter {name}: need min < max (and min > 0 for log scale)")
        initial = float(entry.get("initial", math.sqrt(minimum * maximum) if log else (minimum + maximum) / 2))
        parameters.append(TunedParameter(str(name), initial, minimum, maximum, log))
    if not parameters:
        raise ValueError("tuning spec needs at least one parameter")
    objective = [ObjectiveTerm(str(item["metric"]), float(item.get("weight", 1.0)))
                 for item in raw.get("objective") or []]
    if not objective:
        raise ValueError("tuning spec needs an objective")
    constraints = [Constraint(str(item["metric"]),
                              None if item.get("min") is None else float(item["min"]),
                              None if item.get("max") is None else float(item["max"]))
                   for item in raw.get("constraints") or []]
    return TuningSpec(project, parameters, objective, constraints, bool(raw.get("mock", False)),
                      None if raw.get("duration") is None else float(raw["duration"]),
                      int(raw.get("max_evaluations", 40)), float(raw.get("tolerance", 1e-4)))


def simulate(spec: TuningSpec, values: Mapping[str, float]) -> dict[str, float | None]:
    """One full co-simulation with the given parameter values; returns its metrics."""
    project = MechatronicProject.load(spec.project)
    if spec.duration is not None:
        project.duration_seconds = spec.duration
    project.apply_parameter_overrides(dict(values), source="tuning")
    if not project.metrics:
        raise ValueError(f"{spec.project} declares no metrics to tune against")
    rows = CoSimulationOrchestrator(project, build_adapters(project, mock=spec.mock)).run()
    return compute_metrics(rows, parse_metric_specs(project.metrics))


def score(spec: TuningSpec, metrics: Mapping[str, float | None]) -> tuple[float, list[str]]:
    total, violations = 0.0, []
    for term in spec.objective:
        value = select_metrics(metrics, [term.metric])[term.metric]
        if value is None or not math.isfinite(value):
            total += MISSING_PENALTY
            violations.append(f"{term.metric} not available")
        else:
            total += term.weight * value
    for constraint in spec.constraints:
        value = select_metrics(metrics, [constraint.metric])[constraint.metric]
        if value is None or not math.isfinite(value):
            total += MISSING_PENALTY
            violations.append(f"{constraint.metric} not available")
            continue
        for bound, excess in ((constraint.maximum, None if constraint.maximum is None else value - constraint.maximum),
                              (constraint.minimum, None if constraint.minimum is None else constraint.minimum - value)):
            if excess is not None and excess > 0:
                total += CONSTRAINT_PENALTY * (1.0 + excess / max(abs(bound), 1e-9))
                violations.append(f"{constraint.metric}={value:.6g} violates {'max' if bound == constraint.maximum else 'min'} {bound:g}")
    return total, violations


def nelder_mead(function: Callable[[list[float]], float], start: Sequence[float], max_evaluations: int,
                tolerance: float = 1e-4, initial_step: float = 0.15) -> tuple[list[float], float]:
    """Minimise `function` over the unit box (coordinates clipped to [0, 1])."""
    clip = lambda point: [min(max(x, 0.0), 1.0) for x in point]
    evaluations = 0

    def evaluate(point):
        nonlocal evaluations
        evaluations += 1
        return function(clip(point))

    dimension = len(start)
    simplex = [clip(list(start))]
    for i in range(dimension):
        vertex = list(simplex[0])
        vertex[i] = vertex[i] + initial_step if vertex[i] + initial_step <= 1.0 else vertex[i] - initial_step
        simplex.append(vertex)
    values = [evaluate(point) for point in simplex]
    while evaluations < max_evaluations:
        order = sorted(range(len(simplex)), key=lambda i: values[i])
        simplex, values = [simplex[i] for i in order], [values[i] for i in order]
        size = max(max(abs(a - b) for a, b in zip(vertex, simplex[0])) for vertex in simplex[1:])
        if size < tolerance:
            break
        centroid = [sum(vertex[k] for vertex in simplex[:-1]) / dimension for k in range(dimension)]
        worst = simplex[-1]
        reflected = clip([c + (c - w) for c, w in zip(centroid, worst)])
        reflected_value = evaluate(reflected)
        if reflected_value < values[0] and evaluations < max_evaluations:
            expanded = clip([c + 2 * (c - w) for c, w in zip(centroid, worst)])
            expanded_value = evaluate(expanded)
            simplex[-1], values[-1] = (expanded, expanded_value) if expanded_value < reflected_value else (reflected, reflected_value)
        elif reflected_value < values[-2]:
            simplex[-1], values[-1] = reflected, reflected_value
        else:
            contracted = clip([c + 0.5 * (w - c) for c, w in zip(centroid, worst)])
            contracted_value = evaluate(contracted) if evaluations < max_evaluations else math.inf
            if contracted_value < values[-1]:
                simplex[-1], values[-1] = contracted, contracted_value
            else:
                for i in range(1, len(simplex)):
                    if evaluations >= max_evaluations:
                        break
                    simplex[i] = clip([b + 0.5 * (x - b) for b, x in zip(simplex[0], simplex[i])])
                    values[i] = evaluate(simplex[i])
    best = min(range(len(simplex)), key=lambda i: values[i])
    return simplex[best], values[best]


def tune(spec: TuningSpec, progress: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    history: list[dict[str, Any]] = []

    def objective(unit_point: list[float]) -> float:
        values = {p.name: p.from_unit(u) for p, u in zip(spec.parameters, unit_point)}
        started = time.monotonic()
        try:
            metrics = simulate(spec, values)
            value, violations = score(spec, metrics)
            error = None
        except Exception as exc:  # a diverging candidate must not stop the search
            metrics, value, violations, error = {}, math.inf, [], f"{type(exc).__name__}: {exc}"
        record = {"evaluation": len(history) + 1, "parameters": values, "objective": value,
                  "violations": violations, "metrics": metrics, "seconds": round(time.monotonic() - started, 3)}
        if error:
            record["error"] = error
        history.append(record)
        if progress:
            progress(record)
        return value

    start = [p.to_unit(p.initial) for p in spec.parameters]
    nelder_mead(objective, start, spec.max_evaluations, spec.tolerance)
    finite = [record for record in history if math.isfinite(record["objective"])]
    if not finite:
        raise RuntimeError("every tuning evaluation failed; first error: " + str(history[0].get("error")))
    best = min(finite, key=lambda record: record["objective"])
    return {
        "project": str(spec.project),
        "evaluations": len(history),
        "initial": history[0],
        "best": best,
        "feasible": not best["violations"],
        "history": history,
    }


def write_result(result: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, default=lambda value: None), encoding="utf-8")
