"""Physical parameter estimation from bench measurements.

Fits model parameters (project parameters, or constant signals such as
`electrical.motor_resistance`) so that the co-simulation reproduces measured
traces, by nonlinear least squares over full runs:

```yaml
project: ../dc-motor.yaml
measurements: bench/step-test.csv      # time + measured columns (relative to this file)
disable: [firmware]                    # instances replaced by the recorded input
fixed: {electrical.motor_inductance: 0.0045}   # known values, held constant
replay:                                # recorded inputs driven into the model
  domain: firmware
  columns: {duty: firmware.pwm_duty}
fit:                                   # model signal -> measured column (+ noise sigma)
  electrical.motor_current: {column: current, sigma: 0.05}
  mechanical.velocity: {column: speed, sigma: 0.02}
parameters:
  electrical.motor_resistance: {initial: 1.0, min: 0.1, max: 10, scale: log}
  mechanical.inertia: {initial: 0.05, min: 0.001, max: 1, scale: log}
max_iterations: 30
```

The optimiser is Levenberg-Marquardt in a bounded space (logarithmic for
`scale: log`), with a forward-difference Jacobian (one run per parameter per
iteration). The covariance at the solution is s^2 (J^T J)^-1 with s^2 the
reduced chi-square, which gives standard errors, 95 % confidence intervals
and the parameter correlation matrix (|r| near 1 means the data can't
separate those parameters).
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import yaml

from .adapters.replay import read_columns
from .factory import build_adapters
from .model import Domain, MechatronicProject, SimulatorConfig
from .orchestrator import CoSimulationOrchestrator

Z95 = 1.959963984540054


@dataclass(frozen=True)
class EstimatedParameter:
    name: str
    initial: float
    minimum: float
    maximum: float
    log: bool = False

    def to_z(self, value: float) -> float:
        value = min(max(value, self.minimum), self.maximum)
        return math.log(value) if self.log else value

    def from_z(self, z: float) -> float:
        value = math.exp(z) if self.log else z
        return min(max(value, self.minimum), self.maximum)

    def clip_z(self, z: float) -> float:
        return self.to_z(self.from_z(z))


@dataclass(frozen=True)
class FitSignal:
    signal: str
    column: str
    sigma: float = 1.0


@dataclass
class EstimationSpec:
    project: Path
    measurements: Path
    parameters: list[EstimatedParameter]
    fit: list[FitSignal]
    time_column: str = "time"
    disable: list[str] = field(default_factory=list)
    replay: dict[str, Any] | None = None
    max_iterations: int = 30
    tolerance: float = 1e-8
    fixed: dict[str, float] = field(default_factory=dict)


def load_estimation_spec(path: Path) -> EstimationSpec:
    path = path.resolve()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def resolve(value: Any) -> Path:
        candidate = Path(str(value))
        return candidate if candidate.is_absolute() else (path.parent / candidate).resolve()

    for key in ("project", "measurements", "parameters", "fit"):
        if not raw.get(key):
            raise ValueError(f"estimation spec needs '{key}'")
    parameters = []
    for name, entry in dict(raw["parameters"]).items():
        entry = dict(entry or {})
        minimum, maximum = float(entry["min"]), float(entry["max"])
        log = str(entry.get("scale", "linear")).lower() in {"log", "logarithmic"}
        if not minimum < maximum or (log and minimum <= 0):
            raise ValueError(f"parameter {name}: need min < max (and min > 0 for log scale)")
        initial = float(entry.get("initial", math.sqrt(minimum * maximum) if log else (minimum + maximum) / 2))
        parameters.append(EstimatedParameter(str(name), initial, minimum, maximum, log))
    fit = []
    for signal, entry in dict(raw["fit"]).items():
        entry = {"column": entry} if isinstance(entry, str) else dict(entry or {})
        sigma = float(entry.get("sigma", 1.0))
        if sigma <= 0:
            raise ValueError(f"fit {signal}: sigma must be positive")
        fit.append(FitSignal(str(signal), str(entry.get("column", signal)), sigma))
    replay = dict(raw["replay"]) if raw.get("replay") else None
    return EstimationSpec(resolve(raw["project"]), resolve(raw["measurements"]), parameters, fit,
                          str(raw.get("time_column", "time")), [str(x) for x in raw.get("disable") or []], replay,
                          int(raw.get("max_iterations", 30)), float(raw.get("tolerance", 1e-8)),
                          {str(k): float(v) for k, v in dict(raw.get("fixed") or {}).items()})


# -- model evaluation ----------------------------------------------------------

def build_project(spec: EstimationSpec, values: Mapping[str, float], duration: float) -> MechatronicProject:
    project = MechatronicProject.load(spec.project)
    project.duration_seconds = duration
    instances = project.simulator_instances()
    for name in spec.disable:
        if name not in instances:
            raise ValueError(f"cannot disable unknown simulator instance {name}")
        config = instances[name]
        project.instances[name] = replace(config, enabled=False) if name not in project.instances else config
        project.instances[name].enabled = False
    if spec.replay:
        domain = Domain(spec.replay.get("domain", "environment"))
        project.instances["estimation_replay"] = SimulatorConfig(
            name="estimation_replay", domain=domain, model=str(spec.measurements),
            options={"backend": "replay", "columns": dict(spec.replay.get("columns") or {}),
                     "interpolation": str(spec.replay.get("interpolation", "previous")),
                     "time_column": spec.time_column})
    overrides = {}
    for name, value in {**spec.fixed, **values}.items():
        if name in project.signals:
            project.signals[name] = replace(project.signals[name], initial=float(value))
        else:
            overrides[name] = value
    if overrides:
        project.apply_parameter_overrides(overrides, source="estimation")
    return project


def _interpolate(times: Sequence[float], values: Sequence[float], at: float) -> float:
    import bisect
    if at <= times[0]:
        return values[0]
    if at >= times[-1]:
        return values[-1]
    i = bisect.bisect_right(times, at) - 1
    return values[i] + (values[i + 1] - values[i]) * (at - times[i]) / (times[i + 1] - times[i])


class Problem:
    """Residual vector (simulated − measured) / sigma over all fitted signals."""

    def __init__(self, spec: EstimationSpec) -> None:
        self.spec = spec
        self.times, self.columns = read_columns(spec.measurements, spec.time_column)
        missing = [f.column for f in spec.fit if f.column not in self.columns]
        if missing:
            raise ValueError(f"{spec.measurements}: no columns {', '.join(missing)}")
        self.duration = self.times[-1]
        self.evaluations = 0

    def simulate(self, values: Mapping[str, float]) -> dict[str, list[float]]:
        project = build_project(self.spec, values, self.duration)
        for f in self.spec.fit:
            if f.signal not in project.signals:
                raise ValueError(f"fit signal {f.signal} is not in the project")
        rows = CoSimulationOrchestrator(project, build_adapters(project)).run()
        self.evaluations += 1
        sim_times = [float(row["time"]) for row in rows]
        return {f.signal: [_interpolate(sim_times, [float(row[f.signal]) for row in rows], t) for t in self.times]
                for f in self.spec.fit}

    def residuals(self, values: Mapping[str, float]) -> list[float]:
        simulated = self.simulate(values)
        out = []
        for f in self.spec.fit:
            out.extend((s - m) / f.sigma for s, m in zip(simulated[f.signal], self.columns[f.column]))
        return out


# -- linear algebra (small dense systems) --------------------------------------

def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    n = len(vector)
    a = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-300:
            raise ZeroDivisionError("singular matrix")
        a[col], a[pivot] = a[pivot], a[col]
        for r in range(n):
            if r != col:
                factor = a[r][col] / a[col][col]
                for c in range(col, n + 1):
                    a[r][c] -= factor * a[col][c]
    return [a[i][n] / a[i][i] for i in range(n)]


def _inverse(matrix: list[list[float]]) -> list[list[float]]:
    n = len(matrix)
    columns = [_solve(matrix, [1.0 if i == j else 0.0 for i in range(n)]) for j in range(n)]
    return [[columns[j][i] for j in range(n)] for i in range(n)]


def _normal(jacobian: list[list[float]], residuals: list[float]) -> tuple[list[list[float]], list[float]]:
    n = len(jacobian[0])
    jtj = [[sum(row[i] * row[j] for row in jacobian) for j in range(n)] for i in range(n)]
    jtr = [sum(row[i] * r for row, r in zip(jacobian, residuals)) for i in range(n)]
    return jtj, jtr


# -- Levenberg-Marquardt -------------------------------------------------------

def estimate(spec: EstimationSpec, progress: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    problem = Problem(spec)
    params = spec.parameters
    started = time.monotonic()

    def values_of(z: Sequence[float]) -> dict[str, float]:
        return {p.name: p.from_z(zi) for p, zi in zip(params, z)}

    def ssr(r: Sequence[float]) -> float:
        return sum(x * x for x in r)

    def jacobian(z: list[float], r0: list[float]) -> list[list[float]]:
        columns = []
        for k, p in enumerate(params):
            h = 1e-4 * max(1.0, abs(z[k])) if not p.log else 1e-4
            trial = list(z)
            trial[k] = p.clip_z(z[k] + h)
            if trial[k] == z[k]:                      # at the upper bound: step inward
                trial[k] = p.clip_z(z[k] - h)
            delta = trial[k] - z[k]
            rk = problem.residuals(values_of(trial))
            columns.append([(a - b) / delta for a, b in zip(rk, r0)])
        return [list(row) for row in zip(*columns)]

    z = [p.to_z(p.initial) for p in params]
    r = problem.residuals(values_of(z))
    cost = ssr(r)
    initial_cost, lam, history = cost, 1e-3, []
    for iteration in range(1, spec.max_iterations + 1):
        jac = jacobian(z, r)
        jtj, jtr = _normal(jac, r)
        improved = False
        for _ in range(12):
            damped = [[jtj[i][j] + (lam * max(jtj[i][i], 1e-12) if i == j else 0.0) for j in range(len(z))]
                      for i in range(len(z))]
            try:
                step = _solve(damped, [-g for g in jtr])
            except ZeroDivisionError:
                lam *= 10
                continue
            trial = [p.clip_z(zi + si) for p, zi, si in zip(params, z, step)]
            trial_r = problem.residuals(values_of(trial))
            trial_cost = ssr(trial_r)
            if trial_cost < cost:
                change = (cost - trial_cost) / max(cost, 1e-300)
                z, r, cost, lam, improved = trial, trial_r, trial_cost, max(lam / 3, 1e-12), True
                break
            lam *= 4
        record = {"iteration": iteration, "cost": cost, "lambda": lam, "parameters": values_of(z),
                  "evaluations": problem.evaluations}
        history.append(record)
        if progress:
            progress(record)
        if not improved or change < spec.tolerance:
            break

    # Statistics at the solution, in natural parameter units.
    jac = jacobian(z, r)
    natural = values_of(z)
    for k, p in enumerate(params):
        if p.log:
            for row in jac:
                row[k] /= natural[p.name]
    m, n = len(r), len(params)
    dof = max(1, m - n)
    variance = cost / dof
    jtj, _ = _normal(jac, r)
    try:
        covariance = [[variance * x for x in row] for row in _inverse(jtj)]
    except ZeroDivisionError:
        covariance = None
    results = {}
    for k, p in enumerate(params):
        value = natural[p.name]
        std = math.sqrt(covariance[k][k]) if covariance and covariance[k][k] >= 0 else None
        at_bound = math.isclose(value, p.minimum, rel_tol=1e-6) or math.isclose(value, p.maximum, rel_tol=1e-6)
        results[p.name] = {
            "estimate": value, "initial": p.initial, "std_error": std,
            "ci95": [value - Z95 * std, value + Z95 * std] if std is not None else None,
            "relative_ci95_percent": 100 * Z95 * std / abs(value) if std is not None and value else None,
            "at_bound": at_bound,
        }
    correlation = None
    if covariance:
        correlation = {params[i].name: {params[j].name: covariance[i][j] / math.sqrt(covariance[i][i] * covariance[j][j])
                                        for j in range(n)} for i in range(n)}
    simulated = problem.simulate(natural)
    fit_quality = {}
    for f in spec.fit:
        measured = problem.columns[f.column]
        errors = [s - m_ for s, m_ in zip(simulated[f.signal], measured)]
        mean = sum(measured) / len(measured)
        total = sum((x - mean) ** 2 for x in measured)
        fit_quality[f.signal] = {"rmse": math.sqrt(sum(e * e for e in errors) / len(errors)),
                                 "r_squared": 1 - sum(e * e for e in errors) / total if total > 0 else None}
    return {
        "project": str(spec.project), "measurements": str(spec.measurements),
        "samples": m, "parameters": results, "correlation": correlation, "fit": fit_quality,
        "cost": {"initial": initial_cost, "final": cost, "reduced_chi_square": variance},
        "iterations": len(history), "evaluations": problem.evaluations,
        "seconds": round(time.monotonic() - started, 2), "history": history,
    }


def write_result(result: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, default=lambda value: None), encoding="utf-8")
