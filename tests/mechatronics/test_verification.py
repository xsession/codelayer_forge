import math
from pathlib import Path

import pytest
import yaml

from embeddyn.mechatronics.model import MechatronicProject
from embeddyn.mechatronics.verification import (
    convergence,
    energy_balance,
    golden,
    refine,
    run,
    scenarios,
    verify,
)

ROOT = Path(__file__).resolve().parents[2]
DC_MOTOR = ROOT / "examples/mechatronics/dc-motor.yaml"
SERVO = ROOT / "examples/mechatronics/servo-drivetrain.yaml"
TWO_WHEEL = ROOT / "examples/mechatronics/two-wheel-drive.yaml"


def test_energy_balance_on_synthetic_rows():
    """2 W in, 1 W dissipated, storage rising 1 J/s: balances exactly."""
    project = MechatronicProject.load(DC_MOTOR)
    rows = [{"time": t / 10, "p_in": 2.0, "p_loss": 1.0, "e": t / 10} for t in range(11)]
    spec = {"sources": [{"signal": "p_in"}], "sinks": [{"signal": "p_loss"}], "storage": [{"signal": "e"}]}
    result = energy_balance(project, rows, spec)
    assert result["residual"] == pytest.approx(0.0, abs=1e-12) and result["passed"]
    spec["sinks"] = [{"product": ["p_loss", 0.5]}]              # half the loss missing -> 25 % residual
    result = energy_balance(project, rows, spec)
    assert result["relative_residual"] == pytest.approx(0.25) and not result["passed"]
    with pytest.raises(ValueError, match="not a signal, parameter or number"):
        energy_balance(project, rows, {"sources": [{"product": ["nope"]}]})


def test_dc_motor_energy_balances():
    project = MechatronicProject.load(DC_MOTOR)
    project.duration_seconds = 0.1
    result = energy_balance(project, run(project), project.verification["energy"])
    assert result["relative_residual"] < 0.005
    assert result["sinks"]["copper"] > result["sinks"]["viscous"] > 0


def test_servo_energy_balances_across_four_domains():
    project = MechatronicProject.load(SERVO)
    project.duration_seconds = 0.2
    result = energy_balance(project, run(project), project.verification["energy"])
    assert result["relative_residual"] < 0.005
    assert result["storage"]["drivetrain"] > 0


def test_convergence_reports_first_order_for_explicit_coupling():
    result = convergence(DC_MOTOR, {"signals": ["mechanical.velocity"], "tolerance": 0.01}, duration=0.1)
    order = result["signals"]["mechanical.velocity"]["observed_order"]
    assert result["passed"] and 0.7 < order < 1.5
    assert result["steps"] == pytest.approx([0.0005, 0.00025, 0.000125])


def test_refine_divides_instance_steps():
    project = refine(TWO_WHEEL, 2)
    assert project.step_seconds == pytest.approx(0.0005)
    assert project.declared_instances()["wheel_left"].step_seconds == pytest.approx(0.00025)
    assert project.declared_instances()["ctrl_left"].step_seconds is None


def test_golden_write_compare_and_detect_change(tmp_path):
    data = yaml.safe_load(DC_MOTOR.read_text())
    data["duration_seconds"] = 0.05
    path = tmp_path / "p.yaml"
    path.write_text(yaml.safe_dump(data))
    project = MechatronicProject.load(path)
    spec = {"file": "g.csv", "every": 0.01, "signals": {"mechanical.velocity": 1e-6}}
    rows = run(project)
    assert golden(project, rows, spec)["written"]
    assert golden(project, rows, spec)["passed"]
    for row in rows:
        row["mechanical.velocity"] += 0.01
    result = golden(project, rows, spec)
    assert not result["passed"] and result["max_abs_error"]["mechanical.velocity"] == pytest.approx(0.01)


def test_scenarios_report_values_and_errors():
    result = scenarios(DC_MOTOR, [
        {"name": "ok", "duration": 0.05, "expect": [{"metric": "current.peak", "max": 100}]},
        {"name": "too-strict", "duration": 0.05, "expect": [{"metric": "current.peak", "max": 1}]},
        {"name": "unsettled", "duration": 0.05, "expect": [{"metric": "speed.settling_time", "max": 1}]},
    ])
    status = {item["name"]: item["passed"] for item in result["scenarios"]}
    assert status == {"ok": True, "too-strict": False, "unsettled": False}
    assert result["scenarios"][2]["checks"][0]["value"] is None
    with pytest.raises(ValueError, match="unknown signal"):
        scenarios(DC_MOTOR, [{"signals": {"nope": 1}}])


def test_verify_selects_checks_and_rejects_unknown():
    report = verify(DC_MOTOR, only=["scenarios"])
    assert set(report["checks"]) == {"scenarios"} and report["passed"]
    with pytest.raises(ValueError, match="unknown verification checks"):
        verify(DC_MOTOR, only=["bogus"])
