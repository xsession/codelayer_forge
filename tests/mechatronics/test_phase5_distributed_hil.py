from pathlib import Path

import pytest

from embeddyn.mechatronics.distributed import (
    DistributedCoordinator,
    JobSpec,
    WorkerCapabilities,
    WorkerRecord,
    expand_experiment,
)
from embeddyn.mechatronics.hil import HilSafetyController, HilSafetyPolicy, MockHilDevice, SafetyState


def test_worker_capability_matching_and_job_lifecycle(tmp_path: Path):
    coordinator = DistributedCoordinator(tmp_path / "metadata.sqlite3")
    worker = WorkerRecord(
        "worker-1",
        "linux-sim",
        "local://worker-1",
        WorkerCapabilities(simulators=("mock", "webots"), labels=("simulation",), max_parallel_jobs=1),
    )
    coordinator.register_worker(worker)
    incompatible = JobSpec("bad.yaml", requirements={"simulators": ["ltspice"]}, priority=100)
    compatible = JobSpec("good.yaml", requirements={"simulators": ["mock"], "labels": ["simulation"]}, priority=10)
    coordinator.submit_job(incompatible)
    coordinator.submit_job(compatible)

    claimed = coordinator.claim_job("worker-1")
    assert claimed is not None
    assert claimed["job_id"] == compatible.job_id
    coordinator.start_job(compatible.job_id, "worker-1")
    coordinator.complete_job(compatible.job_id, "worker-1", {"run_id": "r1"})
    finished = coordinator.get_job(compatible.job_id)
    assert finished["status"] == "completed"
    assert finished["result"]["run_id"] == "r1"
    assert coordinator.list_workers()[0]["active_jobs"] == 0


def test_queued_job_can_be_cancelled(tmp_path: Path):
    coordinator = DistributedCoordinator(tmp_path / "metadata.sqlite3")
    job = JobSpec("p.yaml")
    coordinator.submit_job(job)
    coordinator.request_cancel(job.job_id)
    assert coordinator.get_job(job.job_id)["status"] == "cancelled"


def test_experiment_cartesian_expansion():
    expansion = expand_experiment({
        "name": "sweep",
        "project": "/tmp/project.yaml",
        "variables": {
            "kp": {"values": [1, 2]},
            "ki": {"range": {"start": 0.1, "stop": 1.0, "count": 3, "scale": "linear"}},
        },
    })
    assert len(expansion.jobs) == 6
    assert expansion.jobs[0].arguments["parameter_overrides"] == {"ki": 0.1, "kp": 1}


def test_hil_safety_controller_clamps_and_trips():
    device = MockHilDevice()
    device.open()
    policy = HilSafetyPolicy.from_dict({
        "watchdog_timeout_seconds": 0.1,
        "require_arm_token": True,
        "outputs": {
            "motor_pwm": {"minimum": -1, "maximum": 1, "safe_value": 0},
        },
    })
    controller = HilSafetyController(policy, device.write_output)
    with pytest.raises(PermissionError):
        controller.arm("wrong", "secret")
    controller.arm("secret", "secret")
    applied = controller.write_outputs({"motor_pwm": 2.5}, now=controller.last_update + 1.0)
    assert applied["motor_pwm"] == 1.0
    controller.observe_inputs({"emergency_stop": True})
    assert controller.state == SafetyState.TRIPPED
    assert device.outputs["motor_pwm"] == 0.0


def test_hil_watchdog_applies_safe_state():
    policy = HilSafetyPolicy.from_dict({
        "watchdog_timeout_seconds": 0.1,
        "require_arm_token": False,
        "outputs": {"enable": {"minimum": 0, "maximum": 1, "safe_value": 0}},
    })
    controller = HilSafetyController(policy)
    controller.arm()
    assert not controller.check_watchdog(controller.last_heartbeat + 0.2)
    assert controller.state == SafetyState.TRIPPED
