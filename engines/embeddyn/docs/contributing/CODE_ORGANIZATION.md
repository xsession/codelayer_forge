# Code organization

This is the practical ownership map for the repository.

## Root

| Path | Responsibility |
|---|---|
| `bootstrap.py` | West-like environment/source dependency manager. |
| `bootstrap.sh`, `bootstrap.ps1`, `bootstrap.cmd` | Platform launchers delegating to bootstrap logic. |
| `embeddyn.yml` | Dependency manifest, profiles, source groups, host package declarations. |
| `embeddyn.lock.json` | Frozen source revisions/tree fingerprints. |
| `pyproject.toml` | Python package metadata, entry points, extras, first-party pytest scope. |
| `README.md` | Project overview/entry points. |
| `CONTRIBUTING.md` | Git-hosting discoverable contributor pointer. |
| `docs/` | User, contributor, C4, specialist documentation. |
| `examples/` | Reusable mechatronics/RF examples. |
| `demo/` | Classic Zephyr/demo graph assets. |
| `tests/` | First-party tests only. |
| `externals/` | Vendor/forked external engineering projects. |

## `embeddyn/` core

| Module | Responsibility |
|---|---|
| `__main__.py` | Typer app composition; conditional classic commands. |
| `init.py` | Classic workspace/Zephyr/SDK/resources/Renode setup/update/info. |
| `env.py` | Workspace/environment setup helpers. |
| `specification.py` | Component specification parsing/modification/resolution. |
| `graph.py` | Classic system graph model/resolution. |
| `build.py` | Generated Zephyr board/app preparation and west build. |
| `generate.py` | Jinja-based application generation from connected components. |
| `backend.py` | Classic Pipeline Manager/backend integration. |
| `simulate.py` | Classic Renode preparation/callback/simulation path. |
| `dependency_manager.py` | Manifest/lock project status/sync/update/fingerprint primitives used by bootstrap. |
| `utils.py` | Small shared graph/Git helpers. |

## `embeddyn/local/`

| Module | Responsibility |
|---|---|
| `cli.py` | `embeddyn studio` commands. |
| `config.py` | Local data/workspace/bind/token policy. |
| `api.py` | FastAPI app, request schemas, routes, static mount. |
| `store.py` | Studio SQLite schema and content-addressed asset persistence. |
| `models.py` | Simple store/API records. |
| `firmware.py` | Static firmware parsing/inspection. |
| `emulation.py` | Tool discovery and session process management. |
| `telemetry.py` | Telemetry ingest/hub/live streaming helpers. |
| `filtering.py` | Restricted telemetry filtering/pipeline/plot preparation. |
| `static/index.html` | Browser UI structure. |
| `static/app.js` | Browser behavior/API interactions/plots/RF cockpit. |
| `static/styles.css` | Studio visual system/layout. |
| `assets/` | Bundled component catalog and supported local assets. |

Tests: `tests/local/` plus RF UI/API contract tests where the endpoint belongs to Studio.

## `embeddyn/library/`

| Module | Responsibility |
|---|---|
| `cli.py` | Local aggregated library commands. |
| `config.py` | Library path/offline configuration. |
| `database.py` | Searchable SQLite index/schema. |
| `assets.py` | Content-addressed media ingest. |
| `importers.py` | Source-format specific importers. |

Tests: `tests/test_library_database.py` and future focused library tests.

## `embeddyn/mechatronics/`

### Core model/orchestration

| Module | Responsibility |
|---|---|
| `model.py` | Domains/signals/transforms/couplings/simulator/scheduler/project parsing and validation. |
| `quantities.py` | Engineering quantity parsing. |
| `compiler.py` | Compile project to run-ready representation/provenance. |
| `factory.py` | Convert simulator config to concrete adapters/proxies. |
| `orchestrator.py` | Coupled time advancement and signal exchange. |
| `bindings.py` | External simulator signal binding manifests. |
| `catalog.py` | Mechatronics component descriptors/catalog. |
| `integration.py` | External integration validation. |
| `kicad.py` | KiCad bridge. |
| `cli.py` | All mechatronics command surfaces. |

### Adapters

`adapters/base.py` defines `SimulatorAdapter` and `StepResult`. Concrete adapters are in `adapters/{renode,ngspice,ltspice,webots,mock}.py`.

### Runtime

| Module | Responsibility |
|---|---|
| `runtime/scheduler.py` | deterministic/multirate/real-time activation strategies. |
| `runtime/manager.py` | adapter lifecycle/health/checkpoint aggregation. |
| `runtime/worker.py` | isolated adapter process proxy. |
| `runtime/events.py` | event queue/runtime event model. |
| `runtime/checkpoints.py` | checkpoint persistence/orchestration. |
| `runtime/replay.py` | stored-run replay verification. |

### Storage

| Module | Responsibility |
|---|---|
| `storage/database.py` | run metadata DB. |
| `storage/artifacts.py` | content-addressed artifacts. |
| `storage/telemetry.py` | structured telemetry write/read/export. |

### Distributed

| Module | Responsibility |
|---|---|
| `distributed/models.py` | worker/job models/status/capabilities. |
| `distributed/coordinator.py` | queue, worker heartbeat, claims, status, experiments. |
| `distributed/agent.py` | local worker execution loop/subprocess lifecycle. |
| `distributed/experiments.py` | variable expansion and experiment loading. |

### HIL

- `hil/devices.py`: HIL device abstraction/mock/bounded I/O queue.
- `hil/safety.py`: policy, limits, state, safety controller/events.

### Digital twin

- `digital_twin/state.py`: state snapshots.
- `analytics.py`: measurement reading/alignment/metrics.
- `calibration.py`: affine calibration.
- `uncertainty.py`: distribution sampling/uncertainty runs.
- `traceability.py`: requirement verification/evidence rendering.

Tests: `tests/mechatronics/` organized by feature phases and project behavior.

## `embeddyn/rf/`

| Module | Responsibility |
|---|---|
| `analysis.py` | Touchstone parsing/network calculations, waveform loading/FFT/noise analysis, capabilities. |
| `models.py` | patch specification/analytical seed/resolved geometry/openEMS script generation. |
| `openems.py` | safe native openEMS build/XML run wrappers. |
| `cli.py` | RF command surface. |

Tests: `tests/rf/` including UI/API contract coverage.

## Compatibility package

`vsd/` exists as a compatibility shim for the older console/module naming. New internal resource imports and code should use `embeddyn.*` unless compatibility specifically requires otherwise.

## Packaging

`packaging/` contains desktop/Studio packaging helpers and requirements material. Package data in `pyproject.toml` explicitly includes templates, spec modifications, Studio static files, and local assets. If you add runtime-loaded package resources, update package-data tests.

## Documentation ownership

- `docs/user/`: user-visible behavior and workflows.
- `docs/contributing/`: developer practices/contracts.
- `docs/c4/`: current architecture views.
- topic-specific existing docs: deep implementation/history/operations for that subsystem.

When moving a code module across a major boundary, update this file and C4 C3 views in the same change.
