"""Mappings keyed by simulator instance name that also accept Domain keys.

Legacy code addresses adapters by `Domain`; instance-based projects use names
(`mcu0`, `left_wheel`). A legacy instance is named after its domain, so
`adapters[Domain.FIRMWARE]` and `adapters["firmware"]` are the same entry.
"""
from __future__ import annotations

from typing import Any

from ..model import Domain


def instance_key(key: Any) -> str:
    return key.value if isinstance(key, Domain) else str(key)


class InstanceMap(dict):
    def __init__(self, data: Any = (), **kwargs: Any) -> None:
        super().__init__()
        self.update(data, **kwargs)

    def update(self, data: Any = (), **kwargs: Any) -> None:  # type: ignore[override]
        items = data.items() if hasattr(data, "items") else data
        for key, value in [*items, *kwargs.items()]:
            self[key] = value

    def __setitem__(self, key: Any, value: Any) -> None:
        super().__setitem__(instance_key(key), value)

    def __getitem__(self, key: Any) -> Any:
        return super().__getitem__(instance_key(key))

    def __contains__(self, key: Any) -> bool:
        return super().__contains__(instance_key(key))

    def __delitem__(self, key: Any) -> None:
        super().__delitem__(instance_key(key))

    def get(self, key: Any, default: Any = None) -> Any:
        return super().get(instance_key(key), default)

    def pop(self, key: Any, *default: Any) -> Any:
        return super().pop(instance_key(key), *default)

    def setdefault(self, key: Any, default: Any = None) -> Any:
        return super().setdefault(instance_key(key), default)


class InstanceCounter(InstanceMap):
    def __missing__(self, key: str) -> int:
        return 0
