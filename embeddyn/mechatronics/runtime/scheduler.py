from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import math
import time

from ..model import Domain, SchedulerConfig


DEFAULT_ORDER = (
    Domain.FIRMWARE,
    Domain.ELECTRICAL,
    Domain.MECHANICAL,
    Domain.THERMAL,
    Domain.ENVIRONMENT,
)


@dataclass(frozen=True)
class ScheduledActivation:
    domain: Domain
    time_seconds: float
    step_seconds: float


class SchedulerStrategy:
    """Produces deterministic domain activations for one macro step."""

    def activations(self, macro_start: float, macro_end: float) -> Iterable[ScheduledActivation]:
        raise NotImplementedError


class DeterministicFixedStepScheduler(SchedulerStrategy):
    def __init__(self, config: SchedulerConfig, order=DEFAULT_ORDER) -> None:
        self.config = config
        self.order = tuple(order)

    def activations(self, macro_start: float, macro_end: float) -> Iterable[ScheduledActivation]:
        step = macro_end - macro_start
        for domain in self.order:
            yield ScheduledActivation(domain, macro_end, step)


class MultiRateFixedStepScheduler(SchedulerStrategy):
    """Deterministic integer-ratio multi-rate schedule.

    Activations are sorted by target time and then by the stable domain order.
    Domain steps are validated by the project model to divide the macro step.
    """

    def __init__(self, config: SchedulerConfig, order=DEFAULT_ORDER) -> None:
        self.config = config
        self.order = tuple(order)
        self._priority = {domain: index for index, domain in enumerate(self.order)}

    def activations(self, macro_start: float, macro_end: float) -> Iterable[ScheduledActivation]:
        macro = macro_end - macro_start
        result: list[ScheduledActivation] = []
        for domain in self.order:
            step = self.config.step_for(domain)
            count = max(0, int(math.floor((macro + 1e-15) / step)))
            for index in range(1, count + 1):
                activation_time = macro_start + index * step
                if activation_time <= macro_end + 1e-15:
                    result.append(ScheduledActivation(domain, activation_time, step))
        result.sort(key=lambda item: (round(item.time_seconds, 15), self._priority[item.domain]))
        return result


def build_scheduler(config: SchedulerConfig) -> SchedulerStrategy:
    if config.algorithm in {"deterministic-fixed-step", "real-time-fixed-step"}:
        base: SchedulerStrategy = DeterministicFixedStepScheduler(config)
    elif config.algorithm in {"multirate-fixed-step", "real-time-multirate"}:
        base = MultiRateFixedStepScheduler(config)
    else:
        raise ValueError(f"unsupported scheduler algorithm: {config.algorithm}")
    return RealTimeScheduler(base, config) if config.real_time.enabled or config.algorithm.startswith("real-time") else base


class RealTimeScheduler(SchedulerStrategy):
    """Wall-clock pacing wrapper with explicit deadline policy."""
    def __init__(self, inner: SchedulerStrategy, config: SchedulerConfig) -> None:
        self.inner = inner
        self.config = config
        self._wall_start: float | None = None
        self._sim_start: float | None = None
        self.deadline_misses = 0
        self.max_lateness_seconds = 0.0

    def activations(self, macro_start: float, macro_end: float) -> Iterable[ScheduledActivation]:
        if self._wall_start is None:
            self._wall_start = time.monotonic()
            self._sim_start = macro_start
        target = self._wall_start + (macro_end - self._sim_start) / self.config.real_time.speed_factor
        remaining = target - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
        lateness = max(0.0, time.monotonic() - target)
        self.max_lateness_seconds = max(self.max_lateness_seconds, lateness)
        if lateness > self.config.real_time.deadline_tolerance_seconds:
            self.deadline_misses += 1
            if self.config.real_time.missed_deadline_policy == "abort":
                raise TimeoutError(f"real-time deadline missed by {lateness:.6f}s")
        return self.inner.activations(macro_start, macro_end)
