# Metrics, tuning and plant models

Three pieces turn the co-simulation into a tuning tool: metrics computed
from every run, an optimiser that varies parameters across runs, and Python
plant models for the physics that the built-in mock doesn't cover.

## Metrics

A project declares named metrics; `mechatronics run` computes them after the
run, prints them in its JSON summary and writes `metrics.json` into the run
directory. Distributed sweep jobs record them too (an experiment's
`metrics:` list selects which).

```yaml
metrics:
  speed: {type: step_response, signal: mechanical.velocity, target: firmware.target_velocity, settling_band: 0.02}
  current: {type: stats, signal: electrical.motor_current}
  energy: {type: integral, signal: electrical.input_power}
```

| Type | Results (`<name>.<result>`) |
|------|-----------------------------|
| `step_response` | `rise_time` (10–90 %), `overshoot` (%), `peak_time`, `settling_time` (last exit from the band), `final_value`, `steady_state_error`, `iae`, `ise`, `itae` |
| `stats` | `peak` (max \|x\|), `rms`, `mean` (time-weighted), `min`, `max` |
| `integral` | `integral` (trapezoidal; power gives energy in J) |

`target` is a signal name or a number. `start`/`end` restrict the time
window. A response that never rises or settles reports `null`, never a made-up
number. `embeddyn mechatronics metrics <project> <run.csv>` recomputes the
metrics from an exported CSV.

The step-response figures are checked against the closed-form second-order
response (overshoot within 0.1 %, peak time within 2 ms).

## Tuning

```bash
embeddyn mechatronics tune examples/mechatronics/tuning/servo-pi.yaml -o result.json
```

```yaml
project: ../servo-drivetrain.yaml
mock: false                 # true forces the built-in simulators
duration: 1.0               # optional duration override
parameters:                 # project parameters; they reach every adapter as inputs
  controller.kp: {initial: 0.5, min: 0.02, max: 3.0, scale: log}
  controller.ki: {initial: 4.0, min: 0.1, max: 40.0, scale: log}
objective:                  # minimise sum(weight * metric)
  - {metric: speed.itae, weight: 1.0}
  - {metric: shaft.peak, weight: 0.002}
constraints:                # penalised; a missing metric counts as violated
  - {metric: speed.overshoot, max: 5.0}
  - {metric: speed.settling_time, max: 0.5}
max_evaluations: 30
```

* The optimiser is a bounded Nelder–Mead in a normalised space (0..1 per
  parameter, logarithmic with `scale: log`). It is deterministic.
* Every evaluation is a full co-simulation with whatever backends the project
  uses. To tune the **real firmware**, bind the parameter name to its RAM
  location in the Renode bindings (a `float32` `sysbus` input, as the
  set-point test in `test_renode_real.py` does); `integration-validate`
  accepts bindings to parameter names.
* A failing candidate (diverging model, simulator error) is recorded with its
  error and scored as infinite; the search continues.
* `result.json` holds every evaluation: parameters, objective, violations,
  all metrics, wall time.

Results on this machine:

| Spec | Start | Best after | Time |
|------|-------|-----------|------|
| `tuning/pi-mock.yaml` (dc-motor, 1 s) | kp 0.12, ki 0.8: violates overshoot and settling | kp 2.0 (bound), ki 0.74: feasible | 40 runs, 10 s |
| `tuning/servo-pi.yaml` (geared servo, 1 s) | kp 0.5, ki 4.0: overshoot 34 % | kp 0.56, ki 1.45: feasible | 30 runs, 50 s |

The servo case first came out infeasible: the mock controller's integrator
wound up during saturation, so every gain pair that settled fast overshot.
The mock controller now has opt-in anti-windup (`controller.anti_windup: 1`,
conditional integration as in the reference firmware); the servo example
enables it.

## Python plant models (`backend: python`)

Any domain can run a Python ODE model, integrated with fixed-step RK4
(`max_step`) between co-simulation steps; inputs are held for the step.

```yaml
mechanical:
  model: "embeddyn.mechatronics.plants:GearedDrivetrain"   # or "plants/my.py:MyPlant"
  options:
    backend: python
    max_step: 2.0e-5
    parameters: {gear_ratio: 10, backlash: "@drivetrain.backlash"}  # "@name" = project parameter
    inputs: {motor_torque: mechanical.motor_torque}
    outputs: {motor_speed: mechanical.velocity, shaft_torque: mechanical.shaft_torque}
```

A plant class declares `inputs`, `outputs` and `states`, and implements
`initial_state()`, `derivatives(t, x, u)` and `output(t, x, u)`; see
`embeddyn/mechatronics/adapters/python_model.py`. Checkpoint/restore works.
Plant parameters given as `"@name"` come from project parameters, so design
values (backlash, gear ratio, inertia) can be swept and tuned like gains.

Built-in plants (`embeddyn/mechatronics/plants.py`):

* **`GearedDrivetrain`**: motor rotor → gearbox (ratio, efficiency, backlash
  gap) → compliant shaft (spring-damper that transmits torque only in contact
  and never pulls) → load with viscous, Coulomb and Stribeck friction
  (tanh-regularised) → incremental encoder (`encoder_cpr`). Outputs motor and
  load angle/speed, shaft and friction torque, encoder count, backlash contact.
* **`ThermalRC`**: winding temperature with copper loss I²·R(T) and
  R(T) = R20 (1 + α (T − 20)); feeds the resistance back to the electrical
  model.

The `thermal` and `environment` domains are now built by the factory when a
project configures them (python backend), and they run in the scheduler's
order after the mechanical domain.

### Example: geared servo with thermal feedback

`examples/mechatronics/servo-drivetrain.yaml` couples four domains: the mock
firmware PI (with anti-windup), the mock RL motor model, the geared
drivetrain with 4 mrad backlash and Stribeck friction, and the winding
thermal model, whose resistance feeds back into the motor. One second runs in
about 4 s. With the starting gains: 34 % overshoot, an 18.6 N·m shaft torque
peak during the first acceleration, and +4.9 K winding temperature. Replace
the firmware and electrical simulators with Renode and `ngspice-shared` as in
`dc-motor-full.yaml` to put the real firmware and the switching bridge in the
same loop.
