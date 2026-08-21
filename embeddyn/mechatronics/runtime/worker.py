from __future__ import annotations

import importlib
import multiprocessing as mp
import traceback
from dataclasses import dataclass, field
from typing import Any, Mapping

from ..adapters.base import SimulatorAdapter, StepResult


@dataclass(frozen=True)
class AdapterWorkerSpec:
    module: str
    class_name: str
    kwargs: dict[str, Any] = field(default_factory=dict)


def _worker_main(connection, spec: AdapterWorkerSpec) -> None:
    try:
        module = importlib.import_module(spec.module)
        adapter = getattr(module, spec.class_name)(**spec.kwargs)
        connection.send({"ok": True, "name": adapter.name})
        while True:
            request = connection.recv()
            command = request["command"]
            if command == "close":
                try:
                    adapter.stop()
                finally:
                    connection.send({"ok": True})
                    break
            try:
                if command == "prepare":
                    result = adapter.prepare(request.get("context", {}))
                elif command == "start":
                    result = adapter.start(request["signals"])
                elif command == "step":
                    step = adapter.step(request["time_seconds"], request["step_seconds"], request["inputs"])
                    result = {"outputs": step.outputs, "diagnostics": step.diagnostics}
                elif command == "health":
                    result = adapter.health()
                elif command == "capabilities":
                    result = adapter.capabilities()
                elif command == "checkpoint":
                    result = adapter.checkpoint()
                elif command == "restore":
                    result = adapter.restore(request.get("state"))
                elif command == "stop":
                    result = adapter.stop()
                else:
                    raise ValueError(f"unknown worker command: {command}")
                connection.send({"ok": True, "result": result})
            except Exception as exc:
                connection.send({"ok": False, "error": str(exc), "traceback": traceback.format_exc()})
    except Exception as exc:
        connection.send({"ok": False, "error": str(exc), "traceback": traceback.format_exc()})
    finally:
        connection.close()


class ProcessAdapterProxy(SimulatorAdapter):
    """Runs an adapter in a supervised child process over a small RPC protocol."""

    def __init__(self, spec: AdapterWorkerSpec, timeout_seconds: float = 10.0) -> None:
        self.spec = spec
        self.timeout_seconds = timeout_seconds
        self._process: mp.Process | None = None
        self._connection = None
        self.name = f"worker:{spec.class_name}"

    def _ensure_process(self) -> None:
        if self._process is not None and self._process.is_alive():
            return
        context = mp.get_context("spawn")
        parent, child = context.Pipe()
        process = context.Process(target=_worker_main, args=(child, self.spec), daemon=True)
        process.start()
        child.close()
        self._process = process
        self._connection = parent
        response = self._receive()
        self.name = str(response.get("name", self.name))

    def _receive(self) -> dict[str, Any]:
        if self._connection is None or not self._connection.poll(self.timeout_seconds):
            self._terminate()
            raise TimeoutError(f"adapter worker timed out after {self.timeout_seconds}s")
        response = self._connection.recv()
        if not response.get("ok"):
            raise RuntimeError(f"adapter worker failed: {response.get('error')}\n{response.get('traceback', '')}")
        return response

    def _request(self, command: str, **payload: Any) -> Any:
        self._ensure_process()
        self._connection.send({"command": command, **payload})
        return self._receive().get("result")

    def prepare(self, context: Mapping[str, Any]) -> None:
        self._request("prepare", context=dict(context))

    def start(self, initial_signals: Mapping[str, float]) -> None:
        self._request("start", signals=dict(initial_signals))

    def step(self, time_seconds: float, step_seconds: float, inputs: Mapping[str, float]) -> StepResult:
        result = self._request("step", time_seconds=time_seconds, step_seconds=step_seconds, inputs=dict(inputs))
        return StepResult(dict(result["outputs"]), result.get("diagnostics"))

    def stop(self) -> None:
        if self._process is None:
            return
        try:
            self._request("stop")
            self._connection.send({"command": "close"})
            self._receive()
        finally:
            self._terminate()

    def checkpoint(self) -> object:
        return self._request("checkpoint")

    def restore(self, checkpoint: object) -> None:
        self._request("restore", state=checkpoint)

    def health(self) -> dict[str, object]:
        if self._process is None or not self._process.is_alive():
            return {"name": self.name, "healthy": False, "reason": "worker-not-running"}
        return dict(self._request("health"))

    def capabilities(self) -> dict[str, bool]:
        return dict(self._request("capabilities"))

    def _terminate(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        if self._process is not None:
            if self._process.is_alive():
                self._process.terminate()
            self._process.join(timeout=2.0)
            self._process = None
