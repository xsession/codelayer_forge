# C4 dynamic views

These sequence diagrams show important runtime interactions. They are deliberately more specific than C1/C2 but avoid method-by-method implementation detail.

## D1 — Start Local Studio and analyze firmware

```mermaid
sequenceDiagram
    actor User
    participant CLI as Embeddyn CLI
    participant Config as LocalConfig
    participant API as FastAPI Studio
    participant Store as LocalStore
    participant UI as Browser UI
    participant FW as FirmwareAnalyzer

    User->>CLI: embeddyn studio run
    CLI->>Config: resolve data/workspace/host/remote policy
    Config-->>CLI: validated config + optional token
    CLI->>API: create_app(config), start uvicorn
    API->>Store: initialize schema/import bundled catalog
    CLI-->>User: local URL (+ token only when remote mode)
    User->>UI: open Studio
    UI->>API: GET /api/health
    API-->>UI: safe health/tool state
    User->>UI: upload firmware
    UI->>API: POST /api/assets
    API->>Store: SHA-256 ingest + metadata
    Store-->>API: asset ID
    UI->>API: POST /api/firmware/analyze(asset_id)
    API->>Store: resolve stored asset
    API->>FW: analyze(path, architecture?)
    FW-->>API: structured report
    API-->>UI: JSON report
    UI-->>User: visual inspection
```

## D2 — Classic graph to Zephyr build

```mermaid
sequenceDiagram
    actor User
    participant CLI as Embeddyn CLI
    participant Spec as Specification
    participant Graph as Graph
    participant Build as Build generator
    participant West as west / Zephyr

    User->>CLI: prepare-zephyr-app graph.json ...
    CLI->>Spec: load components-specification.json
    opt spec modifications
        CLI->>Spec: modify(mod JSON)
    end
    CLI->>Graph: resolve graph against specification
    Graph-->>CLI: SoC + supported connections
    CLI->>Build: prepare generated board/app
    Build->>Build: render overlays/templates
    Build->>West: west build argv (no shell interpolation)
    West-->>Build: ELF/DTS/config/log
    Build-->>User: generated/build artifact paths
```

## D3 — Coupled mechatronics run

```mermaid
sequenceDiagram
    actor User
    participant CLI as Mechatronics CLI
    participant Model as MechatronicProject
    participant Compiler as ProjectCompiler
    participant Factory as Adapter Factory
    participant Runtime as Orchestrator/Scheduler
    participant FW as Firmware Adapter
    participant EE as Electrical Adapter
    participant ME as Mechanical Adapter
    participant Store as Run Store

    User->>CLI: mechatronics run project.yaml
    CLI->>Model: load + validate
    opt runtime parameter overrides
        CLI->>Model: apply_parameter_overrides(source=runtime-override)
    end
    CLI->>Compiler: compile validated project
    Compiler-->>CLI: compiled run/provenance
    CLI->>Factory: build adapters
    Factory-->>CLI: domain adapter map
    CLI->>Runtime: execute duration/scheduler
    Runtime->>FW: start(initial)
    Runtime->>EE: start(initial)
    Runtime->>ME: start(initial)
    loop macro steps / scheduled activations
        Runtime->>FW: step(t, dt, coupled inputs)
        FW-->>Runtime: outputs/diagnostics
        Runtime->>EE: step(t, dt, transformed inputs)
        EE-->>Runtime: outputs/diagnostics
        Runtime->>ME: step(t, dt, transformed inputs)
        ME-->>Runtime: outputs/diagnostics
        Runtime->>Store: telemetry/events/checkpoint metadata
    end
    Runtime->>FW: stop
    Runtime->>EE: stop
    Runtime->>ME: stop
    Runtime->>Store: finalize run/artifacts
    Store-->>User: run ID / output paths
```

## D4 — Distributed experiment sweep

