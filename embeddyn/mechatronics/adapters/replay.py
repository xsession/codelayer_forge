"""Replay recorded data as signals (`backend: replay`, any domain).

Drives a model from a bench recording instead of a simulator, e.g. the duty
cycle an open-loop test applied:

```yaml
instances:
  bench_input:
    domain: firmware
    model: bench/step-test.csv          # CSV with a time column
    options:
      backend: replay
      columns: {duty: firmware.pwm_duty}   # CSV column -> project signal
      interpolation: previous              # previous (sample-and-hold) or linear
      time_column: time
```
"""
from __future__ import annotations

import bisect
import csv
from pathlib import Path
from typing import Mapping

from .base import SimulatorAdapter, StepResult


def read_columns(path: Path, time_column: str = "time") -> tuple[list[float], dict[str, list[float]]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or time_column not in reader.fieldnames:
            raise ValueError(f"{path}: no {time_column!r} column")
        rows = list(reader)
    times = [float(row[time_column]) for row in rows]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError(f"{path}: time column must be strictly increasing")
    columns = {name: [float(row[name]) for row in rows] for name in rows[0] if name != time_column} if rows else {}
    return times, columns


def sample(times: list[float], values: list[float], t: float, interpolation: str = "linear") -> float:
    if t <= times[0]:
        return values[0]
    if t >= times[-1]:
        return values[-1]
    index = bisect.bisect_right(times, t) - 1
    if interpolation == "previous":
        return values[index]
    t0, t1 = times[index], times[index + 1]
    return values[index] + (values[index + 1] - values[index]) * (t - t0) / (t1 - t0)


class ReplayAdapter(SimulatorAdapter):
    name = "replay"

    def __init__(self, file: str, columns: Mapping[str, str], interpolation: str = "previous",
                 time_column: str = "time") -> None:
        if interpolation not in ("previous", "linear"):
            raise ValueError("interpolation must be 'previous' or 'linear'")
        self.file = Path(file)
        self.times, data = read_columns(self.file, time_column)
        missing = set(columns) - set(data)
        if missing:
            raise ValueError(f"{self.file}: no columns {', '.join(sorted(missing))}")
        self.columns = dict(columns)
        self.data = data
        self.interpolation = interpolation

    def start(self, initial_signals: Mapping[str, float]) -> None:
        pass

    def step(self, time_seconds: float, step_seconds: float, inputs: Mapping[str, float]) -> StepResult:
        # "previous": the value in force during the step that ends now (sample-and-hold from its start).
        at = time_seconds - step_seconds if self.interpolation == "previous" else time_seconds
        return StepResult({signal: sample(self.times, self.data[column], at + 1e-12, self.interpolation)
                           for column, signal in self.columns.items()})

    def checkpoint(self) -> object:
        return {}

    def restore(self, checkpoint: object) -> None:
        pass

    def capabilities(self) -> dict[str, bool]:
        return {**super().capabilities(), "checkpoint": True}

    def stop(self) -> None:
        pass
