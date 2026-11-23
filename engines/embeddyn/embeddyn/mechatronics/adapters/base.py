from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass
class StepResult:
    outputs: dict[str, float]
    diagnostics: dict[str, object] | None = None


class SimulatorAdapter(ABC):
    """Common lifecycle for all simulation domains."""

    name = "simulator"

    def prepare(self, context: Mapping[str, Any]) -> None:
        """Prepare resources without advancing simulation time."""

    @abstractmethod
    def start(self, initial_signals: Mapping[str, float]) -> None: ...

    @abstractmethod
    def step(self, time_seconds: float, step_seconds: float, inputs: Mapping[str, float]) -> StepResult: ...

    @abstractmethod
    def stop(self) -> None: ...

    def checkpoint(self) -> object:
        """Return JSON-serializable adapter state when supported."""
        return None

    def restore(self, checkpoint: object) -> None:
        if checkpoint is not None:
            raise NotImplementedError(f"{self.name} does not support restore")

    def health(self) -> dict[str, object]:
        return {"name": self.name, "healthy": True, "capabilities": self.capabilities()}

    def capabilities(self) -> dict[str, bool]:
        return {
            "deterministic_step": True,
            "variable_step": True,
            "checkpoint": False,
            "real_time": False,
            "events": False,
        }
