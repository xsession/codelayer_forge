# C4 deployment view

Embeddyn is optimized for a local engineering workstation but supports distributed simulation workers and HIL/lab connections. These deployment views make the trust/performance boundaries explicit.

## DPL-1 — Standard local workstation

```mermaid
flowchart TB
    subgraph WS["Deployment Node: Engineer Workstation"]
        Browser["Browser\nLocal Studio UI"]
        Python["Python environment\nEmbeddyn CLI/API/mechatronics/RF"]
        StudioDB[("Local filesystem\nStudio SQLite + blobs")]
        RunDB[("Local filesystem\nRun DB/telemetry/artifacts")]
        Workspace[("Workspace/externals\nresources, Zephyr, solver sources")]

        subgraph Processes["External local processes"]
            Renode["Renode"]
            Spice["ngspice/LTspice"]
            Webots["Webots"]
            OpenEMS["openEMS"]
            West["west/toolchain"]
        end
    end

    Browser <-->|localhost HTTP/WebSocket| Python
    Python <--> StudioDB
    Python <--> RunDB
    Python <--> Workspace
    Python <-->|process/socket/file protocols| Processes
```

Recommended security posture: loopback Studio, local filesystem databases, exact dependency lock, external processes running with normal user privileges rather than administrator/root unless specifically required.

## DPL-2 — Remote browser over trusted tunnel

```mermaid
flowchart LR
    Laptop["Node: User device\nBrowser"]
    Tunnel["Trusted VPN / SSH tunnel"]
    Workstation["Node: Engineering workstation\nStudio API + tools + local stores"]

    Laptop <-->|HTTPS/VPN/SSH protected path| Tunnel
    Tunnel <-->|forwarded Studio port| Workstation
```

If binding Studio directly to a non-loopback interface, explicit remote mode and bearer token are required. A tunnel/private-network boundary is still recommended.

## DPL-3 — Distributed simulation farm

```mermaid
flowchart TB
    subgraph CoordNode["Node: Coordinator / Engineer Workstation"]
        CLI["Submitter CLI"]
        CoordDB[("Coordinator SQLite metadata DB")]
        Results[("Collected run artifacts / reports")]
    end

    subgraph W1["Node: Worker A"]
        Agent1["WorkerAgent"]
        Env1["Locked Embeddyn environment"]
        Tools1["Simulator/tool processes"]
        Out1[("Worker output root")]
    end

    subgraph W2["Node: Worker B"]
        Agent2["WorkerAgent"]
        Env2["Locked Embeddyn environment"]
        Tools2["Simulator/tool processes"]
        Out2[("Worker output root")]
    end

    CLI <--> CoordDB
    Agent1 <-->|heartbeat/claim/status| CoordDB
    Agent2 <-->|heartbeat/claim/status| CoordDB
    Agent1 --> Env1 --> Tools1
    Agent2 --> Env2 --> Tools2
    Env1 --> Out1
    Env2 --> Out2
    Out1 --> Results
    Out2 --> Results
```

### Current deployment caveat

The coordinator is SQLite-based. A single SQLite file is not a production distributed message broker. For multiple hosts, use an arrangement that provides safe access semantics or evolve the coordinator behind a network service/database. Do not put the file on an unreliable network share and assume atomic claim/locking semantics are preserved.

### Reproducibility requirement

Workers should use the same Embeddyn commit/release, dependency lock, project inputs, and solver versions unless the experiment deliberately studies version differences.

## DPL-4 — HIL workstation

```mermaid
flowchart LR
    subgraph Host["Node: HIL Host"]
        Runtime["Embeddyn Mechatronics Runtime"]
        Safety["HIL Safety Controller"]
        Adapter["HIL/Debugger Adapter"]
    end

    subgraph Bench["Node: Physical Test Bench"]
        HWGate["Independent hardware enable / watchdog / e-stop"]
        DUT["Controller/DUT"]
        Plant["Physical plant / sensors / actuators"]
    end

    Runtime --> Safety --> Adapter
    Adapter <-->|I/O/debug/telemetry| HWGate
    HWGate --> DUT
    DUT <--> Plant
```

The independent hardware gate is intentionally outside the Embeddyn software node. Host software cannot be the only safety layer.

## DPL-5 — RF/EMC lab loop

```mermaid
flowchart LR
    subgraph WS["Node: Engineering Workstation"]
        Studio["RF/EMC Cockpit"]
        RF["RF Analysis Core"]
        OpenEMS["openEMS full-wave process"]
        Files[("S1P / waveform / reports")]
    end

    subgraph Lab["Node: RF/EMC Lab"]
        DUT["Prototype / PCB / antenna"]
        VNA["VNA"]
        Scope["Oscilloscope / current/near-field probes"]
        EMI["Pre-compliance / spectrum / EMI receiver"]
    end

    Studio <--> RF
    RF <--> Files
    RF <--> OpenEMS
    DUT --> VNA --> Files
    DUT --> Scope --> Files
    DUT --> EMI --> Files
```

Simulation and measurement enter the same analysis environment through files/telemetry, but their provenance and calibration strength must remain distinguishable.

## Deployment data locations

| Data | Recommended location |
|---|---|
| Studio SQLite/blob store | local SSD/filesystem on Studio host. |
| Mechatronics telemetry/artifacts | local/high-throughput disk; copy/archive after run. |
| External solver scratch | local fast disk; often disposable after extracting results. |
| Coordinator DB | local to coordinator; avoid casual network filesystem sharing. |
| Dependency workspace | per worker/workstation, synchronized from same lock. |
| VNA/EMC raw files | immutable project/lab evidence store with calibration/setup metadata. |

## Network ports/protocols

Ports for external simulators are configuration-dependent (for example Renode/Webots bridge sockets). Keep them loopback/private by default. Do not expose simulator control ports publicly simply because Studio remote mode is enabled.
