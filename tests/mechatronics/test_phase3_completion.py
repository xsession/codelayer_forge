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


def test_event_and_bus_signals_do_not_break_numeric_telemetry(tmp_path):
    from embeddyn.mechatronics.adapters.base import SimulatorAdapter, StepResult
    from embeddyn.mechatronics.model import Signal, SignalKind
    from embeddyn.mechatronics.storage.telemetry import TelemetryWriter, read_telemetry_rows

    class EventBusAdapter(SimulatorAdapter):
        name = "event-bus"

        def start(self, initial_signals):
            pass

        def step(self, time_seconds, step_seconds, inputs):
            return StepResult({
                "firmware.scalar": 1.0,
                "firmware.event": {"edge": "rising"},
                "firmware.bus": {"id": 1, "data": [1, 2, 3]},
            })

        def stop(self):
            pass

    project = MechatronicProject(
        name="events",
        step_seconds=0.001,
        duration_seconds=0.001,
        signals={
            "firmware.scalar": Signal("firmware.scalar", Domain.FIRMWARE),
            "firmware.event": Signal("firmware.event", Domain.FIRMWARE, kind=SignalKind.EVENT),
            "firmware.bus": Signal("firmware.bus", Domain.FIRMWARE, kind=SignalKind.BUS),
        },
        couplings=[],
        simulators={},
        root=tmp_path,
        scheduler=SchedulerConfig(macro_step_seconds=0.001),
    )
    project.validate()
    telemetry = TelemetryWriter(tmp_path / "telemetry")
    events = StructuredRecordWriter(tmp_path / "events")
    buses = StructuredRecordWriter(tmp_path / "buses")
    rows = CoSimulationOrchestrator(project, {Domain.FIRMWARE: EventBusAdapter()}).run(
        telemetry_writer=telemetry,
        event_writer=events,
        bus_writer=buses,
    )
    numeric_rows = read_telemetry_rows(telemetry.path)
    assert len(rows) == 2
    assert list(numeric_rows[0]) == ["time", "firmware.scalar"]
    assert events.row_count == 1
    assert buses.row_count == 1


def test_zero_delay_bus_coupling_does_not_require_history(tmp_path):
    from embeddyn.mechatronics.model import Coupling, Signal, SignalKind

    project = MechatronicProject(
        name="bus-coupling",
        step_seconds=0.001,
        duration_seconds=0.001,
        signals={
            "firmware.bus_value": Signal("firmware.bus_value", Domain.FIRMWARE, initial=2.0, kind=SignalKind.BUS),
            "firmware.scalar": Signal("firmware.scalar", Domain.FIRMWARE, initial=0.0),
        },
        couplings=[Coupling("firmware.bus_value", "firmware.scalar")],
        simulators={},
        root=tmp_path,
        scheduler=SchedulerConfig(macro_step_seconds=0.001),
    )
    project.validate()
    runtime = CoSimulationOrchestrator(project, {})
    rows = runtime.run()
    assert rows[-1]["firmware.scalar"] == 2.0


def test_snapshot_values_are_independent_from_runtime_state():
    project = MechatronicProject.load(ROOT / "examples/mechatronics/dc-motor.yaml")
    runtime = CoSimulationOrchestrator(project, build_adapters(project, mock=True))
    snapshot = runtime.snapshot()
    key = next(iter(runtime.values))
    before = snapshot["values"][key]
    runtime.values[key] = before + 1.0
    assert snapshot["values"][key] == before
