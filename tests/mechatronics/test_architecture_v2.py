import json
from pathlib import Path

import pytest

from embeddyn.mechatronics.compiler import ProjectCompiler
from embeddyn.mechatronics.model import MechatronicProject
from embeddyn.mechatronics.quantities import Quantity


def test_quantity_parses_compact_and_structured():
    assert Quantity.parse("24 V") == Quantity(24.0, "V")
    assert Quantity.parse({"value": 2.0, "unit": "ohm"}) == Quantity(2.0, "ohm")


def test_v2_project_compiles_immutable_run(tmp_path):
    project_file = tmp_path / "project.yaml"
    project_file.write_text("""
schema_version: 2
name: v2-motor
scheduler:
  algorithm: multirate-fixed-step
  macro_step: 1 ms
  domains:
    electrical: {step: 0.1 ms}
duration_seconds: 10 ms
parameters:
  motor.resistance: {value: 2.1, unit: ohm}
signals:
  electrical.current: {domain: electrical, unit: A, initial: 0 A}
  mechanical.torque: {domain: mechanical, unit: N*m, initial: 0 N*m}
couplings:
  - source: electrical.current
    target: mechanical.torque
    transform: {type: affine, gain: 0.08}
simulators: {}
""", encoding="utf-8")
    project = MechatronicProject.load(project_file)
    compiled = ProjectCompiler().compile(project, tmp_path / "runs")
    manifest = json.loads(compiled.manifest_path.read_text(encoding="utf-8"))
    assert manifest["result_status"] == "compiled"
    assert manifest["scheduler"]["algorithm"] == "multirate-fixed-step"
    assert manifest["resolved_parameters"]["motor.resistance"]["unit"] == "ohm"
    assert (compiled.directory / "project.normalized.json").exists()


def test_unsafe_expression_is_rejected(tmp_path):
    project_file = tmp_path / "unsafe.yaml"
    project_file.write_text("""
name: unsafe
step_seconds: 0.1
duration_seconds: 1
signals:
  a: {domain: firmware}
  b: {domain: firmware}
couplings:
  - {source: a, target: b, expression: "x * 2"}
""", encoding="utf-8")
    with pytest.raises(ValueError, match="unsafe coupling expressions"):
        MechatronicProject.load(project_file)


def test_parameter_overrides_reach_runtime_and_manifest(tmp_path):
    from embeddyn.mechatronics.factory import build_adapters
    from embeddyn.mechatronics.orchestrator import CoSimulationOrchestrator

    root = Path(__file__).resolve().parents[2]
    default_project = MechatronicProject.load(root / "examples/mechatronics/dc-motor.yaml")
    default_project.duration_seconds = 0.001
    default_rows = CoSimulationOrchestrator(default_project, build_adapters(default_project, mock=True)).run()

    overridden = MechatronicProject.load(root / "examples/mechatronics/dc-motor.yaml")
    overridden.duration_seconds = 0.001
    overridden.apply_parameter_overrides({"controller.kp": 0.0, "controller.ki": 0.0}, source="test")
    override_rows = CoSimulationOrchestrator(overridden, build_adapters(overridden, mock=True)).run()
    assert default_rows[-1]["firmware.pwm_duty"] != override_rows[-1]["firmware.pwm_duty"]
    assert override_rows[-1]["firmware.pwm_duty"] == 0.0

    compiled = ProjectCompiler().compile(overridden, tmp_path / "runs")
    manifest = json.loads(compiled.manifest_path.read_text(encoding="utf-8"))
    assert manifest["resolved_parameters"]["controller.kp"]["value"] == 0.0
    assert manifest["resolved_parameters"]["controller.kp"]["provenance"][-1]["source"] == "test"


def test_project_validation_rejects_non_finite_and_inconsistent_scheduler(tmp_path):
    nan_project = tmp_path / "nan.yaml"
    nan_project.write_text("""
name: bad
step_seconds: .nan
duration_seconds: 1
signals: {}
couplings: []
simulators: {}
""", encoding="utf-8")
    with pytest.raises(ValueError, match="finite positive"):
        MechatronicProject.load(nan_project)

    inconsistent = tmp_path / "inconsistent.yaml"
    inconsistent.write_text("""
name: bad-scheduler
step_seconds: 1 ms
scheduler:
  macro_step: 2 ms
duration_seconds: 10 ms
signals: {}
couplings: []
simulators: {}
""", encoding="utf-8")
    with pytest.raises(ValueError, match="macro_step must match"):
        MechatronicProject.load(inconsistent)
