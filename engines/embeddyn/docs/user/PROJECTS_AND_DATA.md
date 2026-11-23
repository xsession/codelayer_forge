# Projects, data, and file formats

Embeddyn deliberately uses several data models because a design graph, a co-simulation model, raw firmware, and telemetry have different lifecycle and validation requirements. This document explains where each belongs.

## Repository versus workspace versus data directory

| Location | Typical contents | Lifecycle |
|---|---|---|
| Repository | Embeddyn source, docs, examples, manifest/lock, bundled external trees | Version controlled/released. |
| `workspace/` | resources, generated boards/apps, Zephyr/tool workspace, default local library | Reproducible engineering workspace. |
| Studio data directory | local SQLite DB, content-addressed uploaded assets, logs/exports/token | User/runtime state; back up separately. |
| `.embeddyn/` | bootstrap env helper and mechatronics runtime/storage state depending on command defaults | Generated local state. |
| run output root | compiled manifests, telemetry, checkpoints, artifacts/evidence | Engineering result/provenance. |

Do not commit large generated runtime data unless it is a deliberate small test fixture.

## Classic component specification

The classic graph/build path loads `workspace/embeddyn-resources/components-specification.json` through `embeddyn.specification.Specification`.

At a high level the specification contains:

- `metadata`,
- `nodes`, including normal nodes,
- category nodes (`isCategory`),
- abstract nodes (`abstract`),
- inheritance-like `extends`,
- interfaces/properties used by graph/build logic.

Specification modifications may update metadata, add nodes, and add interfaces/properties to named nodes. See the existing example `embeddyn/spec_mods/interactive.json` and the root README for the modification format.

## Embedded design graph

`embeddyn.graph.Graph` resolves graph JSON against the specification. The build path expects a graph that contains a supported SoC and connected components. The graph name is normalized into a Zephyr board name.

The graph should remain a declarative description. Avoid storing process commands or machine-specific absolute paths in graph metadata.

## Generated Zephyr content

`prepare-zephyr-app` derives a board/application from the graph and specification, then uses argument-vector based west invocation rather than a shell-built command.

Generated content may include:

- a generated board directory and overlay,
- application sources rendered from templates,
- Zephyr build output,
- copied build images such as `zephyr.elf`, `zephyr.dts`, `.config`, and build log.

Treat generated boards/apps as rebuildable artifacts. Keep source graphs/spec modifications/templates as the inputs you version-control.

## Local Studio schema

Studio metadata lives in `embeddyn-local.db`. The current schema includes these conceptual entities:

```text
components
assets
projects
sessions
telemetry
logs
analyses
metadata/schema information
```

Relationships include project/session references and asset/session references; deleting a session cascades its telemetry/log-style child data where the schema declares that relationship.

The asset blob itself is stored outside SQLite under a SHA-256 content-addressed path. This separation keeps the database small and makes duplicate binary uploads naturally deduplicated.

## Telemetry point model

A Studio telemetry point has:

```json
{
  "timestamp": 1234.5,
  "channel": "motor.current",
  "value": 1.23,
  "kind": "analog",
  "metadata": {"unit": "A"}
}
```

Values can be numeric, boolean, or text. Numeric engineering analysis obviously requires a numeric channel. Time bounds and channel selection should be explicit when extracting RF/noise analysis from a session.

## Aggregated component library

The separate `embeddyn library` subsystem defaults to `workspace/library` and has:

```text
library/
  library.yml
  sources/
    embeddyn-resources/
    designer-media-files/
    hardware-components/
    designer-graphs/
    custom/
  store/
    library.sqlite3
    objects/
  generated/
    components-specification.json
  manifests/
  licenses/
```

The default library is offline (`offline: true`). `library sync` previews network actions unless `--apply` is given; import consumes material already in source directories.

Supported importer families currently include:

