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
    instance: str = ""


@dataclass(frozen=True)
class ScheduleEntry:
    """One simulator instance in the schedule (name, domain, optional own step)."""
    name: str
    domain: Domain
    step_seconds: float | None = None


def default_entries(order=DEFAULT_ORDER) -> list[ScheduleEntry]:
    return [ScheduleEntry(domain.value, domain) for domain in order]


def order_entries(entries: Iterable[ScheduleEntry], order=DEFAULT_ORDER) -> list[ScheduleEntry]:
    """Stable order: by domain (firmware, electrical, mechanical, thermal,
    environment), then by declaration."""
    rank = {domain: index for index, domain in enumerate(order)}
    entries = list(entries)
    return [entry for _, entry in sorted(enumerate(entries), key=lambda item: (rank.get(item[1].domain, len(rank)), item[0]))]


class SchedulerStrategy:
    """Produces deterministic domain activations for one macro step."""

    def activations(self, macro_start: float, macro_end: float) -> Iterable[ScheduledActivation]:
        raise NotImplementedError


class DeterministicFixedStepScheduler(SchedulerStrategy):
    def __init__(self, config: SchedulerConfig, order=DEFAULT_ORDER, entries: Iterable[ScheduleEntry] | None = None) -> None:
        self.config = config
        self.order = tuple(order)
        self.entries = order_entries(entries if entries is not None else default_entries(order), order)

    def activations(self, macro_start: float, macro_end: float) -> Iterable[ScheduledActivation]:
        step = macro_end - macro_start
        for entry in self.entries:
            yield ScheduledActivation(entry.domain, macro_end, step, entry.name)


class MultiRateFixedStepScheduler(SchedulerStrategy):
    """Deterministic integer-ratio multi-rate schedule.

    Activations are sorted by target time and then by the stable domain order.
    Domain steps are validated by the project model to divide the macro step.
    """

    def __init__(self, config: SchedulerConfig, order=DEFAULT_ORDER, entries: Iterable[ScheduleEntry] | None = None) -> None:
        self.config = config
        self.order = tuple(order)
        self.entries = order_entries(entries if entries is not None else default_entries(order), order)
        self._priority = {entry.name: index for index, entry in enumerate(self.entries)}

    def activations(self, macro_start: float, macro_end: float) -> Iterable[ScheduledActivation]:
        macro = macro_end - macro_start
        result: list[ScheduledActivation] = []
        for entry in self.entries:
            step = entry.step_seconds or self.config.step_for(entry.domain)
            count = max(0, int(math.floor((macro + 1e-15) / step)))
            for index in range(1, count + 1):
                activation_time = macro_start + index * step
                if activation_time <= macro_end + 1e-15:
                    result.append(ScheduledActivation(entry.domain, activation_time, step, entry.name))
        result.sort(key=lambda item: (round(item.time_seconds, 15), self._priority[item.instance]))
        return result


def build_scheduler(config: SchedulerConfig, entries: Iterable[ScheduleEntry] | None = None) -> SchedulerStrategy:
    if config.algorithm in {"deterministic-fixed-step", "real-time-fixed-step"}:
        base: SchedulerStrategy = DeterministicFixedStepScheduler(config, entries=entries)
    elif config.algorithm in {"multirate-fixed-step", "real-time-multirate"}:
        base = MultiRateFixedStepScheduler(config, entries=entries)
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
