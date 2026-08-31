# C3 — Component views

This document zooms into the major first-party containers. It is intentionally organized by subsystem so contributors can map diagram boxes directly to modules.

## C3-A — Local Studio API

```mermaid
flowchart LR
    UI["Container: Browser UI"]
    Tools["External tools/processes"]
    DB[("Container: Studio store")]

    subgraph API["Container: Local Studio API"]
        Routes["Component\nFastAPI route layer\napi.py"]
        Config["Component\nLocalConfig\nconfig.py"]
        Store["Component\nLocalStore\nstore.py"]
        Firmware["Component\nFirmwareAnalyzer\nfirmware.py"]
        Emu["Component\nEmulationManager\nemulation.py"]
        Telemetry["Component\nTelemetryHub\ntelemetry.py"]
        Filtering["Component\nFilter/plot pipeline\nfiltering.py"]
        RFBridge["Component\nRF service bridge\napi.py -> embeddyn.rf"]
    end

    UI <-->|HTTP/JSON, WebSocket| Routes
    Routes --> Config
    Routes --> Store
    Routes --> Firmware
    Routes --> Emu
    Routes --> Telemetry
    Routes --> Filtering
    Routes --> RFBridge
    Store <--> DB
    Telemetry --> Store
    Emu --> Store
    Emu --> Telemetry
    Emu <-->|subprocess/protocol| Tools
```

### Responsibilities

- `LocalConfig` enforces bind/token policy before server startup.
- Route request models validate JSON payloads.
- `LocalStore` owns schema/transactions/object paths.
- `FirmwareAnalyzer` is static/local and never executes the uploaded firmware.
- `EmulationManager` owns tool discovery/process sessions.
- `TelemetryHub` handles live fanout plus persistence integration.
- Filtering is restricted/structured; it is not arbitrary Python evaluation.
- RF route handling delegates calculation/model behavior to `embeddyn.rf`.

## C3-B — Classic graph/build/simulation core

```mermaid
flowchart TB
    CLI["Container: CLI"]
    Resources["External/resource data\ncomponents-specification.json"]
    Zephyr["External: Zephyr/west"]
    Renode["External: Renode"]
    Pipeline["External: Pipeline Manager"]

    subgraph Classic["Container: Classic Build/Simulation Core"]
        Init["Component\nWorkspace init/update\ninit.py"]
        Spec["Component\nSpecification\nspecification.py"]
        Graph["Component\nGraph/Node\ngraph.py"]
        Generator["Component\nTemplate generator\ngenerate.py"]
        Build["Component\nZephyr board/build\nbuild.py"]
        Backend["Component\nClassic backend/RPC\nbackend.py"]
        Sim["Component\nRenode simulation\nsimulate.py"]
        Env["Component\nEnvironment helpers\nenv.py"]
    end

    CLI --> Init
    CLI --> Build
    CLI --> Backend
    CLI --> Sim
    Init --> Env
    Init --> Resources
    Build --> Spec
    Build --> Graph
    Spec --> Resources
    Graph --> Spec
    Build --> Generator
    Build <-->|argument-vector west build| Zephyr
    Backend <-->|backend messages| Pipeline
    Sim <-->|pyrenode/emulation| Renode
    Sim --> Build
```

### Boundary rule

`Specification`/`Graph` are declarative model components. Zephyr and Renode details should not leak into them beyond information necessary to resolve component interfaces.

## C3-C — Component library

```mermaid
flowchart LR
    CLI["Container: CLI"]
    Sources["External/source directories\nVSD resources, hardware JSON, media, graphs"]
    DB[("Container: Library store")]

    subgraph Lib["Container: Component Library Service"]
        LibCLI["Component\nLibrary CLI\ncli.py"]
        Config["Component\nLibraryConfig\nconfig.py"]
        Importers["Component\nSource importers\nimporters.py"]
        Assets["Component\nAsset ingest\nassets.py"]
        Index["Component\nLibraryDatabase\ndatabase.py"]
        Builder["Component\nAggregate specification builder\ncli.py build"]
    end

    CLI --> LibCLI
    LibCLI --> Config
    LibCLI --> Importers
    LibCLI --> Builder
    Importers --> Sources
    Importers --> Index
    Importers --> Assets
    Assets --> DB
    Index <--> DB
    Builder --> Index
```

The importer layer should remain repeatable/idempotent and network-independent. Network synchronization is a separate explicit CLI operation.

## C3-D — Mechatronics runtime

```mermaid
flowchart TB
    CLI["Container: CLI / Worker"]
    Ext["External simulators\nRenode / SPICE / Webots"]
    Store[("Container: Run store")]

    subgraph M["Container: Mechatronics Runtime"]
        Model["Component\nProject model + validation\nmodel.py, quantities.py"]
        Compiler["Component\nProjectCompiler\ncompiler.py"]
        Factory["Component\nAdapter factory\nfactory.py"]
        Adapters["Component\nSimulator adapters\nadapters/*"]
        Manager["Component\nAdapterManager\nruntime/manager.py"]
        Scheduler["Component\nScheduler strategies\nruntime/scheduler.py"]
        Orchestrator["Component\nCoSimulationOrchestrator\norchestrator.py"]
        Events["Component\nEvents/checkpoints/replay\nruntime/*"]
        Bindings["Component\nBinding manifests\nbindings.py"]
        Storage["Component\nTelemetry/artifact/metadata storage\nstorage/*"]
    end

    CLI --> Model
    Model --> Compiler
    Compiler --> Factory
    Factory --> Adapters
    Adapters --> Manager
    Bindings --> Adapters
    Manager --> Orchestrator
    Scheduler --> Orchestrator
    Events --> Orchestrator
    Orchestrator --> Storage
    Storage <--> Store
    Adapters <-->|tool-specific files/sockets/processes| Ext
```

