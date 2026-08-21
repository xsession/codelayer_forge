# Embeddyn Unified Feature Set

Embeddyn combines all implemented Phase 1-6 capabilities into one engineering platform.

## Core modeling and reproducibility
- versioned simulator-independent project model
- unit-aware parameters and typed signals/events/buses
- declarative coupling transforms
- component definitions and instances
- parameter ownership, overrides, and provenance
- immutable compiled run plans, lock files, and manifests

## Storage and telemetry
- SQLite local metadata registry with migrations
- SHA-256 content-addressed artifact store
- Parquet/Arrow-oriented telemetry with streaming fallback
- event, bus, checkpoint, and run artifact registration

## Co-simulation runtime
- deterministic fixed-step and multi-rate scheduling
- iterative convergence coupling
- checkpoint/resume and replay
- isolated adapter workers
- real-time pacing, deadline monitoring, and HIL-oriented safety hooks

## Engineering integrations
- Renode firmware emulation
- Webots mechanical simulation bridge
- ngspice and LTspice electrical simulation adapters
- KiCad extraction, SPICE inspection, and plugin integration path
- reusable multi-fidelity mechatronic component catalog

## Distributed execution and HIL
- worker registry, heartbeat, and capability matching
- persistent job queue and cancellation
- parameter-sweep experiment expansion
- disarmed-by-default HIL safety gate
- output allowlists, clamping, slew limits, watchdogs, and emergency-stop handling

## Digital twin and engineering evidence
- measurement ingestion and state snapshots
- simulation-to-measurement alignment and metrics
- calibration fitting
- uncertainty and Monte Carlo sampling
- requirements traceability
- evidence report generation and artifact registration

The primary CLI is `embeddyn`; `vsd` is retained only as a compatibility alias during migration.
