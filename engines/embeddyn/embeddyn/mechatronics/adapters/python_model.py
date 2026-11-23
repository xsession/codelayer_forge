"""Co-simulate a Python plant model (ODE) with fixed-step RK4 sub-stepping.

A plant is a class with:

```python
class MyPlant:
    inputs = ("torque",)                      # names read each step (held constant)
    outputs = ("speed", "angle")              # names written each step
    states = ("angle", "speed")               # continuous state vector
    def __init__(self, **parameters): ...
    def initial_state(self) -> list[float]: ...
    def derivatives(self, t, x, u) -> list[float]: ...   # u: dict of inputs
    def output(self, t, x, u) -> dict[str, float]: ...
```

Configured as:

```yaml
mechanical:
  model: "embeddyn.mechatronics.plants:GearedDrivetrain"   # or "plants/my.py:MyPlant"
  options:
    backend: python
    max_step: 1.0e-5
    parameters: {gear_ratio: 10, backlash: "@drivetrain.backlash"}   # "@name": project parameter
    inputs: {motor_torque: mechanical.motor_torque}
    outputs: {motor_speed: mechanical.velocity}
```
"""
from __future__ import annotations

import importlib
import importlib.util
import math
import sys
from pathlib import Path
from typing import Any, Mapping

from .base import SimulatorAdapter, StepResult


def load_plant_class(reference: str, root: Path | None = None) -> type:
    """`package.module:Class` or `path/to/file.py:Class` (relative to the project)."""
    if ":" not in reference:
        raise ValueError(f"plant model {reference!r} must be 'module:Class' or 'file.py:Class'")
    location, class_name = reference.rsplit(":", 1)
    if location.endswith(".py"):
        path = Path(location)
        if not path.is_absolute() and root is not None:
            path = (root / path).resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        module_name = f"embeddyn_plant_{abs(hash(str(path)))}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    else:
        module = importlib.import_module(location)
    try:
        return getattr(module, class_name)
    except AttributeError as error:
        raise ValueError(f"{location} has no class {class_name}") from error


class PythonModelAdapter(SimulatorAdapter):
    name = "python-model"

    def __init__(self, model: str, root: str | None = None, parameters: Mapping[str, Any] | None = None,
                 inputs: Mapping[str, str] | None = None, outputs: Mapping[str, str] | None = None,
                 max_step: float = 1e-4) -> None:
        self.model = model
        self.root = Path(root) if root else None
        self.parameter_spec = dict(parameters or {})
        self.input_map = dict(inputs or {})      # plant input name -> project signal
        self.output_map = dict(outputs or {})    # plant output name -> project signal
        if not max_step > 0:
            raise ValueError("max_step must be positive")
        self.max_step = float(max_step)
        self.plant: Any = None
        self.state: list[float] = []
        self.time = 0.0
        plant_class = load_plant_class(model, self.root)
        unknown_in = set(self.input_map) - set(getattr(plant_class, "inputs", ()))
        unknown_out = set(self.output_map) - set(getattr(plant_class, "outputs", ()))
        if unknown_in or unknown_out:
            raise ValueError(f"{model}: unknown plant inputs {sorted(unknown_in)} / outputs {sorted(unknown_out)}")
        self.plant_class = plant_class

    def _resolve_parameters(self, values: Mapping[str, float]) -> dict[str, Any]:
        resolved = {}
        for key, value in self.parameter_spec.items():
            if isinstance(value, str) and value.startswith("@"):
                name = value[1:]
                if name not in values:
                    raise ValueError(f"plant parameter {key} refers to unknown project parameter {name}")
                value = float(values[name])
            resolved[key] = value
        return resolved

    def _plant_inputs(self, values: Mapping[str, float]) -> dict[str, float]:
        return {name: float(values.get(signal, 0.0)) for name, signal in self.input_map.items()}

    def start(self, initial_signals: Mapping[str, float]) -> None:
        self.plant = self.plant_class(**self._resolve_parameters(initial_signals))
        self.state = [float(x) for x in self.plant.initial_state()]
        if len(self.state) != len(self.plant.states):
            raise ValueError(f"{self.model}: initial_state has {len(self.state)} values for {len(self.plant.states)} states")
        self.time = 0.0

    def step(self, time_seconds: float, step_seconds: float, inputs: Mapping[str, float]) -> StepResult:
        if self.plant is None:
            raise RuntimeError("python model adapter is not started")
        u = self._plant_inputs(inputs)
        span = float(time_seconds) - self.time
        substeps = max(1, math.ceil(span / self.max_step - 1e-9)) if span > 0 else 0
        h = span / substeps if substeps else 0.0
        x, t, f = self.state, self.time, self.plant.derivatives
        for _ in range(substeps):
            k1 = f(t, x, u)
            k2 = f(t + h / 2, [a + h / 2 * b for a, b in zip(x, k1)], u)
            k3 = f(t + h / 2, [a + h / 2 * b for a, b in zip(x, k2)], u)
            k4 = f(t + h, [a + h * b for a, b in zip(x, k3)], u)
            x = [a + h / 6 * (b1 + 2 * b2 + 2 * b3 + b4) for a, b1, b2, b3, b4 in zip(x, k1, k2, k3, k4)]
            t += h
        if any(not math.isfinite(value) for value in x):
            raise FloatingPointError(f"{self.model}: state diverged at t={t:.6g}; reduce max_step")
        self.state, self.time = x, float(time_seconds)
        plant_outputs = self.plant.output(self.time, self.state, u)
        return StepResult({signal: float(plant_outputs[name]) for name, signal in self.output_map.items()},
                          {"substeps": substeps})

    def checkpoint(self) -> object:
        return {"time": self.time, "state": list(self.state)}

    def restore(self, checkpoint: object) -> None:
        data = dict(checkpoint or {})
        self.time = float(data.get("time", 0.0))
        self.state = [float(x) for x in data.get("state", self.state)]

    def capabilities(self) -> dict[str, bool]:
        return {**super().capabilities(), "checkpoint": True}

    def stop(self) -> None:
        self.plant = None
