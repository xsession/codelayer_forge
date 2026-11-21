"""NgspiceSharedAdapter: parsing/maths always; simulation when libngspice is available.

The simulation tests run when libngspice is found (system library or
NGSPICE_LIBRARY) and are skipped otherwise.
"""
import csv
import math
from pathlib import Path

import pytest

from embeddyn.mechatronics.adapters.ngspice_shared import (
    NgspiceError,
    NgspiceSharedAdapter,
    _reduce,
    find_library,
    load_ngspice_bindings,
    prepare_netlist,
)
from embeddyn.mechatronics.factory import build_adapters
from embeddyn.mechatronics.model import Domain, MechatronicProject
from embeddyn.mechatronics.orchestrator import CoSimulationOrchestrator

ROOT = Path(__file__).resolve().parents[2]
HBRIDGE = ROOT / "examples/mechatronics/dc-motor-ngspice.yaml"

try:
    LIBRARY = find_library()
except NgspiceError:
    LIBRARY = None
needs_ngspice = pytest.mark.skipif(LIBRARY is None, reason="libngspice not found (install libngspice0 or set NGSPICE_LIBRARY)")


def test_prepare_netlist_substitutes_and_replaces_analyses():
    text = """* {{not.a.signal}} in a comment is left alone
R1 a b {{electrical.r}}
.tran 1u 1m
.control
run
.endc
.end
"""
    lines = prepare_netlist(text, {"electrical.r": 2.5}, ".tran 1e-6 1 0 1e-6 uic")
    assert "R1 a b 2.5" in lines
    assert lines[-2:] == [".tran 1e-6 1 0 1e-6 uic", ".end"]
    assert not any(line.strip().lower() in {"run", ".control", ".endc", ".tran 1u 1m"} for line in lines)
    with pytest.raises(ValueError, match="unknown"):
        prepare_netlist("R1 a b {{unknown}}\n", {}, ".tran 1 1")


def test_bindings_validation():
    bindings = load_ngspice_bindings(inline=[
        {"signal": "e.duty", "source": "Vd", "min": 0, "max": 1},
        {"signal": "e.r", "alter": "Rmotor"},
        {"signal": "e.i", "vector": "i(Vsense)", "mode": "rms"},
    ])
    assert [b.kind for b in bindings.inputs] == ["source", "alter"]
    assert bindings.inputs[0].value(1.7) == 1.0
    assert bindings.outputs[0].mode == "rms"
    with pytest.raises(ValueError, match="exactly one"):
        load_ngspice_bindings(inline=[{"signal": "x", "direction": "input"}])
    with pytest.raises(ValueError, match="mode"):
        load_ngspice_bindings(inline=[{"signal": "x", "vector": "V(a)", "mode": "median"}])


def test_reduce_modes():
    times, values = [0.0, 1.0, 2.0], [0.0, 2.0, 0.0]
    assert _reduce(times, values, "mean") == pytest.approx(1.0)
    assert _reduce(times, values, "last") == 0.0
    assert _reduce(times, values, "max") == 2.0
    assert _reduce(times, [3.0, 3.0, 3.0], "rms") == pytest.approx(3.0)


def test_factory_builds_shared_adapter():
    project = MechatronicProject.load(HBRIDGE)
    adapter = build_adapters(project)[Domain.ELECTRICAL]
    assert isinstance(adapter, NgspiceSharedAdapter)
    assert adapter.max_step == pytest.approx(1e-6)
    assert {b.target for b in adapter.bindings.inputs} >= {"Vdutyp", "Vdutyn", "Vbus", "Vbemf", "Rmotor"}


RC = """* RC low-pass driven by an external source
Vin in 0 dc 0 external
R1 in out 1k
C1 out 0 1u ic=0
"""


