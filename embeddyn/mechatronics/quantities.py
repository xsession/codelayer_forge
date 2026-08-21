from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_QUANTITY = re.compile(r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(.*?)\s*$")


@dataclass(frozen=True)
class Quantity:
    value: float
    unit: str = ""

    @classmethod
    def parse(cls, raw: Any, default_unit: str = "") -> "Quantity":
        if isinstance(raw, Quantity):
            return raw
        if isinstance(raw, (int, float)):
            return cls(float(raw), default_unit)
        if isinstance(raw, dict):
            return cls(float(raw.get("value", raw.get("value_si", 0.0))), str(raw.get("unit", default_unit)))
        if isinstance(raw, str):
            match = _QUANTITY.match(raw)
            if not match:
                raise ValueError(f"invalid quantity: {raw!r}")
            return cls(float(match.group(1)), match.group(2) or default_unit)
        raise TypeError(f"unsupported quantity value: {type(raw).__name__}")

    def to_dict(self) -> dict[str, object]:
        return {"value": self.value, "unit": self.unit}
