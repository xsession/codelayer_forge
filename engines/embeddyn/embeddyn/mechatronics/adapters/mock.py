from __future__ import annotations

from typing import Mapping

from .base import SimulatorAdapter, StepResult


class MockMechanicalAdapter(SimulatorAdapter):
    name = "mock-mechanical"

    def __init__(self) -> None:
        self.position = 0.0
        self.velocity = 0.0

    def start(self, initial_signals: Mapping[str, float]) -> None:
        self.position = float(initial_signals.get("mechanical.position", 0.0))
        self.velocity = float(initial_signals.get("mechanical.velocity", 0.0))

    def step(self, time_seconds: float, step_seconds: float, inputs: Mapping[str, float]) -> StepResult:
        torque = float(inputs.get("mechanical.motor_torque", 0.0))
        load = float(inputs.get("mechanical.load_torque", 0.0))
        damping = float(inputs.get("mechanical.damping", 0.08))
        inertia = max(float(inputs.get("mechanical.inertia", 0.02)), 1e-9)
        acceleration = (torque - load - damping * self.velocity) / inertia
        self.velocity += acceleration * step_seconds
        self.position += self.velocity * step_seconds
        return StepResult({
            "mechanical.position": self.position,
            "mechanical.velocity": self.velocity,
            "mechanical.acceleration": acceleration,
        })

    def checkpoint(self) -> object:
        return {"position": self.position, "velocity": self.velocity}

    def restore(self, checkpoint: object) -> None:
        state = dict(checkpoint or {})
        self.position = float(state.get("position", 0.0))
        self.velocity = float(state.get("velocity", 0.0))

    def capabilities(self) -> dict[str, bool]:
        return {**super().capabilities(), "checkpoint": True}

    def stop(self) -> None:
        pass


class MockElectricalAdapter(SimulatorAdapter):
    name = "mock-electrical"

    def __init__(self) -> None:
        self.current = 0.0

    def start(self, initial_signals: Mapping[str, float]) -> None:
        self.current = float(initial_signals.get("electrical.motor_current", 0.0))

    def step(self, time_seconds: float, step_seconds: float, inputs: Mapping[str, float]) -> StepResult:
        duty = max(-1.0, min(1.0, float(inputs.get("electrical.pwm_duty", 0.0))))
        supply = float(inputs.get("electrical.supply_voltage", 24.0))
        resistance = max(float(inputs.get("electrical.motor_resistance", 2.0)), 1e-9)
        inductance = max(float(inputs.get("electrical.motor_inductance", 0.003)), 1e-9)
        back_emf = float(inputs.get("electrical.back_emf", 0.0))
        voltage = duty * supply
        di = (voltage - back_emf - resistance * self.current) / inductance
        self.current += di * step_seconds
        return StepResult({
            "electrical.motor_voltage": voltage,
            "electrical.motor_current": self.current,
            "electrical.input_power": voltage * self.current,
        })

    def checkpoint(self) -> object:
        return {"current": self.current}

    def restore(self, checkpoint: object) -> None:
        self.current = float(dict(checkpoint or {}).get("current", 0.0))

    def capabilities(self) -> dict[str, bool]:
        return {**super().capabilities(), "checkpoint": True}

    def stop(self) -> None:
        pass


class MockFirmwareAdapter(SimulatorAdapter):
    name = "mock-firmware"

    def __init__(self) -> None:
        self.integral = 0.0

    def start(self, initial_signals: Mapping[str, float]) -> None:
        self.integral = 0.0

    def step(self, time_seconds: float, step_seconds: float, inputs: Mapping[str, float]) -> StepResult:
        target = float(inputs.get("firmware.target_velocity", 5.0))
        actual = float(inputs.get("firmware.measured_velocity", 0.0))
        error = target - actual
        kp = float(inputs.get("controller.kp", 0.12))
        ki = float(inputs.get("controller.ki", 0.8))
        candidate = self.integral + error * step_seconds
        raw = kp * error + ki * candidate
        duty = max(-1.0, min(1.0, raw))
        # controller.anti_windup = 1: conditional integration (freeze the
        # integrator while the output saturates), as in the reference firmware.
        if not (float(inputs.get("controller.anti_windup", 0.0)) and raw != duty):
            self.integral = candidate
        return StepResult({"firmware.pwm_duty": duty, "firmware.control_error": error})

    def checkpoint(self) -> object:
        return {"integral": self.integral}

    def restore(self, checkpoint: object) -> None:
        self.integral = float(dict(checkpoint or {}).get("integral", 0.0))

    def capabilities(self) -> dict[str, bool]:
        return {**super().capabilities(), "checkpoint": True}

    def stop(self) -> None:
        pass
