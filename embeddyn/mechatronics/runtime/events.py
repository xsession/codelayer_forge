from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any


@dataclass(order=True, frozen=True)
class RuntimeEvent:
    time_seconds: float
    sequence: int
    topic: str = field(compare=False)
    payload: Any = field(compare=False)
    source: str | None = field(default=None, compare=False)


class EventQueue:
    def __init__(self) -> None:
        self._heap: list[RuntimeEvent] = []
        self._sequence = 0

    def publish(self, time_seconds: float, topic: str, payload: Any, source: str | None = None) -> RuntimeEvent:
        event = RuntimeEvent(float(time_seconds), self._sequence, topic, payload, source)
        self._sequence += 1
        heapq.heappush(self._heap, event)
        return event

    def drain_until(self, time_seconds: float) -> list[RuntimeEvent]:
        result: list[RuntimeEvent] = []
        while self._heap and self._heap[0].time_seconds <= time_seconds + 1e-15:
            result.append(heapq.heappop(self._heap))
        return result

    def snapshot(self) -> list[dict[str, Any]]:
        return [
            {"time_seconds": e.time_seconds, "sequence": e.sequence, "topic": e.topic,
             "payload": e.payload, "source": e.source}
            for e in sorted(self._heap)
        ]

    def restore(self, items: list[dict[str, Any]]) -> None:
        self._heap = [RuntimeEvent(**item) for item in items]
        heapq.heapify(self._heap)
        self._sequence = max((event.sequence for event in self._heap), default=-1) + 1
