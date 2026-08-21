from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from .quantities import Quantity


class Domain(str, Enum):
    FIRMWARE = "firmware"
    MECHANICAL = "mechanical"
    ELECTRICAL = "electrical"
    THERMAL = "thermal"
    ENVIRONMENT = "environment"


class SignalKind(str, Enum):
    CONTINUOUS = "continuous"
    DISCRETE = "discrete"
    EVENT = "event"
    BUS = "bus"


@dataclass(frozen=True)
class Signal:
    name: str
    domain: Domain
    unit: str = ""
    initial: float = 0.0
    minimum: float | None = None
    maximum: float | None = None
    data_type: str = "float64"
    kind: SignalKind = SignalKind.CONTINUOUS
    quantity: str | None = None
    retention: str = "full"

    def clamp(self, value: float) -> float:
        if self.minimum is not None:
            value = max(self.minimum, value)
        if self.maximum is not None:
            value = min(self.maximum, value)
        return value


@dataclass(frozen=True)
class Transform:
    type: str = "affine"
    gain: float = 1.0
    offset: float = 0.0
    minimum: float | None = None
    maximum: float | None = None
    deadband: float = 0.0

    def apply(self, value: float) -> float:
        if self.type == "identity":
            result = value
        elif self.type == "affine":
            result = self.gain * value + self.offset
        elif self.type == "clamp":
            result = value
        elif self.type == "deadband":
            result = 0.0 if abs(value) < self.deadband else value
        elif self.type == "quantize":
            quantum = self.gain
            if quantum <= 0:
                raise ValueError("quantize transform requires gain/quantum > 0")
            result = round(value / quantum) * quantum + self.offset
        else:
            raise ValueError(f"unsupported coupling transform: {self.type}")
        if self.minimum is not None:
            result = max(self.minimum, result)
        if self.maximum is not None:
            result = min(self.maximum, result)
        return result


@dataclass(frozen=True)
class Coupling:
    source: str
    target: str
    transform: Transform = field(default_factory=Transform)
    delay_steps: int = 0
    interpolation: str = "zero_order_hold"
    extrapolation: str = "hold"

    @property
    def gain(self) -> float:
        return self.transform.gain

    @property
    def offset(self) -> float:
        return self.transform.offset


@dataclass
class SimulatorConfig:
    enabled: bool = True
    executable: str | None = None
    model: str | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConvergenceConfig:
    enabled: bool = False
    tolerance: float = 1e-9
    max_iterations: int = 8
    failure_policy: str = "error"


@dataclass(frozen=True)
class RealTimeConfig:
    enabled: bool = False
    speed_factor: float = 1.0
    deadline_tolerance_seconds: float = 0.01
    missed_deadline_policy: str = "continue"


@dataclass(frozen=True)
class SchedulerConfig:
    algorithm: str = "deterministic-fixed-step"
    macro_step_seconds: float = 0.001
    domain_steps: dict[Domain, float] = field(default_factory=dict)
    convergence: ConvergenceConfig = field(default_factory=ConvergenceConfig)
    real_time: RealTimeConfig = field(default_factory=RealTimeConfig)

    def step_for(self, domain: Domain) -> float:
        return self.domain_steps.get(domain, self.macro_step_seconds)


