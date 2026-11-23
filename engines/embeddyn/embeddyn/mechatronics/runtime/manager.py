from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..adapters.base import SimulatorAdapter
from ..model import Domain
from .instances import InstanceMap


@dataclass(frozen=True)
class AdapterHealth:
    domain: Domain | None
    healthy: bool
    details: dict[str, object]
    instance: str = ""


class AdapterManager:
    """Lifecycle of the adapters, keyed by simulator instance name (Domain keys accepted)."""

    def __init__(self, adapters: Mapping[object, SimulatorAdapter], domains: Mapping[str, Domain] | None = None) -> None:
        self.adapters = InstanceMap(adapters)
        self.domains = dict(domains or {})
        self.started: list[str] = []

    def _domain(self, name: str) -> Domain | None:
        if name in self.domains:
            return self.domains[name]
        try:
            return Domain(name)
        except ValueError:
            return None

    def start_all(self, initial_signals: Mapping[str, float]) -> None:
        try:
            for name, adapter in self.adapters.items():
                domain = self._domain(name)
                adapter.prepare({"domain": domain.value if domain else None, "instance": name})
                adapter.start(initial_signals)
                self.started.append(name)
        except Exception:
            self.stop_all()
            raise

    def stop_all(self) -> None:
        for name in reversed(self.started):
            try:
                self.adapters[name].stop()
            except Exception:
                pass
        self.started.clear()

    def health(self) -> list[AdapterHealth]:
        result = []
        for name, adapter in self.adapters.items():
            details = adapter.health()
            result.append(AdapterHealth(self._domain(name), bool(details.get("healthy", False)), details, name))
        return result

    def checkpoint(self) -> dict[str, object]:
        return {name: adapter.checkpoint() for name, adapter in self.adapters.items()}

    def restore(self, state: Mapping[str, object]) -> None:
        for name, adapter in self.adapters.items():
            if name in state:
                adapter.restore(state[name])
