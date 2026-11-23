# Mechatronics, distributed simulation, HIL, and digital twin

Embeddyn's mechatronics subsystem couples multiple simulation domains around an explicit signal model and scheduler. The key design goal is to make cross-domain data exchange deterministic, inspectable, and storable rather than hiding it inside one monolithic simulator.

## Architecture in one picture

```text
MechatronicProject YAML
        |
        v
 ProjectCompiler -----> compiled run/provenance
        |
        v
 adapter factory
   |       |       |
Renode   SPICE   Webots        (or mock adapters)
   \       |       /
    \      |      /
     CoSimulationOrchestrator
             |
      scheduler + couplings
             |
     telemetry/events/checkpoints
             |
       run storage/artifacts
```

See the C4 [component view](../c4/C3_COMPONENTS.md) for a broader architecture map.

## Start with mock adapters

Use the mock path first even if the final system will use real tools:

```bash
embeddyn mechatronics validate examples/mechatronics/dc-motor.yaml
embeddyn mechatronics run examples/mechatronics/dc-motor.yaml --mock
```

This isolates project-model/coupling/scheduler errors from external-process installation problems.

## Domains and adapters

Current adapter factory behavior covers:

- **firmware**: mock or Renode socket adapter,
- **electrical**: mock, ngspice, or LTspice,
- **mechanical**: mock or Webots.

The project model also defines thermal/environment domains so signals can be modeled consistently even where a dedicated external adapter is not yet selected by the current factory.

Each adapter follows the same lifecycle:

```text
prepare(context)
start(initial_signals)
step(time, step, inputs) -> outputs + diagnostics
checkpoint()/restore() where supported
health()/capabilities()
stop()
```

Use `--isolate-adapters` when process isolation is valuable. Isolated adapters are proxied through worker processes with explicit timeout handling.

## Scheduler choices

### Deterministic fixed step

Every active domain receives one activation per macro step in stable domain order. This is the simplest and easiest mode to debug.

### Multi-rate fixed step

Domains may declare smaller substeps, provided each substep divides the macro step by an integer ratio. Activations are ordered by simulation time and stable domain priority.

Use this when, for example, an electrical model needs finer updates than firmware/mechanics.

### Real-time pacing

Real-time scheduler wrappers pace simulation against wall time and apply configured deadline tolerance/policy. Real-time pacing is not the same as deterministic performance: host load can create deadline misses, so HIL projects must define safe deadline behavior.

## Couplings

Couplings are explicit signal transfers with safe typed transformations. Typical uses:

- PWM duty from firmware to electrical plant,
- motor current to mechanical torque,
- shaft velocity to back-EMF,
- measured velocity back to firmware.

Use transforms instead of embedding arbitrary code in project files. Delay steps model causal/sample delays. Be deliberate about unit conversions: an affine gain that changes units should be documented in model metadata/parameter naming.

## Convergence

Projects can enable convergence behavior with a tolerance, maximum iterations, and failure policy. Use convergence only when the coupled model requires repeated solving within a macro step; otherwise keep the single deterministic pass for simpler reasoning and faster runs.

## Run storage

The storage layer provides:

- metadata database,
- structured telemetry writers/readers,
- content-addressed artifact store,
- export helpers.

Important commands:

```bash
embeddyn mechatronics runs-list
embeddyn mechatronics runs-inspect RUN_ID
embeddyn mechatronics runs-export RUN_ID
embeddyn mechatronics artifacts-verify RUN_ID
embeddyn mechatronics replay RUN_ID
```

Use artifact verification before treating a copied/archive run as evidence.

## Checkpoints and replay

Adapters can advertise checkpoint support. The runtime checkpoint manager records recoverable state where available. Replay uses stored data to reproduce/verify execution evidence without pretending that an external simulator lacking restore can be magically rewound.

## External integrations

### Renode

The firmware adapter communicates through the project's Renode integration/socket path. Use the binding manifest to keep simulator-specific signal names out of the core coupling model.