@dataclass
class MechatronicProject:
    name: str
    step_seconds: float
    duration_seconds: float
    signals: dict[str, Signal]
    couplings: list[Coupling]
    simulators: dict[Domain, SimulatorConfig]
    root: Path
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1
    scheduler: SchedulerConfig | None = None
    parameters: dict[str, Quantity] = field(default_factory=dict)
    parameter_provenance: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    component_definitions: dict[str, dict[str, Any]] = field(default_factory=dict)
    component_instances: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "MechatronicProject":
        path = path.resolve()
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        schema_version = int(raw.get("schema_version", 1))
        signals: dict[str, Signal] = {}
        for name, spec in (raw.get("signals") or {}).items():
            spec = spec or {}
            initial = Quantity.parse(spec.get("initial", 0.0), str(spec.get("unit", "")))
            signals[name] = Signal(
                name=name,
                domain=Domain(spec.get("domain", "environment")),
                unit=initial.unit or str(spec.get("unit", "")),
                initial=initial.value,
                minimum=_optional_quantity(spec.get("min"), initial.unit),
                maximum=_optional_quantity(spec.get("max"), initial.unit),
                data_type=str(spec.get("data_type", "float64")),
                kind=SignalKind(spec.get("kind", "continuous")),
                quantity=spec.get("quantity"),
                retention=str(spec.get("retention", "full")),
            )
        couplings = [_parse_coupling(item) for item in (raw.get("couplings") or [])]
        sims: dict[Domain, SimulatorConfig] = {}
        for key, spec in (raw.get("simulators") or {}).items():
            spec = spec or {}
            sims[Domain(key)] = SimulatorConfig(
                enabled=bool(spec.get("enabled", True)),
                executable=spec.get("executable"),
                model=spec.get("model"),
                options=dict(spec.get("options") or {}),
            )
        step_seconds = Quantity.parse(raw.get("step_seconds", raw.get("scheduler", {}).get("macro_step", 0.001)), "s").value
        scheduler = _parse_scheduler(raw.get("scheduler") or {}, step_seconds)
        parameters: dict[str, Quantity] = {}
        provenance: dict[str, list[dict[str, Any]]] = {}
        for name, value in (raw.get("parameters") or {}).items():
            quantity = Quantity.parse(value.get("value", value) if isinstance(value, dict) else value,
                                      str(value.get("unit", "")) if isinstance(value, dict) else "")
            parameters[name] = quantity
            provenance[name] = list(value.get("provenance") or []) if isinstance(value, dict) else []
            if not provenance[name]:
                provenance[name] = [{"source": "project", "value": quantity.value, "unit": quantity.unit}]
        components = raw.get("components") or {}
        definitions = dict(components.get("definitions") or {})
        instances = dict(components.get("instances") or {})
        # Instance parameter overrides participate in the resolved parameter set.
        for instance_name, instance in instances.items():
            for param_name, raw_value in dict((instance or {}).get("parameters") or {}).items():
                key = f"{instance_name}.{param_name}"
                q = Quantity.parse(raw_value.get("value", raw_value) if isinstance(raw_value, dict) else raw_value,
                                   str(raw_value.get("unit", "")) if isinstance(raw_value, dict) else "")
                parameters[key] = q
                provenance[key] = [{"source": "component-instance", "component": instance_name,
                                    "value": q.value, "unit": q.unit}]
        project = cls(
            name=str(raw.get("name", path.stem)),
            step_seconds=step_seconds,
            duration_seconds=Quantity.parse(raw.get("duration_seconds", 1.0), "s").value,
            signals=signals,
            couplings=couplings,
            simulators=sims,
            root=path.parent,
            metadata=dict(raw.get("metadata") or {}),
            schema_version=schema_version,
            scheduler=scheduler,
            parameters=parameters,
            parameter_provenance=provenance,
            component_definitions=definitions,
            component_instances=instances,
        )
        project.validate()
        return project

    def validate(self) -> None:
        if self.schema_version not in {1, 2}:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.step_seconds <= 0:
            raise ValueError("step_seconds must be positive")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        if self.scheduler and self.scheduler.algorithm not in {"deterministic-fixed-step", "multirate-fixed-step", "real-time-fixed-step", "real-time-multirate"}:
            raise ValueError(f"unsupported scheduler algorithm: {self.scheduler.algorithm}")
        for domain, step in (self.scheduler.domain_steps if self.scheduler else {}).items():
            if step <= 0:
                raise ValueError(f"scheduler step for {domain.value} must be positive")
            ratio = self.step_seconds / step
            if abs(ratio - round(ratio)) > 1e-9:
                raise ValueError(f"domain step for {domain.value} must divide macro step")
        if self.scheduler:
            if self.scheduler.convergence.tolerance <= 0 or self.scheduler.convergence.max_iterations < 1:
                raise ValueError("invalid scheduler convergence configuration")
            if self.scheduler.convergence.failure_policy not in {"error", "warn", "accept"}:
                raise ValueError("unsupported convergence failure policy")
            if self.scheduler.real_time.speed_factor <= 0:
                raise ValueError("real-time speed_factor must be positive")
            if self.scheduler.real_time.missed_deadline_policy not in {"continue", "warn", "abort"}:
                raise ValueError("unsupported missed deadline policy")
        for name, instance in self.component_instances.items():
            definition = (instance or {}).get("definition")
            if definition and definition not in self.component_definitions:
                raise ValueError(f"component instance {name} references unknown definition {definition}")
        for coupling in self.couplings:
            if coupling.source not in self.signals:
                raise ValueError(f"unknown coupling source: {coupling.source}")
            if coupling.target not in self.signals:
                raise ValueError(f"unknown coupling target: {coupling.target}")
            if coupling.delay_steps < 0:
                raise ValueError("delay_steps cannot be negative")
            source_unit = self.signals[coupling.source].unit
            target_unit = self.signals[coupling.target].unit
            if coupling.transform.type in {"identity", "clamp", "deadband"} and source_unit and target_unit and source_unit != target_unit:
                raise ValueError(f"unit mismatch for {coupling.source} -> {coupling.target}: {source_unit} != {target_unit}")

    def resolve(self, value: str | None) -> Path | None:
        if not value:
            return None
        path = Path(value)
        return path if path.is_absolute() else (self.root / path).resolve()


