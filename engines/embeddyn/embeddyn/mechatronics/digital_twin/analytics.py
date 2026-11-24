from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..storage.telemetry import read_telemetry_rows


@dataclass(frozen=True)
class SignalMetrics:
    signal: str
    samples: int
    mae: float
    rmse: float
    max_abs_error: float
    bias: float
    measured_min: float
    measured_max: float
    nrmse: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal": self.signal,
            "samples": self.samples,
            "mae": self.mae,
            "rmse": self.rmse,
            "max_abs_error": self.max_abs_error,
            "bias": self.bias,
            "measured_min": self.measured_min,
            "measured_max": self.measured_max,
            "nrmse": self.nrmse,
        }


def read_measurements(path: Path) -> list[dict[str, float]]:
    path = path.resolve()
    if path.suffix.lower() in {".jsonl", ".parquet", ".csv"}:
        return read_telemetry_rows(path)
    if path.suffix.lower() == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows = raw.get("rows", raw) if isinstance(raw, dict) else raw
        if not isinstance(rows, list):
            raise ValueError("measurement JSON must contain a list or a 'rows' list")
        return [{str(k): float(v) for k, v in row.items()} for row in rows]
    raise ValueError(f"unsupported measurement format: {path}")


def write_rows_csv(rows: Iterable[Mapping[str, float]], path: Path) -> Path:
    records = [dict(row) for row in rows]
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        path.write_text("", encoding="utf-8")
        return path
    fields = list(records[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    return path


def _time_key(rows: list[dict[str, float]]) -> str:
    if not rows:
        raise ValueError("telemetry dataset is empty")
    for candidate in ("time_seconds", "time", "t"):
        if candidate in rows[0]:
            return candidate
    raise ValueError("telemetry dataset has no time column (time_seconds, time, or t)")


def _interpolate(rows: list[dict[str, float]], time_key: str, signal: str, target: float) -> float | None:
    if not rows:
        return None
    if target < rows[0][time_key] or target > rows[-1][time_key]:
        return None
    lo, hi = 0, len(rows) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        current = rows[mid][time_key]
        if current < target:
            lo = mid + 1
        elif current > target:
            hi = mid - 1
        else:
            return rows[mid].get(signal)
    upper = min(lo, len(rows) - 1)
    lower = max(0, upper - 1)
    a, b = rows[lower], rows[upper]
    if signal not in a or signal not in b:
        return None
    ta, tb = a[time_key], b[time_key]
    if tb == ta:
        return a[signal]
    ratio = (target - ta) / (tb - ta)
    return a[signal] + ratio * (b[signal] - a[signal])


def align_datasets(
    simulated: list[dict[str, float]],
    measured: list[dict[str, float]],
    mapping: Mapping[str, str] | None = None,
) -> list[dict[str, float]]:
    simulation_time = _time_key(simulated)
    measurement_time = _time_key(measured)
    simulated = sorted(simulated, key=lambda row: row[simulation_time])
    measured = sorted(measured, key=lambda row: row[measurement_time])
    mapping = dict(mapping or {})
    if not mapping:
        common = sorted((set(simulated[0]) & set(measured[0])) - {simulation_time, measurement_time})
        mapping = {name: name for name in common}
    if not mapping:
        raise ValueError("datasets contain no common signals and no mapping was provided")
    aligned: list[dict[str, float]] = []
    for row in measured:
        t = row[measurement_time]
        output: dict[str, float] = {"time_seconds": t}
        valid = True
        for measured_name, simulated_name in mapping.items():
            if measured_name not in row:
                valid = False
                break
            simulated_value = _interpolate(simulated, simulation_time, simulated_name, t)
            if simulated_value is None:
                valid = False
                break
            output[f"measured.{measured_name}"] = row[measured_name]
            output[f"simulated.{measured_name}"] = simulated_value
            output[f"error.{measured_name}"] = simulated_value - row[measured_name]
        if valid:
            aligned.append(output)
    return aligned


def calculate_metrics(aligned: list[dict[str, float]]) -> dict[str, SignalMetrics]:
    if not aligned:
        raise ValueError("no overlapping samples after alignment")
    signals = sorted(key.split(".", 1)[1] for key in aligned[0] if key.startswith("error."))
    result: dict[str, SignalMetrics] = {}
    for signal in signals:
        errors = [row[f"error.{signal}"] for row in aligned]
        measured = [row[f"measured.{signal}"] for row in aligned]
        mae = sum(abs(value) for value in errors) / len(errors)
        mse = sum(value * value for value in errors) / len(errors)
        rmse = math.sqrt(mse)
        span = max(measured) - min(measured)
        result[signal] = SignalMetrics(
            signal=signal,
            samples=len(errors),
            mae=mae,
            rmse=rmse,
            max_abs_error=max(abs(value) for value in errors),
            bias=sum(errors) / len(errors),
            measured_min=min(measured),
            measured_max=max(measured),
            nrmse=(rmse / span) if span > 0 else None,
        )
    return result


def compare_files(
    simulated_path: Path,
    measured_path: Path,
    mapping: Mapping[str, str] | None = None,
) -> tuple[list[dict[str, float]], dict[str, Any]]:
    simulated = read_measurements(simulated_path)
    measured = read_measurements(measured_path)
    aligned = align_datasets(simulated, measured, mapping)
    metrics = calculate_metrics(aligned)
    return aligned, {
        "simulation": str(simulated_path.resolve()),
        "measurement": str(measured_path.resolve()),
        "aligned_samples": len(aligned),
        "signals": {name: metric.to_dict() for name, metric in metrics.items()},
    }