- classic Embeddyn/VSD component specification JSON,
- Antmicro-style hardware component JSON,
- media (`webp`, `webm`, `png`, `jpg/jpeg`, `svg`, `gltf/glb`, `blend`),
- designer graph JSON.

Media blobs use content-addressed object storage.

## Mechatronics project YAML

A mechatronics project is loaded by `MechatronicProject.load`. Core keys are:

```yaml
name: my-system
step_seconds: 0.001
duration_seconds: 1.0

simulators: {}
signals: {}
couplings: []
```

### Signals

Each signal declares:

- `domain`: firmware/electrical/mechanical/thermal/environment,
- optional engineering `unit`,
- `initial`,
- optional `min` / `max`,
- optional `data_type`,
- `kind`: continuous/discrete/event/bus,
- optional quantity/retention metadata.

Initial/min/max values support the project's quantity parsing rules. Validation rejects non-finite values and inconsistent bounds.

### Couplings

A coupling connects a known source signal to a known target signal:

```yaml
couplings:
  - source: electrical.motor_current
    target: mechanical.motor_torque
    transform:
      type: affine
      gain: 0.08
      offset: 0
    delay_steps: 0
```

Supported typed transforms are `identity`, `affine`, `clamp`, `deadband`, and `quantize`. Arbitrary coupling expressions are intentionally rejected. Delayed sources must be continuous/discrete. Unit validation protects identity-like transfers when both sides declare units.

### Scheduler

The scheduler supports deterministic fixed step, deterministic multi-rate, and real-time-paced equivalents. Domain substeps must divide the macro step.

Example:

```yaml
scheduler:
  algorithm: multirate-fixed-step
  macro_step: 1 ms
  domains:
    firmware: 1 ms
    electrical: 0.25 ms
    mechanical: 1 ms
  convergence:
    enabled: false
    tolerance: 1e-9
    max_iterations: 8
    failure_policy: error
```

### Parameters and overrides

Project parameters can be overridden at runtime/experiment expansion. Overrides are parsed as quantities and appended to parameter provenance rather than silently replacing history.

## Experiment YAML

Experiments describe a source project, worker requirements, fixed arguments, variable dimensions, maximum job count, and desired metrics.

Example forms:

```yaml
variables:
  controller.kp:
    values: [0.2, 0.4, 0.6]
  controller.ki:
    range:
      start: 0.01
      stop: 0.1
      count: 3
      scale: logarithmic
```

Expand first when you want to inspect the generated job matrix before submission.

## HIL safety policy YAML

The HIL policy can define:

- watchdog timeout,
- arm-token requirement,
- emergency-stop input,
- deadline-miss trip policy/count,
- output minimum/maximum,
- safe value,
- slew-rate limit.

Never bypass the policy in a real HIL adapter merely because a simulator path did not require it.

## Digital-twin files

The supplied examples show three important declarative inputs:

- signal mapping,
- uncertainty distribution definitions,
- requirement verification thresholds/evidence labels.

These files are intended to be version-controlled alongside the model because they define how evidence is interpreted.

## Touchstone and RF waveform data

### Touchstone

Embeddyn's built-in parser supports the common data required for S-parameter analysis and can operate without scikit-rf for the basic path. Preserve the reference impedance and units/header from measurement/export.

### Waveform CSV

Noise analysis needs a numeric value channel plus either:

- a numeric time column, or
- an explicit sample rate.

A useful CSV is:

```csv
time_s,switch_v
0.0000000,0.0
0.0000001,3.3
...
```

For trustworthy frequency interpretation, the sampling interval should be sufficiently uniform and the Nyquist limit must exceed the frequencies of interest.

## Provenance rules of thumb

For engineering traceability, capture:

1. repository commit/release,
2. dependency lock state,
3. project graph/YAML/spec modifications,
4. firmware hash,
5. simulator/tool versions,
6. runtime parameter overrides,
7. raw telemetry/measurement data,
8. analysis settings (filters, FFT length, impedance, RF target/mask),
9. generated report/evidence artifacts.
