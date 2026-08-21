from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from threading import Lock
from time import monotonic
from typing import Any, Callable


class SafetyState(str, Enum):
    DISARMED = "disarmed"
    ARMED = "armed"
    TRIPPED = "tripped"
    SHUTDOWN = "shutdown"


@dataclass(frozen=True)
class OutputLimit:
    minimum: float
    maximum: float
    safe_value: float
    slew_rate_per_second: float | None = None

    def validate(self) -> None:
        if self.minimum > self.maximum:
            raise ValueError("output minimum exceeds maximum")
        if not self.minimum <= self.safe_value <= self.maximum:
            raise ValueError("safe output is outside allowed range")
        if self.slew_rate_per_second is not None and self.slew_rate_per_second <= 0:
            raise ValueError("slew rate must be positive")


@dataclass(frozen=True)
class HilSafetyPolicy:
    watchdog_timeout_seconds: float = 0.5
    require_arm_token: bool = True
    emergency_stop_input: str = "emergency_stop"
    outputs: dict[str, OutputLimit] = field(default_factory=dict)
    trip_on_deadline_miss: bool = True
    maximum_deadline_misses: int = 1

    def validate(self) -> None:
        if self.watchdog_timeout_seconds <= 0:
            raise ValueError("watchdog timeout must be positive")
        if self.maximum_deadline_misses < 1:
            raise ValueError("maximum deadline misses must be positive")
        for limit in self.outputs.values():
            limit.validate()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "HilSafetyPolicy":
        outputs = {
            name: OutputLimit(
                minimum=float(spec["minimum"]),
                maximum=float(spec["maximum"]),
                safe_value=float(spec["safe_value"]),
                slew_rate_per_second=(
                    float(spec["slew_rate_per_second"])
                    if spec.get("slew_rate_per_second") is not None else None
                ),
            )
            for name, spec in dict(raw.get("outputs") or {}).items()
        }
        policy = cls(
            watchdog_timeout_seconds=float(raw.get("watchdog_timeout_seconds", 0.5)),
            require_arm_token=bool(raw.get("require_arm_token", True)),
            emergency_stop_input=str(raw.get("emergency_stop_input", "emergency_stop")),
            outputs=outputs,
            trip_on_deadline_miss=bool(raw.get("trip_on_deadline_miss", True)),
            maximum_deadline_misses=int(raw.get("maximum_deadline_misses", 1)),
        )
        policy.validate()
        return policy


@dataclass
class SafetyEvent:
    timestamp: float
    state: SafetyState
    reason: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["state"] = self.state.value
        return result


class HilSafetyController:
    """Fail-safe output gate for hardware-in-the-loop execution.

    The controller starts disarmed. Any watchdog timeout, emergency-stop input,
    excessive deadline misses, or explicit trip immediately applies safe outputs.
    """

    def __init__(self, policy: HilSafetyPolicy, output_writer: Callable[[str, float], None] | None = None) -> None:
        policy.validate()
        self.policy = policy
        self.output_writer = output_writer or (lambda _name, _value: None)
        self.state = SafetyState.DISARMED
        self.last_heartbeat = monotonic()
        self.last_update = self.last_heartbeat
        self.deadline_misses = 0
        self.outputs = {name: limit.safe_value for name, limit in policy.outputs.items()}
        self.events: list[SafetyEvent] = []
        self._lock = Lock()
        self.apply_safe_state("initialization")

    def arm(self, token: str | None = None, expected_token: str | None = None) -> None:
        with self._lock:
            if self.state == SafetyState.SHUTDOWN:
                raise RuntimeError("cannot arm a shutdown safety controller")
            if self.policy.require_arm_token and (not token or token != expected_token):
                raise PermissionError("invalid HIL arm token")
            self.state = SafetyState.ARMED
            self.last_heartbeat = monotonic()
            self._record("armed")

    def disarm(self, reason: str = "operator request") -> None:
        with self._lock:
            self.state = SafetyState.DISARMED
            self._apply_safe_state_locked(reason)

    def trip(self, reason: str, **details: Any) -> None:
        with self._lock:
            if self.state == SafetyState.SHUTDOWN:
                return
            self.state = SafetyState.TRIPPED
            self._apply_safe_state_locked(reason, details)

    def shutdown(self, reason: str = "shutdown") -> None:
        with self._lock:
            self.state = SafetyState.SHUTDOWN
            self._apply_safe_state_locked(reason)

    def heartbeat(self) -> None:
        with self._lock:
            if self.state == SafetyState.ARMED:
                self.last_heartbeat = monotonic()

    def check_watchdog(self, now: float | None = None) -> bool:
        now = monotonic() if now is None else now
        with self._lock:
            expired = self.state == SafetyState.ARMED and now - self.last_heartbeat > self.policy.watchdog_timeout_seconds
        if expired:
            self.trip("watchdog timeout", age_seconds=now - self.last_heartbeat)
        return not expired

    def observe_inputs(self, inputs: dict[str, Any]) -> None:
        if bool(inputs.get(self.policy.emergency_stop_input, False)):
            self.trip("emergency stop asserted", input=self.policy.emergency_stop_input)

    def record_deadline_miss(self, lateness_seconds: float) -> None:
        with self._lock:
            self.deadline_misses += 1
            should_trip = (
                self.policy.trip_on_deadline_miss
                and self.deadline_misses >= self.policy.maximum_deadline_misses
            )
        if should_trip:
            self.trip("deadline miss limit exceeded", lateness_seconds=lateness_seconds,
                      deadline_misses=self.deadline_misses)

    def write_outputs(self, requested: dict[str, float], now: float | None = None) -> dict[str, float]:
        now = monotonic() if now is None else now
        with self._lock:
            if self.state != SafetyState.ARMED:
                raise RuntimeError(f"HIL outputs unavailable while {self.state.value}")
            dt = max(0.0, now - self.last_update)
            applied: dict[str, float] = {}
            for name, value in requested.items():
                if name not in self.policy.outputs:
                    raise KeyError(f"unconfigured HIL output: {name}")
                limit = self.policy.outputs[name]
                target = min(limit.maximum, max(limit.minimum, float(value)))
                current = self.outputs[name]
                if limit.slew_rate_per_second is not None:
                    delta = limit.slew_rate_per_second * dt
                    target = min(current + delta, max(current - delta, target))
                self.outputs[name] = target
                self.output_writer(name, target)
                applied[name] = target
            self.last_update = now
            return applied

    def apply_safe_state(self, reason: str) -> None:
        with self._lock:
            self._apply_safe_state_locked(reason)

    def _apply_safe_state_locked(self, reason: str, details: dict[str, Any] | None = None) -> None:
        for name, limit in self.policy.outputs.items():
            self.outputs[name] = limit.safe_value
            self.output_writer(name, limit.safe_value)
        self.last_update = monotonic()
        self._record(reason, details or {})

    def _record(self, reason: str, details: dict[str, Any] | None = None) -> None:
        self.events.append(SafetyEvent(monotonic(), self.state, reason, details or {}))

    def report(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": self.state.value,
                "outputs": dict(self.outputs),
                "deadline_misses": self.deadline_misses,
                "events": [event.to_dict() for event in self.events],
            }
