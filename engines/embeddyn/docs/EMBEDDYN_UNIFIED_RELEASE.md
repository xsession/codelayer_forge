# Embeddyn Unified Release

This repository is the unified Embeddyn codebase containing the cumulative Phase 1-6 mechatronic platform work.

## Product identity

- Name: **Embeddyn**
- Python distribution: `embeddyn`
- Python package: `embeddyn`
- Primary CLI: `embeddyn`
- Runtime state root: `.embeddyn/`
- Environment prefix: `EMBEDDYN_`
- Compatibility CLI alias: `vsd`

## Unified capabilities

The release combines the versioned domain model, parameter provenance, content-addressed artifacts, scalable telemetry, deterministic and multi-rate co-simulation, convergence scheduling, checkpoints and replay, process-isolated adapters, Webots mechanical integration, SPICE electrical integration, KiCad integration, Renode firmware integration, reusable multi-fidelity components, distributed workers, parameter-sweep experiments, HIL safety controls, digital-twin synchronization, calibration, uncertainty analysis, requirements traceability, and engineering evidence generation.

## Migration compatibility

The primary public identity is Embeddyn. Compatibility aliases are intentionally retained for selected former `vsd` CLI/API/environment entry points so existing local projects can migrate incrementally. Upstream Antmicro Visual System Designer URLs and copyright/license notices remain unchanged where they refer to the original upstream project or resources.

## Verification for this package

- Python source compilation: passed
- Local + mechatronics test suite: 47 passed, 1 skipped
- Embeddyn CLI startup: passed
- Mechatronics project validation: passed
- Deterministic mock closed-loop simulation: passed, 501 steps
