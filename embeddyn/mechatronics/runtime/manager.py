from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..adapters.base import SimulatorAdapter
from ..model import Domain


@dataclass(frozen=True)
class AdapterHealth:
    domain: Domain
    healthy: bool
    details: dict[str, object]


class AdapterManager:
    def __init__(self, adapters: Mapping[Domain, SimulatorAdapter]) -> None:
        self.adapters = dict(adapters)
        self.started: list[Domain] = []

    def start_all(self, initial_signals: Mapping[str, float]) -> None:
        try:
            for domain, adapter in self.adapters.items():
                adapter.prepare({"domain": domain.value})
                adapter.start(initial_signals)
                self.started.append(domain)
        except Exception:
            self.stop_all()
            raise

    def stop_all(self) -> None:
        for domain in reversed(self.started):
            try:
                self.adapters[domain].stop()
            except Exception:
                pass
        self.started.clear()

    def health(self) -> list[AdapterHealth]:
        result = []
        for domain, adapter in self.adapters.items():
            details = adapter.health()
            result.append(AdapterHealth(domain, bool(details.get("healthy", False)), details))
        return result

    def checkpoint(self) -> dict[str, object]:
        return {domain.value: adapter.checkpoint() for domain, adapter in self.adapters.items()}

    def restore(self, state: Mapping[str, object]) -> None:
        for domain, adapter in self.adapters.items():
            if domain.value in state:
                adapter.restore(state[domain.value])
