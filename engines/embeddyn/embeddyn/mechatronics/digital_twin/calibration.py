from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AffineCalibration:
    signal: str
    scale: float
    offset: float
    samples: int
    before_rmse: float
    after_rmse: float
    r_squared: float | None

    def apply(self, value: float) -> float:
        return self.scale * value + self.offset

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "affine",
            "signal": self.signal,
            "scale": self.scale,
            "offset": self.offset,
            "samples": self.samples,
            "before_rmse": self.before_rmse,
            "after_rmse": self.after_rmse,
            "r_squared": self.r_squared,
        }


def fit_affine(aligned: list[dict[str, float]], signal: str) -> AffineCalibration:
    x = [row[f"simulated.{signal}"] for row in aligned]
    y = [row[f"measured.{signal}"] for row in aligned]
    if len(x) < 2:
        raise ValueError(f"at least two aligned samples are required for {signal}")
    x_mean = sum(x) / len(x)
    y_mean = sum(y) / len(y)
    denominator = sum((value - x_mean) ** 2 for value in x)
    scale = sum((a - x_mean) * (b - y_mean) for a, b in zip(x, y)) / denominator if denominator else 1.0
    offset = y_mean - scale * x_mean
    before = math.sqrt(sum((a - b) ** 2 for a, b in zip(x, y)) / len(x))
    corrected = [scale * value + offset for value in x]
    after = math.sqrt(sum((a - b) ** 2 for a, b in zip(corrected, y)) / len(x))
    total = sum((value - y_mean) ** 2 for value in y)
    residual = sum((a - b) ** 2 for a, b in zip(corrected, y))
    r_squared = 1.0 - residual / total if total else None
    return AffineCalibration(signal, scale, offset, len(x), before, after, r_squared)


def fit_all(aligned: list[dict[str, float]]) -> dict[str, AffineCalibration]:
    if not aligned:
        raise ValueError("aligned dataset is empty")
    signals = sorted(key.split(".", 1)[1] for key in aligned[0] if key.startswith("simulated."))
    return {signal: fit_affine(aligned, signal) for signal in signals}
