from pathlib import Path

from embeddyn.mechatronics.factory import build_adapters
from embeddyn.mechatronics.model import Domain, MechatronicProject, SchedulerConfig, ConvergenceConfig, RealTimeConfig
from embeddyn.mechatronics.orchestrator import CoSimulationOrchestrator
from embeddyn.mechatronics.runtime.scheduler import RealTimeScheduler, build_scheduler
from embeddyn.mechatronics.storage.telemetry import StructuredRecordWriter

ROOT = Path(__file__).resolve().parents[2]

def test_iterative_coupling_converges():
    project = MechatronicProject.load(ROOT / "examples/mechatronics/dc-motor.yaml")
    project.duration_seconds = 0.001
    project.scheduler = SchedulerConfig(macro_step_seconds=0.001, convergence=ConvergenceConfig(True, 1e-12, 4, "error"))
    runtime = CoSimulationOrchestrator(project, build_adapters(project, mock=True))
    runtime.run()
    assert runtime.last_convergence["converged"]

def test_structured_event_and_bus_datasets(tmp_path):
    event_writer = StructuredRecordWriter(tmp_path / "events")
    bus_writer = StructuredRecordWriter(tmp_path / "buses")
    event_writer.append({"time_seconds": 0.1, "topic": "edge", "payload": {"level": 1}})
    bus_writer.append({"time_seconds": 0.1, "topic": "can", "payload": [1,2,3]})
    assert event_writer.row_count == 1 and bus_writer.row_count == 1
    assert event_writer.path.exists() and bus_writer.path.exists()

def test_real_time_scheduler_wrapper_builds():
    cfg = SchedulerConfig(algorithm="real-time-fixed-step", macro_step_seconds=0.001,
                          real_time=RealTimeConfig(True, 1000.0, 1.0, "continue"))
    assert isinstance(build_scheduler(cfg), RealTimeScheduler)

def test_component_instance_parameters_have_provenance(tmp_path):
    f = tmp_path / "p.yaml"
    f.write_text("""schema_version: 2
name: components
step_seconds: 1 ms
duration_seconds: 2 ms
components:
  definitions:
    motor: {version: 1.0.0}
  instances:
    m1:
      definition: motor
      parameters:
        resistance: 2.1 ohm
signals: {}
couplings: []
simulators: {}
""")
    project = MechatronicProject.load(f)
    assert project.parameters["m1.resistance"].unit == "ohm"
    assert project.parameter_provenance["m1.resistance"][0]["source"] == "component-instance"
