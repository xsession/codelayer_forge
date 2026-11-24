from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Mapping

from .base import SimulatorAdapter, StepResult


class WebotsAdapter(SimulatorAdapter):
    """Webots adapter using a small line-delimited JSON bridge controller.

    The Webots world should contain a Supervisor robot whose controller opens a
    TCP endpoint and exchanges messages of the form:
      {"command":"step","dt":0.001,"inputs":{...}}
      {"outputs":{...}}
    This keeps Embeddyn independent from a specific robot model and lets PROTO authors
    expose arbitrary mechanical ports.
    """

    name = "webots"

    def __init__(self, world: Path, executable: str | None = None, host: str = "127.0.0.1", port: int = 8765,
                 headless: bool = True, launch: bool = True, timeout: float = 15.0) -> None:
        self.world = world
        self.executable = executable or shutil.which("webots") or "webots"
        self.host, self.port = host, port
        self.headless, self.launch, self.timeout = headless, launch, timeout
        self.process: subprocess.Popen[str] | None = None
        self.sock: socket.socket | None = None
        self.stream = None

    def start(self, initial_signals: Mapping[str, float]) -> None:
        if self.launch:
            command = [self.executable]
            if self.headless:
                command.extend(["--batch", "--no-rendering"])
            command.extend(["--mode=fast", str(self.world)])
            env = os.environ.copy()
            env["EMBEDDYN_COSIM_HOST"] = self.host
            env.setdefault("VSD_COSIM_HOST", self.host)
            env["EMBEDDYN_COSIM_PORT"] = str(self.port)
            env.setdefault("VSD_COSIM_PORT", str(self.port))
            self.process = subprocess.Popen(command, env=env, text=True)
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.stream = self.sock.makefile("rwb")
        self._exchange({"command": "initialize", "signals": dict(initial_signals)})

    def step(self, time_seconds: float, step_seconds: float, inputs: Mapping[str, float]) -> StepResult:
        response = self._exchange({"command": "step", "time": time_seconds, "dt": step_seconds, "inputs": dict(inputs)})
        return StepResult({k: float(v) for k, v in response.get("outputs", {}).items()}, response.get("diagnostics"))

    def capabilities(self) -> dict[str, bool]:
        return {"deterministic_step": True, "variable_step": True, "checkpoint": False, "real_time": True, "events": True, "mechanical_contacts": True}

    def stop(self) -> None:
        try:
            if self.stream:
                self._exchange({"command": "stop"})
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        if self.stream:
            self.stream.close()
        if self.sock:
            self.sock.close()
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def health(self) -> dict[str, object]:
        return {
            "name": self.name,
            "executable": shutil.which(self.executable) or self.executable,
            "world": str(self.world),
            "world_exists": self.world.exists(),
            "connected": self.sock is not None,
        }

    def _exchange(self, payload: dict[str, object]) -> dict[str, object]:
        if self.stream is None:
            raise RuntimeError("Webots bridge is not connected")
        self.stream.write((json.dumps(payload) + "\n").encode("utf-8"))
        self.stream.flush()
        line = self.stream.readline()
        if not line:
            raise RuntimeError("Webots bridge closed the connection")
        response = json.loads(line)
        if response.get("error"):
            raise RuntimeError(f"Webots bridge error: {response['error']}")
        return response
