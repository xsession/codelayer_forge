# Architectural decisions and boundaries

This document records the main architectural choices visible in the current code. It is not a formal ADR history; it explains the constraints contributors should preserve unless a deliberate architecture change replaces them.

## A1 — Local-first modular monolith

**Decision:** Keep most first-party capabilities in one Python package/process space with explicit modules rather than decomposing into network microservices.

**Why:** Engineering workstations benefit from simple offline installation, low-latency access to local files/tools, and easy scripting. The primary scaling bottleneck is usually external simulators/hardware, not HTTP service throughput.

**Consequence:** Module boundaries and tests matter because process boundaries do not enforce them automatically.

## A2 — External solvers remain external systems

**Decision:** Renode, SPICE, Webots, openEMS, Zephyr, KiCad, and programmer/debugger tools are adapters/integrations even when their source is bundled.

**Why:** They have independent lifecycle, configuration, licenses, semantics, and failure modes.

**Consequence:** Core project models must not become solver-specific; capability discovery and adapters absorb differences.

## A3 — Declarative project data, no arbitrary expressions

**Decision:** Use typed signal transforms, structured filters, validated model specs, and generated scripts from numeric data.

**Why:** Reproducibility, safety, static validation, and the ability to inspect/project data without executing it.

**Consequence:** New flexibility should be added as a typed operation/schema, not `eval`/arbitrary Python snippets.

## A4 — Normal dependency synchronization is frozen

**Decision:** `sync` follows `embeddyn.lock.json`; only explicit `update` advances dependencies.

**Why:** A working embedded/simulator toolchain should not change just because upstream `main` moved.

**Consequence:** Manifest and lock have different roles: allowed/update intent versus exact reproducible state.

## A5 — SQLite is the local persistence default

**Decision:** Use SQLite plus content-addressed filesystem storage for local user/run/library metadata.

**Why:** Zero-service local deployment, transactional metadata, inspectability, adequate performance for local engineering workflows.

**Consequence:** Large multi-host/multi-tenant coordination may require a future service/database boundary rather than stretching SQLite over unreliable network filesystems.

## A6 — Content-addressed binary artifacts

**Decision:** Store blobs/artifacts by SHA-256 with separate logical metadata.

**Why:** Deduplication, integrity, immutable identity, easier artifact verification.

**Consequence:** Blob bytes must never be mutated in place for an existing hash.

## A7 — Same execution path locally and on workers

**Decision:** `WorkerAgent` invokes `python -m embeddyn mechatronics run` rather than reimplementing run semantics.

**Why:** Prevent local/distributed behavior drift and preserve parameter/provenance handling.

**Consequence:** Worker-specific needs should be expressed as job requirements/arguments or execution isolation, not a forked engine.

## A8 — Safety is layered

**Decision:** HIL host safety policy is explicit, but physical hardware safety remains outside/under it.

**Why:** Host Python/process/network failures can occur.

**Consequence:** Never document host software as the sole emergency protection for dangerous actuators/energy systems.

## A9 — Studio is local by default

**Decision:** Loopback bind is default; non-loopback requires explicit remote mode and bearer token.

**Why:** Studio has access to local artifacts/processes and is not designed as a public multi-tenant SaaS server.

**Consequence:** New endpoints inherit authentication unless there is a clear reason not to; remote deployments should add trusted network/tunnel controls.

## A10 — UI visualizes, Python owns engineering semantics

**Decision:** The Studio browser renders construction/plots/interactions, while reusable RF/firmware/filter/storage semantics live in Python.

**Why:** CLI/API/UI should agree, numerical logic should be testable, and UI refactors should not change physics.

**Consequence:** JavaScript may compute display geometry/cursors, but authoritative engineering metrics should not exist only client-side.

## A11 — Stale analysis must be visible

**Decision:** When analysis assumptions/inputs change, old results are marked stale rather than continuing to look current.

**Why:** Polished engineering dashboards can be dangerously persuasive if state provenance is unclear.

**Consequence:** New analysis panels should track the inputs that determine validity.

## A12 — Pre-compliance is not compliance

**Decision:** RF waveform FFTs, heuristics, mocks, and models are labeled according to evidence level.

**Why:** Regulatory and physical measurements depend on calibrated acquisition/detector/site methods that cannot be inferred from arbitrary simulation data.

**Consequence:** New reports should include assumptions/units/limitations and avoid certification language unless actual validated test data supports it.

## Architecture change procedure

If a future change intentionally reverses one of these decisions:

1. state the new problem/quality requirement,
2. document alternatives and migration impact,
3. update C1/C2/C3/dynamic/deployment views,
4. update security/data/release docs,
5. add compatibility/migration tests,
6. record the decision in a dedicated ADR if it materially affects future contributors.