def _rc_adapter(tmp_path, **extra):
    netlist = tmp_path / "rc.cir"
    netlist.write_text(RC, encoding="utf-8")
    return NgspiceSharedAdapter(netlist, inline_bindings=[
        {"signal": "e.vin", "source": "Vin"},
        {"signal": "e.r", "alter": "R1"},
        {"signal": "e.vout", "vector": "V(out)", "mode": "last"},
        {"signal": "e.vout_mean", "vector": "V(out)", "mode": "mean"},
        {"signal": "e.i", "vector": "I(Vin)", "mode": "last", "scale": -1.0},
    ], max_step=1e-5, duration=0.01, **extra)


@needs_ngspice
def test_state_carries_across_steps(tmp_path):
    """A 1 ms RC charged in 0.5 ms steps follows the analytic curve exactly at each step."""
    adapter = _rc_adapter(tmp_path)
    adapter.start({"e.vin": 1.0, "e.r": 1000.0})
    try:
        for k in range(1, 7):
            out = adapter.step(k * 5e-4, 5e-4, {"e.vin": 1.0, "e.r": 1000.0}).outputs
            assert out["e.vout"] == pytest.approx(1 - math.exp(-k * 0.5), abs=2e-4)
            assert out["e.i"] == pytest.approx(math.exp(-k * 0.5) / 1000, rel=2e-3)
        assert adapter._time == pytest.approx(3e-3, abs=1e-12)
    finally:
        adapter.stop()


@needs_ngspice
def test_input_hold_alter_and_restart(tmp_path):
    adapter = _rc_adapter(tmp_path)
    adapter.start({"e.vin": 1.0, "e.r": 1000.0})
    try:
        adapter.step(5e-3, 5e-3, {"e.vin": 1.0, "e.r": 1000.0})       # ~fully charged
        out = adapter.step(5.5e-3, 5e-4, {"e.vin": 0.0, "e.r": 100.0}).outputs
        # Discharge with tau = 0.1 ms after `alter R1 = 100`: 0.5 ms -> e^-5.
        assert out["e.vout"] == pytest.approx(math.exp(-5) * (1 - math.exp(-5)), abs=2e-3)
        assert 0.0 < out["e.vout_mean"] < 0.3
    finally:
        adapter.stop()
    # The library can be reused by a new adapter after stop().
    again = _rc_adapter(tmp_path)
    again.start({"e.vin": 1.0, "e.r": 1000.0})
    try:
        assert again.step(5e-4, 5e-4, {"e.vin": 1.0}).outputs["e.vout"] == pytest.approx(1 - math.exp(-0.5), abs=2e-4)
    finally:
        again.stop()


@needs_ngspice
def test_one_owner_per_process(tmp_path):
    first, second = _rc_adapter(tmp_path), _rc_adapter(tmp_path)
    first.start({"e.vin": 1.0, "e.r": 1000.0})
    try:
        with pytest.raises(NgspiceError, match="isolate"):
            second.start({"e.vin": 1.0, "e.r": 1000.0})
    finally:
        first.stop()


@needs_ngspice
def test_hbridge_example_closed_loop(tmp_path):
    """Switching H-bridge in the loop: same trend as the mock RL model, with real
    conduction and supply losses (lower bridge voltage at full duty)."""
    project = MechatronicProject.load(HBRIDGE)
    project.duration_seconds = 0.05
    rows = CoSimulationOrchestrator(project, build_adapters(project)).run(tmp_path / "run.csv")
    last = rows[-1]
    assert last["firmware.pwm_duty"] == pytest.approx(1.0)
    # Mock: 24 V at full duty. Here: minus Rsrc (0.05 Ω) and two switches (2 x 0.02 Ω).
    expected_voltage = 24.0 - last["electrical.motor_current"] * (0.05 + 0.04)
    assert last["electrical.motor_voltage"] == pytest.approx(expected_voltage, abs=0.1)
    assert 10.0 < last["electrical.motor_current"] < 12.5
    assert last["electrical.input_power"] == pytest.approx(24.0 * last["electrical.motor_current"], rel=0.03)
    assert 1.5 < last["mechanical.velocity"] < 2.5
    with (tmp_path / "run.csv").open() as handle:
        assert len(list(csv.DictReader(handle))) == len(rows)
