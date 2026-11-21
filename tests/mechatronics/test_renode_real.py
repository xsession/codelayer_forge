"""Closed-loop test against a real Renode build (custom-cores branch).

Opt-in: set RENODE_BIN to the `renode` launcher and build the example firmware
(`make -C examples/mechatronics/firmware/motor-speed-control`). Skipped otherwise.
"""
import csv
import os
from dataclasses import replace
import socket
from pathlib import Path

import pytest

from embeddyn.mechatronics.adapters.renode import RenodeAdapter
from embeddyn.mechatronics.factory import build_adapters
from embeddyn.mechatronics.model import Domain, MechatronicProject
from embeddyn.mechatronics.orchestrator import CoSimulationOrchestrator

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples/mechatronics/dc-motor-renode.yaml"
FIRMWARE = ROOT / "examples/mechatronics/firmware/motor-speed-control.elf"
RENODE = os.environ.get("RENODE_BIN")
GOLDEN = Path(__file__).with_name("data") / "renode_dc_motor_golden.csv"
GOLDEN_SIGNALS = ("firmware.pwm_duty", "electrical.motor_current", "mechanical.velocity")
GOLDEN_EVERY = 0.01  # seconds between stored samples
# Edge timestamps of the sleeping (WFI) core jitter by a few µs, so the
# per-step duty can differ by ~1 %; the integrated quantities stay close.
GOLDEN_TOLERANCE = {"firmware.pwm_duty": 0.02, "electrical.motor_current": 0.1, "mechanical.velocity": 0.05}

pytestmark = pytest.mark.skipif(not RENODE or not FIRMWARE.exists(),
                                reason="set RENODE_BIN and build the example firmware")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _project(tmp_path, duration: float) -> MechatronicProject:
    project = MechatronicProject.load(EXAMPLE)
    project.duration_seconds = duration
    options = project.simulators[Domain.FIRMWARE].options
    options.update(port=_free_port(), executable=RENODE, log=str(tmp_path / "renode.log"))
    return project


def test_real_renode_closed_loop(tmp_path):
    project = _project(tmp_path, 0.3)
    adapters = build_adapters(project)
    firmware = adapters[Domain.FIRMWARE]
    assert isinstance(firmware, RenodeAdapter)
    rows = CoSimulationOrchestrator(project, adapters).run(tmp_path / "run.csv")

    duty = [row["firmware.pwm_duty"] for row in rows[1:]]
    velocity = [row["mechanical.velocity"] for row in rows]
    # Firmware starts at full duty (large error) and backs off as speed rises.
    assert max(duty[:20]) > 0.95
    # While saturated (0.001..0.1 s) the output must never drop out. Catches the
    # STM32_Timer CCR = ARR race (patch 0003), which the 10 ms golden samples miss.
    # The first two steps precede the firmware's first control update (CCR = 1).
    assert min(duty[2:200]) > 0.5
    assert all(0.0 <= d <= 1.0 for d in duty)
    assert velocity[-1] > 2.0
    assert duty[-1] < max(duty)
    _compare_with_golden(rows)


def _golden_rows(rows):
    picked, next_time = [], 0.0
    for row in rows:
        if row["time"] + 1e-9 >= next_time:
            picked.append({"time": round(row["time"], 6),
                           **{name: row[name] for name in GOLDEN_SIGNALS}})
            next_time += GOLDEN_EVERY
    return picked


def _compare_with_golden(rows):
    """Regression check against a stored trace.

    Regenerate after an intended behaviour change with
    EMBEDDYN_UPDATE_GOLDEN=1 pytest tests/mechatronics/test_renode_real.py
    """
    actual = _golden_rows(rows)
    if os.environ.get("EMBEDDYN_UPDATE_GOLDEN"):
        GOLDEN.parent.mkdir(exist_ok=True)
        with GOLDEN.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(actual[0]))
            writer.writeheader()
            writer.writerows(actual)
        pytest.skip(f"golden trace written to {GOLDEN}")
    with GOLDEN.open(newline="", encoding="utf-8") as handle:
        expected = list(csv.DictReader(handle))
    assert len(actual) == len(expected)
    for got, want in zip(actual, expected):
        assert abs(got["time"] - float(want["time"])) < 1e-6
        for name, tolerance in GOLDEN_TOLERANCE.items():
            assert abs(got[name] - float(want[name])) <= tolerance, (
                f"{name} at t={got['time']}: {got[name]:.4f} vs golden {float(want[name]):.4f}")


def test_real_renode_calibration_write_changes_behaviour(tmp_path):
    """Tuning without rebuilding: write the set-point in RAM over the system bus."""
    project = _project(tmp_path, 0.1)
    options = project.simulators[Domain.FIRMWARE].options
    options["inline_bindings"] = [{
        "signal": "firmware.target_velocity", "direction": "input", "property": "sysbus",
        "address": 0x20000004, "width": 4, "float32": True, "scale": 100.0,
    }]
    project.signals["firmware.target_velocity"] = replace(project.signals["firmware.target_velocity"], initial=0.0)
    rows = CoSimulationOrchestrator(project, build_adapters(project)).run()
    # Set-point 0 -> the controller never drives the motor. CCR is clamped to 1
    # (0.1 %); with the WFI firmware the measured per-step duty shows a few µs
    # of edge jitter (up to ~1.2 %), independent of the quantum.
    assert max(row["firmware.pwm_duty"] for row in rows[5:]) < 0.02
    assert abs(rows[-1]["mechanical.velocity"]) < 0.5