```mermaid
sequenceDiagram
    actor User
    participant CLI as Submitter CLI
    participant Exp as Experiment Expander
    participant Coord as DistributedCoordinator
    participant DB as Coordinator DB
    participant Agent as WorkerAgent
    participant Run as mechatronics run subprocess

    User->>CLI: experiment-submit pid-sweep.yaml
    CLI->>Exp: load/expand variable matrix
    Exp-->>CLI: N JobSpecs with parameter_overrides
    CLI->>Coord: register experiment
    Coord->>DB: persist experiment
    loop jobs
        CLI->>Coord: submit job
        Coord->>DB: queued job
    end
    loop worker polling
        Agent->>Coord: heartbeat + claim matching job
        Coord->>DB: atomically claim
        Coord-->>Agent: job spec
        Agent->>Coord: mark running
        Agent->>Run: python -m embeddyn mechatronics run ... --parameter-overrides JSON
        loop while process runs
            Agent->>Coord: heartbeat / cancellation check
        end
        Run-->>Agent: exit status + output
        Agent->>Coord: complete/fail/cancel with result
        Coord->>DB: persist terminal state
    end
    User->>CLI: experiment-status ID
    CLI->>Coord: aggregate status
    Coord-->>User: counts/jobs/status
```

## D5 — HIL output safety

```mermaid
sequenceDiagram
    participant Runtime as Mechatronics Runtime
    participant Safety as HIL Safety Controller
    participant Device as HIL Device
    participant HW as Physical Plant

    Runtime->>Safety: request output(value, time)
    Safety->>Safety: verify armed/token/e-stop/watchdog/deadline
    Safety->>Safety: enforce bounds + slew rate
    alt safe and allowed
        Safety->>Device: write bounded output
        Device->>HW: physical I/O
    else fault/trip
        Safety->>Device: write declared safe value
        Device->>HW: safe output
        Safety-->>Runtime: safety event/tripped state
    end
    loop watchdog
        Runtime->>Safety: heartbeat
    end
```

Independent target/hardware safety is outside this software sequence and remains required.

## D6 — RF antenna tuning loop

```mermaid
sequenceDiagram
    actor User
    participant Studio as RF/EMC Cockpit
    participant RF as RF Core
    participant Generator as Patch/openEMS Generator
    participant OpenEMS as openEMS
    participant File as S1P/Far-field files

    User->>Studio: enter target + stack-up
    Studio->>RF: patch seed request
    RF-->>Studio: analytical geometry + warnings
    User->>Studio: generate full-wave model
    Studio->>Generator: validated RectangularPatchSpec
    Generator-->>User: standalone openEMS Python model
    User->>OpenEMS: execute model
    OpenEMS->>File: patch.s1p + summary/far-field
    User->>Studio: import S1P
    Studio->>RF: analyze_touchstone(target, threshold, Z0)
    RF-->>Studio: resonance, S11, VSWR, Z, bandwidth, tuning
    Studio-->>User: linked S11/Smith/construction view
    User->>Studio: apply resonant-length/feed/match adjustment
    Note over User,OpenEMS: Repeat until simulation is satisfactory, then validate prototype with VNA.
```

## D7 — RF generated-noise analysis from Studio telemetry

```mermaid
sequenceDiagram
    actor User
    participant UI as RF/EMC Cockpit
    participant API as Studio API
    participant Store as LocalStore
    participant RF as RF Analysis

    User->>UI: choose session/channel + FFT/mask settings
    UI->>API: POST /api/rf/noise/session
    API->>Store: query numeric telemetry points
    Store-->>API: timestamp/value samples
    API->>RF: waveform_from_points + analyze_waveform_noise
    RF->>RF: sampling/jitter checks + FFT + peaks + mask margins
    RF-->>API: structured report
    API-->>UI: spectrum/peaks/quality/margins
    UI-->>User: log spectrum + harmonic/mask markers
```

## D8 — Dependency sync versus update

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant Boot as bootstrap.py
    participant Manifest as embeddyn.yml
    participant Lock as embeddyn.lock.json
    participant Repo as Source repository
    participant Tree as Local dependency tree

    Dev->>Boot: sync --profile dev
    Boot->>Manifest: select projects/groups
    Boot->>Lock: read exact commit/fingerprint
    Boot->>Tree: check dirty/drift state
    Boot->>Repo: fetch exact locked object if needed
    Boot->>Tree: checkout/materialize locked state
    Note over Dev,Tree: Upstream moving does not change sync result.

    Dev->>Boot: update --profile dev
    Boot->>Manifest: read requested revision/ref
    Boot->>Tree: refuse unintended dirty tree
    Boot->>Repo: resolve/fetch requested ref
    Repo-->>Boot: new exact commit
    Boot->>Tree: update
    Boot->>Lock: write reviewed exact state
```
