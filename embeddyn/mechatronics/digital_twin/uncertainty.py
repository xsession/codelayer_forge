from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Any

import yaml


def _percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot calculate percentile of empty values")
    position = (len(ordered) - 1) * p
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


def _sample(spec: dict[str, Any], rng: random.Random) -> float:
    distribution = str(spec.get("distribution", "normal"))
    if distribution == "normal":
        return rng.gauss(float(spec["mean"]), float(spec["sigma"]))
    if distribution == "uniform":
        return rng.uniform(float(spec["minimum"]), float(spec["maximum"]))
    if distribution == "triangular":
        return rng.triangular(float(spec["minimum"]), float(spec["maximum"]), float(spec.get("mode", spec["minimum"])))
    if distribution == "choice":
        values = [float(value) for value in spec["values"]]
        return rng.choice(values)
    raise ValueError(f"unsupported distribution: {distribution}")


def run_uncertainty(spec_path: Path, samples: int, seed: int) -> dict[str, Any]:
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    parameters = raw.get("parameters") or {}
    if not parameters:
        raise ValueError("uncertainty specification has no parameters")
    rng = random.Random(seed)
    generated: list[dict[str, float]] = []
    for _ in range(samples):
        generated.append({name: _sample(dict(definition), rng) for name, definition in parameters.items()})
    summary: dict[str, Any] = {}
    for name in parameters:
        values = [row[name] for row in generated]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / max(1, len(values) - 1)
        summary[name] = {
            "mean": mean,
            "standard_deviation": math.sqrt(variance),
            "minimum": min(values),
            "maximum": max(values),
            "p05": _percentile(values, 0.05),
            "p50": _percentile(values, 0.50),
            "p95": _percentile(values, 0.95),
        }
    return {
        "schema_version": 1,
        "source": str(spec_path.resolve()),
        "samples": samples,
        "seed": seed,
        "parameters": summary,
        "sample_set": generated,
    }