### ngspice / LTspice

Electrical adapters operate from a circuit/netlist and exchange results through the configured adapter protocol/output. Validate the standalone circuit first; then integrate it into co-simulation.

### Webots

The mechanical adapter references a `.wbt` world and can launch/headlessly control a bridge endpoint. Keep world physics stable before debugging cross-domain control.

### KiCad

KiCad helpers bridge hardware project information into the mechatronics workflow. Treat KiCad as the hardware-authoring source, not a runtime simulator; generated/exported data should be traceable to the source board/project revision.

## Distributed workers

The distributed coordinator stores worker/job/experiment state in SQLite. A worker registers capabilities/labels, heartbeats, claims matching jobs, executes the normal Embeddyn CLI, and reports completion/failure/cancellation.

Typical flow:

```bash
embeddyn mechatronics worker-register workstation-a ...
embeddyn mechatronics worker-run workstation-a
```

On a submitter/coordinator machine:

```bash
embeddyn mechatronics job-submit examples/mechatronics/dc-motor.yaml ...
embeddyn mechatronics jobs-list
```

Key operational points:

- A job has explicit requirements and arguments.
- Parameter overrides are forwarded to `mechatronics run` and recorded in provenance.
- Worker output is contained beneath the worker output root.
- Cancellation is polled during process execution and terminates/kills the child if necessary.
- Heartbeats support stale-worker/job recovery logic.

Use a shared/coordinated database arrangement appropriate to your deployment; do not place a single SQLite file on an unreliable multi-host network filesystem and assume database semantics will remain correct.

## Parameter sweeps/experiments

Inspect expansion:

```bash
embeddyn mechatronics experiment-expand examples/mechatronics/experiments/pid-sweep.yaml
```

Submit:

```bash
embeddyn mechatronics experiment-submit examples/mechatronics/experiments/pid-sweep.yaml
```

Check:

```bash
embeddyn mechatronics experiment-status EXPERIMENT_ID
```

Use `max_jobs` as a safety limit. A Cartesian sweep grows quickly; inspect the expansion before submitting expensive external-simulator jobs.

## HIL safety

Validate the policy before any hardware is armed:

```bash
embeddyn mechatronics hil-validate examples/mechatronics/hil/safe-motor.yaml
```

The HIL safety controller model includes:

- explicit safe/armed/tripped state,
- watchdog,
- emergency stop,
- bounded outputs,
- safe fallback values,
- slew limits,
- deadline miss policy.

For real hardware, safety must exist below the Python process too. Hardware enable gating, current/voltage limits, independent e-stop paths, and target watchdogs should fail safe even if the host crashes.

## Digital twin comparison

The digital-twin layer is built around evidence rather than a single persistent magical "twin" object.

### State snapshots

`twin-state` summarizes the model/run state at a defined point.

### Comparison

`twin-compare` aligns datasets and reports metrics such as errors for mapped signals. Always review alignment/time-base assumptions before interpreting RMSE/max-error metrics.

### Calibration

`twin-calibrate` fits supported affine calibration relationships. Calibration changes should be stored as model parameters/provenance, not silently applied only to a plot.

### Uncertainty

`uncertainty-run` samples declared distributions. The example supports normal, uniform, and triangular-style parameter definitions in the current workflow.

### Requirements/evidence

Requirement YAML links a metric to an operator/threshold and evidence labels. `requirements-verify` evaluates the metrics; `evidence-report` produces a Markdown report suitable for review/versioning.

## Debugging order

When a real multi-domain run fails, diagnose in this order:

1. `validate` the project.
2. Run the same project with `--mock`.
3. Run each external model standalone.
4. Replace one mock domain at a time.
5. Inspect adapter health/binding manifests.
6. Reduce duration and use deterministic fixed-step scheduling.
7. Inspect raw signal telemetry around the first divergence.
8. Only then introduce multi-rate/convergence/real-time pacing/distributed execution.
