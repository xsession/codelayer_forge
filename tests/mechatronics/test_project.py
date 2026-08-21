from pathlib import Path

import pytest

from embeddyn.mechatronics.factory import build_adapters
from embeddyn.mechatronics.model import Domain, MechatronicProject
from embeddyn.mechatronics.orchestrator import CoSimulationOrchestrator

ROOT = Path(__file__).resolve().parents[2]


def test_project_loads_and_validates():
    project = MechatronicProject.load(ROOT / "examples/mechatronics/dc-motor.yaml")
    assert project.name == "dc-motor-speed-control"
    assert len(project.signals) >= 15
    assert {Domain.FIRMWARE, Domain.ELECTRICAL, Domain.MECHANICAL} <= set(project.simulators)


def test_mock_cosimulation_is_deterministic(tmp_path):
    project = MechatronicProject.load(ROOT / "examples/mechatronics/dc-motor.yaml")
    project.duration_seconds = 0.02
    first = CoSimulationOrchestrator(project, build_adapters(project, mock=True)).run(tmp_path / "first.csv")
    second = CoSimulationOrchestrator(project, build_adapters(project, mock=True)).run(tmp_path / "second.csv")
    assert first == second
    assert first[-1]["mechanical.velocity"] != 0.0
    assert (tmp_path / "first.csv").read_text().startswith("time,")


def test_unknown_coupling_fails(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("""
name: bad
step_seconds: 0.1
duration_seconds: 1
signals:
  a: {domain: firmware}
couplings:
  - {source: missing, target: a}
""")
    with pytest.raises(ValueError, match="unknown coupling source"):
        MechatronicProject.load(path)
