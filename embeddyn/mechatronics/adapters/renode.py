from __future__ import annotations

import json
import socket
from typing import Mapping

from .base import SimulatorAdapter, StepResult


class RenodeSocketAdapter(SimulatorAdapter):
    """Generic JSON socket bridge for Renode external peripherals/cosimulation."""

    name = "renode"

    def __init__(self, host: str = "127.0.0.1", port: int = 8766, timeout: float = 10.0) -> None:
        self.host, self.port, self.timeout = host, port, timeout
        self.sock: socket.socket | None = None
        self.stream = None

    def start(self, initial_signals: Mapping[str, float]) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.stream = self.sock.makefile("rwb")
        self._exchange({"command": "initialize", "signals": dict(initial_signals)})

    def step(self, time_seconds: float, step_seconds: float, inputs: Mapping[str, float]) -> StepResult:
        response = self._exchange({"command": "step", "time": time_seconds, "dt": step_seconds, "inputs": dict(inputs)})
        return StepResult({k: float(v) for k, v in response.get("outputs", {}).items()})

    def capabilities(self) -> dict[str, bool]:
        return {"deterministic_step": True, "variable_step": True, "checkpoint": True, "real_time": True, "events": True, "buses": True}

    def stop(self) -> None:
        if self.stream:
            try:
                self._exchange({"command": "stop"})
            except OSError:
                pass
            self.stream.close()
        if self.sock:
            self.sock.close()

    def _exchange(self, payload: dict[str, object]) -> dict[str, object]:
        if self.stream is None:
            raise RuntimeError("Renode bridge is not connected")
        self.stream.write((json.dumps(payload) + "\n").encode())
        self.stream.flush()
        line = self.stream.readline()
        if not line:
            raise RuntimeError("Renode bridge closed the connection")
        return json.loads(line)
