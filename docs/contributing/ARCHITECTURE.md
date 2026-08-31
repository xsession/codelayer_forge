# Contributor architecture guide

This document explains how the code is partitioned and the architectural rules that should guide changes. For zoomed diagrams, see the [C4 documentation](../c4/README.md).

## Architectural style

Embeddyn is a **modular local-first monolith with external process/tool adapters and optional distributed workers**.

The Python package is intentionally not split into independent network microservices. Most subsystems share a local process and filesystem but expose explicit internal boundaries:

```text
CLI / Browser UI
      |
      +--> classic graph/build pipeline
      +--> Local Studio API/store/emulation
      +--> component library
      +--> mechatronics compiler/runtime/storage
      +--> RF analysis/openEMS integration
      |
      +--> external engineering tools/processes
```

Distributed execution is an optional extension of the mechatronics job model, not the default deployment architecture.

## Top-level layers

### 1. Entry points and orchestration

- `embeddyn.__main__` registers Typer command groups.
- Classic optional commands are imported conditionally so Studio/mechatronics/RF can operate without the complete original dependency set.
- `bootstrap.py` intentionally sits outside the installed package because it must create/synchronize the environment before package installation.

Rule: entry points should validate/translate CLI/API data and delegate to domain modules; they should not accumulate domain logic.

### 2. Declarative models

Examples:

- classic `Specification` and `Graph`,
- `MechatronicProject`, `Signal`, `Coupling`, scheduler config,
- HIL policy,
- distributed job/worker models,
- RF `RectangularPatchSpec`.

Rule: models own validation of structural/engineering invariants. Reject invalid units/ranges/paths/unsafe constructs as early as possible.

### 3. Domain services

Examples:

- build/generation,
- `LocalStore`, `FirmwareAnalyzer`, telemetry/filtering,
- `ProjectCompiler`, orchestrator, scheduler, checkpoint/replay,
- digital-twin analytics/calibration/traceability,
- RF Touchstone/waveform analysis and patch generation.

Rule: pure calculations should remain separable from I/O and UI so they can be tested deterministically.

### 4. Adapters/integrations

Examples:

- Renode, ngspice, LTspice, Webots,
- KiCad helpers,
- openEMS build/run integration,
- Pipeline Manager/Zephyr/west/Renode classic path.

Rule: external tool quirks belong in adapters. Core project models should not import tool-specific APIs just to represent engineering state.

### 5. Persistence/artifacts

Two distinct storage concerns exist:

- Local Studio: `LocalStore` + SQLite + SHA-256 blob store.
- Mechatronics: metadata DB + telemetry writers + content-addressed run artifacts.
- Aggregated library: `LibraryDatabase` + content-addressed media objects.

Rule: do not collapse these databases casually. They have different lifecycle/query/provenance requirements.

### 6. Presentation

Local Studio serves static HTML/CSS/JavaScript and talks to the FastAPI routes. The browser should not become the only place where analysis logic exists; reusable calculations belong in Python domain modules.

## Classic embedded build path

```text
components specification + optional spec modifications
                     |
                     v
                 Graph JSON
                     |
                 Graph model
                     |
                     v
        generated Zephyr board/overlay
                     |
        optional generated app template
                     |
                west build
                     |
       ELF/DTS/config/build log
                     |
               Renode assets
```

Security rule: process invocation must use argument vectors; shell-form commands are only for display/logging.

## Local Studio path

```text
browser static UI
       |
       v
FastAPI create_app(LocalConfig)
       |
       +--> LocalStore (SQLite + asset store)
       +--> FirmwareAnalyzer
       +--> EmulationManager --> external tools
       +--> TelemetryHub
       +--> RF analysis modules
```

`LocalConfig` enforces loopback by default and requires token-bearing remote mode. API token validation uses constant-time comparison.

## Mechatronics execution path

```text
YAML -> MechatronicProject.validate
              |
              v
        ProjectCompiler
              |
              v
        adapter factory
              |
         AdapterManager
              |
        scheduler strategy
              |
     CoSimulationOrchestrator
              |
  telemetry/events/checkpoints
              |
       persistent run store
```

The scheduler emits domain activations. The orchestrator applies couplings/transforms and advances adapters. Adapters expose health/capabilities/checkpoint support rather than the orchestrator assuming tool behavior.

## Distributed path

```text
experiment/job spec
       |
DistributedCoordinator (metadata DB)
       |
       +--> worker registration/heartbeat
       +--> queue/claim/cancel/status
                         |
                         v
                    WorkerAgent
                         |
              python -m embeddyn
              mechatronics run ...
                         |
                    run artifacts
```

The worker invokes the same local run command, which prevents distributed jobs from having a separate incompatible execution semantics.

## HIL path

HIL adds a safety controller and bounded device I/O around runtime signals. The safety controller must remain independent from arbitrary UI logic and should fail to declared safe values on fault conditions.

## Digital-twin path

Digital-twin modules consume model/run/measurement data and produce:

- state snapshots,
- aligned comparisons and metrics,
- calibration fits,
- uncertainty results,
- requirement pass/fail evidence.

This layer should be evidence/provenance driven. Avoid introducing hidden mutable global model calibration.

## RF/EMC path

```text
Touchstone ---------> parser/network analysis ----> S11/VSWR/Z/bandwidth/tuning

stack-up/target ----> patch model math ----------> openEMS Python model
                                                    |
                                                    v
                                             S1P/far field

waveform/session ---> uniform waveform model ----> FFT/peaks/mask margins
```

The UI combines these results visually but analysis semantics stay in Python. Full-wave generation validates numeric input and produces a trusted script from values rather than splicing arbitrary user code.

## Dependency architecture

```text
embeddyn.yml       human/update policy
     |
     | explicit update
     v
embeddyn.lock.json exact source commit/fingerprint
     |
     | sync/bootstrap
     v
workspace/externals + Python venv
```

Dependency groups are mapped to profiles. Recursive Git sources such as openEMS are lockable. Bundled trees can be fingerprinted even if distributed without `.git` metadata.

## Important architecture constraints

1. **No arbitrary eval** for configuration/filtering/couplings.
2. **No unbounded upload/import** paths in Studio.
3. **No implicit remote Studio exposure**.
4. **No implicit dependency advancement** during normal sync.
5. **No hidden parameter sweep overrides**; provenance is required.
6. **No assumption that every adapter supports checkpoint/real time/events**; query capabilities.
7. **No claim that FFT/full-wave/mock output is calibrated physical compliance evidence.**
8. **No recursive first-party pytest collection into vendor trees.**
9. **No user-specific UI calculation duplicated only in JavaScript when it is domain logic.**

## Architecture changes that require C4 updates

Update the C4 documentation when you add/remove:

- a user/external system relationship,
- a deployable/runtime container,
- a major persistent store,
- a new external simulator/tool class,
- a major internal subsystem/component boundary,
- a new distributed/HIL node role,
- a new protocol between containers/processes.