### Core runtime contract

The orchestrator operates on the common `SimulatorAdapter` contract and project signal model. External adapter behavior is expressed through capabilities/diagnostics rather than simulator-specific branches in the scheduler.

## C3-E — Distributed execution and experiments

```mermaid
flowchart LR
    Submitter["Container: CLI"]
    DB[("Container: Coordinator metadata store")]
    WorkerProc["Container: Worker Agent"]
    Run["Component/Process\nstandard mechatronics run"]

    subgraph Dist["Components: distributed package"]
        Exp["Experiment expansion\nexperiments.py"]
        Coord["DistributedCoordinator\ncoordinator.py"]
        Models["Job/worker models\nmodels.py"]
        Agent["WorkerAgent\nagent.py"]
    end

    Submitter --> Exp
    Exp --> Models
    Submitter --> Coord
    Coord <--> DB
    WorkerProc --> Agent
    Agent <--> Coord
    Agent -->|subprocess with validated arguments| Run
    Run -->|result/output paths| Agent
    Agent --> Coord
```

A critical invariant is that distributed workers execute the same local run entry point and forward parameter overrides; distributed mode must not diverge into a separate simulation semantics.

## C3-F — HIL and digital-twin components

```mermaid
flowchart TB
    Runtime["Component: Mechatronics Runtime"]
    Hardware["External: HIL hardware/plant"]
    Measurements["External/data: measured datasets"]
    Store[("Container: Run/evidence store")]

    subgraph HIL["Components: HIL"]
        Policy["HilSafetyPolicy\nhil/safety.py"]
        Controller["HilSafetyController\nhil/safety.py"]
        Device["HilDevice / bounded queue\nhil/devices.py"]
    end

    subgraph Twin["Components: Digital Twin"]
        State["State snapshot\ndigital_twin/state.py"]
        Analytics["Alignment + metrics\nanalytics.py"]
        Calibration["Calibration\ncalibration.py"]
        Uncertainty["Uncertainty\nuncertainty.py"]
        Trace["Requirements/evidence\ntraceability.py"]
    end

    Runtime --> Controller
    Policy --> Controller
    Controller --> Device
    Device <-->|bounded I/O| Hardware
    Runtime --> Store
    Measurements --> Analytics
    Store --> State
    Store --> Analytics
    Analytics --> Calibration
    Analytics --> Trace
    Calibration --> Store
    Uncertainty --> Store
    Trace --> Store
```

HIL safety and digital-twin evidence are adjacent but distinct: one protects physical interaction; the other interprets/validates model versus evidence.

## C3-G — RF/EMC core

```mermaid
flowchart LR
    CLI["Container: CLI"]
    Studio["Container: Studio API/UI"]
    Files["External/data\nTouchstone / CSV / session telemetry"]
    OpenEMS["External system\nopenEMS/CSXCAD"]

    subgraph RF["Container: RF/EMC Analysis Core"]
        Parser["Component\nTouchstone parser/network model\nanalysis.py"]
        Network["Component\nS11/VSWR/Z/bandwidth/tuning\nanalysis.py"]
        Waveform["Component\nWaveform loader/model\nanalysis.py"]
        FFT["Component\nFFT/peaks/masks\nanalysis.py"]
        Patch["Component\nPatch seed/geometry\nmodels.py"]
        Generator["Component\nopenEMS patch script generator\nmodels.py"]
        Runner["Component\nopenEMS build/XML runner\nopenems.py"]
        Caps["Component\nCapability discovery\nanalysis.py"]
    end

    CLI --> Parser
    CLI --> Waveform
    CLI --> Patch
    CLI --> Generator
    CLI --> Runner
    Studio --> Parser
    Studio --> Waveform
    Studio --> Patch
    Studio --> Generator
    Files --> Parser
    Files --> Waveform
    Parser --> Network
    Waveform --> FFT
    Patch --> Generator
    Generator --> OpenEMS
    Runner <--> OpenEMS
    OpenEMS -->|S1P/far-field| Files
```

The Studio cockpit is a presentation consumer of structured RF reports. The Python core remains the authoritative calculation layer.

## C3-H — Bootstrap/dependency manager

```mermaid
flowchart TB
    User["Person: Developer/User"]
    Manifest["Data\nembeddyn.yml"]
    Lock["Data\nembeddyn.lock.json"]
    Repos["External\nGit/package repositories"]
    FS["Container/data\nworkspace, externals, venv"]

    subgraph Boot["Container: Bootstrap Manager"]
        CLI["Component\nbootstrap argparse commands\nbootstrap.py"]
        ManifestParser["Component\nmanifest validation/selection\ndependency_manager.py"]
        Git["Component\nGit state/sync/update\ndependency_manager.py"]
        Fingerprint["Component\nbundled tree digest/lock"]
        PythonEnv["Component\nvenv/package installation"]
        Doctor["Component\nhost/system diagnostics"]
    end

    User --> CLI
    CLI --> ManifestParser
    Manifest --> ManifestParser
    ManifestParser --> Git
    Git <-->|fetch/checkout explicit refs| Repos
    Git --> Lock
    Fingerprint --> Lock
    Lock --> Git
    Git --> FS
    PythonEnv --> FS
    Doctor --> FS
```

The lock is an input to `sync` and an output of explicit update/lock operations. That direction is central to reproducibility.
