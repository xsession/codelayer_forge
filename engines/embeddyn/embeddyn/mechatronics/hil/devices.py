from __future__ import annotations

from dataclasses import dataclass, field
from queue import Queue, Full, Empty
from typing import Any, Protocol


class HilDevice(Protocol):
    def open(self) -> None: ...
    def close(self) -> None: ...
    def read_inputs(self) -> dict[str, Any]: ...
    def write_output(self, name: str, value: float) -> None: ...


@dataclass
class MockHilDevice:
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, float] = field(default_factory=dict)
    opened: bool = False

    def open(self) -> None:
        self.opened = True

    def close(self) -> None:
        self.opened = False

    def read_inputs(self) -> dict[str, Any]:
        if not self.opened:
            raise RuntimeError("HIL device is closed")
        return dict(self.inputs)

    def write_output(self, name: str, value: float) -> None:
        if not self.opened:
            raise RuntimeError("HIL device is closed")
        self.outputs[name] = float(value)


class BoundedIoQueue:
    """Bounded non-blocking queue used at the simulation/hardware boundary."""

    def __init__(self, maximum_size: int = 1024) -> None:
        if maximum_size < 1:
            raise ValueError("maximum_size must be positive")
        self._queue: Queue[Any] = Queue(maxsize=maximum_size)
        self.dropped = 0

    def put_latest(self, item: Any) -> None:
        try:
            self._queue.put_nowait(item)
        except Full:
            try:
                self._queue.get_nowait()
            except Empty:
                pass
            self.dropped += 1
            self._queue.put_nowait(item)

    def get_nowait(self) -> Any | None:
        try:
            return self._queue.get_nowait()
        except Empty:
            return None

    @property
    def size(self) -> int:
        return self._queue.qsize()
