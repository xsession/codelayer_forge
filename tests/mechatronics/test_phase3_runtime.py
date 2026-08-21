from pathlib import Path

from embeddyn.mechatronics.factory import build_adapters
from embeddyn.mechatronics.model import Domain, MechatronicProject, SchedulerConfig
from embeddyn.mechatronics.orchestrator import CoSimulationOrchestrator
from embeddyn.mechatronics.runtime import CheckpointManager, EventQueue, MultiRateFixedStepScheduler

ROOT = Path(__file__).resolve().parents[2]


def test_multirate_schedule_activation_counts():
    config = SchedulerConfig(
        algorithm="multirate-fixed-step",
        macro_step_seconds=0.001,
        domain_steps={
            Domain.FIRMWARE: 0.0001,
            Domain.ELECTRICAL: 0.00001,
            Domain.MECHANICAL: 0.001,
        },
    )
    activations = list(MultiRateFixedStepScheduler(config).activations(0.0, 0.001))
    assert sum(a.domain is Domain.FIRMWARE for a in activations) == 10
    assert sum(a.domain is Domain.ELECTRICAL for a in activations) == 100
    assert sum(a.domain is Domain.MECHANICAL for a in activations) == 1
    assert activations == sorted(activations, key=lambda a: a.time_seconds)


def test_event_queue_is_deterministic():
    queue = EventQueue()
    queue.publish(0.2, "late", 2)
    queue.publish(0.1, "first", 1)
    queue.publish(0.1, "second", 2)
    assert [event.topic for event in queue.drain_until(0.1)] == ["first", "second"]
    assert [event.topic for event in queue.drain_until(1.0)] == ["late"]


def test_multirate_orchestrator_uses_domain_steps():
    project = MechatronicProject.load(ROOT / "examples/mechatronics/dc-motor.yaml")
    project.duration_seconds = 0.002
    project.step_seconds = 0.001
    project.scheduler = SchedulerConfig(
        algorithm="multirate-fixed-step",
        macro_step_seconds=0.001,
        domain_steps={
            Domain.FIRMWARE: 0.0001,
            Domain.ELECTRICAL: 0.00001,
            Domain.MECHANICAL: 0.001,
        },
    )
    runtime = CoSimulationOrchestrator(project, build_adapters(project, mock=True))
    rows = runtime.run()
    assert len(rows) == 3
    assert runtime.activation_count[Domain.FIRMWARE] == 20
    assert runtime.activation_count[Domain.ELECTRICAL] == 200
    assert runtime.activation_count[Domain.MECHANICAL] == 2


def test_checkpoint_resume_matches_continuation(tmp_path):
    project = MechatronicProject.load(ROOT / "examples/mechatronics/dc-motor.yaml")
    project.duration_seconds = 0.004
    manager = CheckpointManager(tmp_path / "checkpoints")
    first = CoSimulationOrchestrator(project, build_adapters(project, mock=True))
    first.run(checkpoint_manager=manager, checkpoint_interval_seconds=0.002)
    checkpoint = sorted((tmp_path / "checkpoints").glob("*.json"))[0]

    resumed = CoSimulationOrchestrator(project, build_adapters(project, mock=True))
    rows = resumed.run(resume_from=checkpoint)
    assert rows[0]["time"] == 0.002
    assert rows[-1]["time"] == 0.004
    assert resumed.current_time == project.duration_seconds


def test_mock_adapter_capabilities_include_checkpoints():
    project = MechatronicProject.load(ROOT / "examples/mechatronics/dc-motor.yaml")
    adapters = build_adapters(project, mock=True)
    assert all(adapter.capabilities()["checkpoint"] for adapter in adapters.values())


def test_mock_adapter_can_run_in_isolated_worker():
    project = MechatronicProject.load(ROOT / "examples/mechatronics/dc-motor.yaml")
    project.duration_seconds = 0.001
    adapters = build_adapters(project, mock=True, isolate=True)
    rows = CoSimulationOrchestrator(project, adapters).run()
    assert rows[-1]["time"] == 0.001
