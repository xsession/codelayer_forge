"""Built-in plant models for the `python` backend (see adapters/python_model.py)."""
from __future__ import annotations

import math
from typing import Mapping, Sequence


class GearedDrivetrain:
    """Motor rotor -> gearbox with backlash -> compliant shaft -> load with friction.

    States: motor angle/speed (motor side) and load angle/speed (output side).
    The gear couples the motor angle divided by `gear_ratio` to the load through
    a spring-damper that only transmits torque outside the backlash gap.
    Load friction is viscous + Coulomb + Stribeck, regularised with tanh so the
    ODE stays smooth (`friction_speed` sets the regularisation width).
    An incremental encoder on the load counts `encoder_cpr` per revolution.
    """

    inputs = ("motor_torque", "load_torque")
    outputs = ("motor_angle", "motor_speed", "motor_acceleration", "load_angle", "load_speed",
               "shaft_torque", "friction_torque", "encoder_count", "backlash_contact")
    states = ("motor_angle", "motor_speed", "load_angle", "load_speed")

    def __init__(self, motor_inertia: float = 0.002, motor_damping: float = 1e-4, gear_ratio: float = 10.0,
                 gear_efficiency: float = 1.0, backlash: float = 0.0, shaft_stiffness: float = 2000.0,
                 shaft_damping: float = 2.0, load_inertia: float = 0.5, load_damping: float = 0.05,
                 coulomb_friction: float = 0.0, static_friction: float | None = None, stribeck_speed: float = 0.05,
                 friction_speed: float = 1e-3, encoder_cpr: int = 0, motor_angle: float = 0.0, motor_speed: float = 0.0,
                 load_angle: float = 0.0, load_speed: float = 0.0) -> None:
        if motor_inertia <= 0 or load_inertia <= 0 or gear_ratio == 0:
            raise ValueError("inertias must be positive and gear_ratio non-zero")
        if backlash < 0 or not 0 < gear_efficiency <= 1:
            raise ValueError("backlash must be >= 0 and 0 < gear_efficiency <= 1")
        self.jm, self.bm, self.n, self.eta = motor_inertia, motor_damping, gear_ratio, gear_efficiency
        self.backlash, self.k, self.c = backlash, shaft_stiffness, shaft_damping
        self.jl, self.bl = load_inertia, load_damping
        self.tc = coulomb_friction
        self.ts = coulomb_friction if static_friction is None else static_friction
        self.ws, self.eps, self.cpr = stribeck_speed, friction_speed, int(encoder_cpr)
        self.x0 = [motor_angle, motor_speed, load_angle, load_speed]

    def initial_state(self) -> list[float]:
        return list(self.x0)

    def _shaft(self, x: Sequence[float]) -> tuple[float, bool]:
        twist = x[0] / self.n - x[2]
        half_gap = self.backlash / 2
        if abs(twist) <= half_gap:
            return 0.0, False
        rate = x[1] / self.n - x[3]
        torque = self.k * (twist - math.copysign(half_gap, twist)) + self.c * rate
        # A damper can't pull the teeth apart: no tension through an opening contact.
        if torque * twist < 0:
            torque = 0.0
        return torque, True

    def _friction(self, speed: float) -> float:
        level = self.tc + (self.ts - self.tc) * math.exp(-(speed / self.ws) ** 2) if self.ws > 0 else self.tc
        return level * math.tanh(speed / self.eps) + self.bl * speed

    def derivatives(self, t: float, x: Sequence[float], u: Mapping[str, float]) -> list[float]:
        shaft, _ = self._shaft(x)
        motor_side = shaft / self.n / (self.eta if shaft * x[1] > 0 else 1.0)
        motor_acc = (u.get("motor_torque", 0.0) - self.bm * x[1] - motor_side) / self.jm
        load_acc = (shaft - self._friction(x[3]) - u.get("load_torque", 0.0)) / self.jl
        return [x[1], motor_acc, x[3], load_acc]

    def output(self, t: float, x: Sequence[float], u: Mapping[str, float]) -> dict[str, float]:
        shaft, contact = self._shaft(x)
        derivative = self.derivatives(t, x, u)
        counts = math.floor(x[2] / (2 * math.pi) * self.cpr) if self.cpr else 0
        return {
            "motor_angle": x[0], "motor_speed": x[1], "motor_acceleration": derivative[1],
            "load_angle": x[2], "load_speed": x[3], "shaft_torque": shaft,
            "friction_torque": self._friction(x[3]), "encoder_count": float(counts),
            "backlash_contact": 1.0 if contact else 0.0,
        }


class ThermalRC:
    """First-order winding thermal model with copper loss from the current:

        C dT/dt = I^2 R(T) - (T - T_ambient) / R_th,   R(T) = R20 (1 + alpha (T - 20))

    `resistance` is fed back to the electrical model, closing the
    current -> heating -> resistance -> current loop.
    """

    inputs = ("current", "ambient")
    outputs = ("temperature", "resistance", "copper_loss")
    states = ("temperature",)

    def __init__(self, thermal_resistance: float = 2.0, thermal_capacitance: float = 50.0,
                 resistance_20c: float = 2.0, alpha: float = 0.00393, initial_temperature: float = 25.0) -> None:
        if thermal_resistance <= 0 or thermal_capacitance <= 0 or resistance_20c <= 0:
            raise ValueError("thermal resistance, capacitance and R20 must be positive")
        self.rth, self.cth, self.r20, self.alpha, self.t0 = (
            thermal_resistance, thermal_capacitance, resistance_20c, alpha, initial_temperature)

    def initial_state(self) -> list[float]:
        return [self.t0]

    def _resistance(self, temperature: float) -> float:
        return self.r20 * (1 + self.alpha * (temperature - 20.0))

    def derivatives(self, t: float, x: Sequence[float], u: Mapping[str, float]) -> list[float]:
        loss = u.get("current", 0.0) ** 2 * self._resistance(x[0])
        return [(loss - (x[0] - u.get("ambient", 25.0)) / self.rth) / self.cth]

    def output(self, t: float, x: Sequence[float], u: Mapping[str, float]) -> dict[str, float]:
        resistance = self._resistance(x[0])
        return {"temperature": x[0], "resistance": resistance, "copper_loss": u.get("current", 0.0) ** 2 * resistance}
