# Embeddyn user guide

Embeddyn is a local-first engineering platform for designing and analyzing embedded systems across firmware, electrical, mechanical, observability, digital-twin, and RF/EMC domains. The same repository can be used as a lightweight firmware-analysis/Studio tool or as a full multi-simulator engineering workstation.

## What Embeddyn can do

Embeddyn currently provides six user-facing capability families:

1. **Embedded project design and Zephyr generation** — describe a hardware graph, resolve component specifications, generate board/application content, build with west, and prepare Renode simulation assets.
2. **Local Studio** — manage local projects and assets, search the bundled component catalog, inspect firmware, start emulation sessions, ingest/filter/plot telemetry, and use the RF/EMC cockpit.
3. **Component library** — maintain an offline searchable library assembled from Embeddyn resources, hardware-component metadata, media, graphs, and local overrides.
4. **Mechatronics co-simulation** — coordinate firmware, electrical, and mechanical simulators with deterministic or multi-rate scheduling and typed signal couplings.
5. **Distributed/HIL/digital twin** — queue parameter sweeps, run workers, enforce HIL output/watchdog policies, compare measurements with simulation, calibrate models, run uncertainty analysis, and produce requirement evidence.
6. **RF / EMC** — analyze Touchstone networks, create a first microstrip-patch geometry, generate an openEMS model, inspect S11/Smith/VSWR/impedance, and FFT waveforms for generated-noise/pre-compliance analysis.

## Choose an installation profile

| Profile | Intended use | Source groups | Python extras |
|---|---|---|---|
| `core` | Core project/build commands | core | base package only |
| `studio` | Local browser Studio and firmware analysis | core | `studio` |
| `rf` | Studio + RF/EMC workflow | core, rf-tools | `studio`, `rf` |
| `full` | Full engineering workstation | core, tools, rf-tools | `studio`, `mechatronics-storage`, `rf` |
| `dev` | Development and CI-like validation | core, tools, rf-tools | full features + `test` |

See [Installation](INSTALLATION.md) for bootstrap details and platform notes.

## Recommended learning path

### If you are evaluating Embeddyn

1. Install the `studio` profile.
2. Run `embeddyn studio doctor`.
3. Start `embeddyn studio run`.
4. Explore the component catalog and import a project/firmware asset.
5. Run the mock mechatronics example with `embeddyn mechatronics run examples/mechatronics/dc-motor.yaml --mock`.
6. If RF matters to your project, bootstrap the `rf` profile and use the provided Touchstone fixture.

### If you are building Zephyr systems

1. Bootstrap `full` with the workspace option.
2. Initialize or inspect the Embeddyn workspace with `embeddyn init` / `embeddyn info`.
3. Create or load a compatible design graph.
4. Use `embeddyn prepare-zephyr-app` for generated board/application output.
5. Use Renode integration for simulation where the target is supported.

### If you are building a multi-domain model

1. Start from `examples/mechatronics/dc-motor.yaml`.
2. Validate with `embeddyn mechatronics validate`.
3. Run with `--mock` to establish the signal/coupling model.
4. Replace mock adapters one domain at a time with Renode, ngspice/LTspice, or Webots.
5. Use run storage/replay before adding distributed execution or HIL.

## Core concepts

### Workspace

The **workspace** contains downloaded/generated engineering resources such as `embeddyn-resources`, Zephyr, SDK/tooling, generated boards/apps, and component-library material. Bootstrap state is tracked separately through the repository manifest and lock.

### Project graph

The classic embedded-design workflow uses a graph of components and connections. `embeddyn.graph.Graph` resolves nodes against the component specification and derives a SoC plus connected devices for code/board generation.

### Local Studio data directory

Studio stores local metadata and artifacts under its configured data directory. It contains a SQLite database plus content-addressed asset storage, exports, logs, and remote-access token material when remote mode is explicitly enabled.

### Mechatronics project

A mechatronics project is YAML describing domains, signals, couplings, simulator configuration, step/duration, scheduler behavior, parameters, and optional component definitions/instances.

### Run

A run is an immutable-ish execution record containing the compiled project, telemetry, artifacts, metadata, and provenance required for inspection/replay/evidence workflows.

### RF analysis

RF analysis is split into network/antenna analysis and time-domain noise analysis. Touchstone data may come from simulation or a VNA. FFT data may come from simulation/session telemetry or measurement, but Embeddyn labels non-calibrated waveform analysis as engineering/pre-compliance evidence rather than certified emissions measurement.

## Next documents

- [Installation](INSTALLATION.md)
- [Quick start](QUICKSTART.md)
- [Local Studio](STUDIO.md)
- [CLI reference](CLI_REFERENCE.md)
- [Projects and data](PROJECTS_AND_DATA.md)
- [Mechatronics](MECHATRONICS.md)
- [RF / EMC](RF_EMC.md)
- [Troubleshooting](TROUBLESHOOTING.md)