def _parse_coupling(item: dict[str, Any]) -> Coupling:
    if item.get("expression"):
        raise ValueError("unsafe coupling expressions are no longer supported; use a typed transform")
    transform_raw = item.get("transform") or {}
    if not transform_raw:
        transform_raw = {"type": "affine", "gain": item.get("gain", 1.0), "offset": item.get("offset", 0.0)}
    timing = item.get("timing") or {}
    return Coupling(
        source=item["source"],
        target=item["target"],
        transform=Transform(
            type=str(transform_raw.get("type", "affine")),
            gain=float(transform_raw.get("gain", transform_raw.get("quantum", 1.0))),
            offset=float(transform_raw.get("offset", 0.0)),
            minimum=_optional_float(transform_raw.get("min", transform_raw.get("minimum"))),
            maximum=_optional_float(transform_raw.get("max", transform_raw.get("maximum"))),
            deadband=float(transform_raw.get("deadband", 0.0)),
        ),
        delay_steps=int(item.get("delay_steps", timing.get("delay_steps", 0))),
        interpolation=str(timing.get("interpolation", "zero_order_hold")),
        extrapolation=str(timing.get("extrapolation", "hold")),
    )


def _parse_scheduler(raw: dict[str, Any], default_step: float) -> SchedulerConfig:
    domain_steps: dict[Domain, float] = {}
    for key, spec in (raw.get("domains") or {}).items():
        value = spec.get("step") if isinstance(spec, dict) else spec
        domain_steps[Domain(key)] = Quantity.parse(value, "s").value
    convergence = raw.get("convergence") or {}
    real_time = raw.get("real_time") or {}
    algorithm = str(raw.get("algorithm", "multirate-fixed-step" if domain_steps else "deterministic-fixed-step"))
    return SchedulerConfig(
        algorithm=algorithm,
        macro_step_seconds=Quantity.parse(raw.get("macro_step", default_step), "s").value,
        domain_steps=domain_steps,
        convergence=ConvergenceConfig(
            enabled=bool(convergence.get("enabled", False)),
            tolerance=float(convergence.get("tolerance", 1e-9)),
            max_iterations=int(convergence.get("max_iterations", 8)),
            failure_policy=str(convergence.get("failure_policy", "error")),
        ),
        real_time=RealTimeConfig(
            enabled=bool(real_time.get("enabled", algorithm.startswith("real-time"))),
            speed_factor=float(real_time.get("speed_factor", 1.0)),
            deadline_tolerance_seconds=Quantity.parse(real_time.get("deadline_tolerance", 0.01), "s").value,
            missed_deadline_policy=str(real_time.get("missed_deadline_policy", "continue")),
        ),
    )


def _optional_quantity(value: Any, unit: str) -> float | None:
    return None if value is None else Quantity.parse(value, unit).value


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)
