# Embeddyn Deep Repository Review and Repair Report

**Review date:** 2026-08-26  
**Scope:** first-party Embeddyn Python/JavaScript code, packaging, Studio API/UI, component library, firmware analysis, mechatronics runtime, distributed execution, initialization/build tooling, and first-party tests.  
**Third-party boundary:** `externals/` contains large imported/vendor projects (Renode, OpenOCD, openFPGALoader, open_microchip_tools). These trees were deliberately not rewritten as part of this Embeddyn repair. Their accidental pytest collection was treated as an Embeddyn test-configuration defect.

## Executive summary

The repository had a healthy first-party baseline when tests were manually scoped (`47 passed, 1 skipped`), but a deep review found several defects that existing tests did not cover. The most important problems were:

- remote Studio mode did not consistently enforce its authentication boundary;
- an empty persisted token could silently disable remote authentication;
- the Zephyr build path constructed a shell command from project-derived paths;
- several post-rebrand resource/package references still pointed at nonexistent `vsd.*` packages;
- experiment parameter sweeps were recorded but not actually applied to simulations;
- event/bus telemetry could crash the numeric telemetry writer;
- distributed workers could strand jobs after a lost heartbeat and did not honor cancellation while a subprocess was running;
- valid UF2 images were misidentified and Intel HEX validation/range handling was incomplete;
- component FTS indexing could accumulate stale duplicate rows;
- persisted Studio graph data could inject malformed attribute/style content into the UI;
- default `pytest` recursively collected incomplete third-party trees and failed during test discovery.

All concrete first-party defects listed in the findings table below were repaired. Regression tests were added for the failures that previously had no coverage.

## Severity model

- **High** — security boundary violation, command execution risk, silent incorrect engineering results, or distributed/runtime failure capable of invalidating a run.
- **Medium** — meaningful correctness, reliability, packaging, persistence, or operability defect.
- **Low** — bounded robustness/developer-experience defect with limited direct impact.

## Findings and fixes

| ID | Severity | Area | Finding / impact | Repair | Status |
|---|---|---|---|---|---|
| EBD-001 | High | Studio security | Remote mode protected mutation endpoints but left multiple data-bearing GET endpoints readable without the bearer token. That exposed project/session/log/catalog/toolchain information remotely. | Added `require_token` to protected reads and made unauthenticated health responses minimal. | Fixed |
| EBD-002 | High | Studio security | A pre-existing empty `studio.token` file produced an empty API token, effectively turning authentication off in remote mode. | Empty/whitespace token files are regenerated atomically with a cryptographically random token; permissions are normalized to owner read/write where supported. | Fixed |
| EBD-003 | High | Studio security | Remote safety was enforced primarily in `from_env()`. A caller constructing `LocalConfig` directly could create non-loopback/remote configuration without the expected invariant or token. | Added dataclass post-init validation: non-loopback requires explicit remote opt-in and remote mode requires a non-empty token. | Fixed |
| EBD-004 | High | Build security | Zephyr build command construction used a shell string containing board/application/workspace-derived values. Special characters in names or paths could become shell syntax. | Build execution now uses an argument vector with `asyncio.create_subprocess_exec`; shell-escaped command text is retained only for display/logging. | Fixed |
| EBD-005 | High | Studio UI | Persisted graph node IDs and coordinates were interpolated into HTML attributes/CSS without normalization. A crafted/malformed saved graph could break markup/style and create a stored DOM-injection path. | Added graph normalization, numeric finite coordinate sanitization, referential filtering of connections, and HTML escaping of attribute values. | Fixed |
| EBD-006 | High | Mechatronics experiments | Experiment `parameter_overrides` were stored in job arguments but never passed through the worker CLI into the simulation. Parameter sweeps could therefore run identical simulations while appearing to vary parameters. | Added CLI override parsing/provenance, worker forwarding, model override application, and adapter parameter input propagation. Mock PID behavior now consumes the controller parameters so the bundled sweep is meaningful. | Fixed |
| EBD-007 | High | Runtime telemetry | The orchestrator sent event/bus/structured values to the numeric telemetry writer, whose scalar conversion could fail during otherwise valid mixed-domain simulations. | Numeric telemetry is now restricted to scalar continuous/discrete signals; event and bus records use their structured writers. | Fixed |
| EBD-008 | High | Distributed execution | Worker heartbeat expiry only marked a worker offline; its claimed/running jobs remained assigned and could be permanently stranded. | Stale-worker processing is transactional, resets worker capacity, requeues non-cancelled active jobs, and finalizes cancellation-requested jobs. | Fixed |
| EBD-009 | High | Distributed execution | `WorkerAgent` used blocking `subprocess.run`, so it could not heartbeat or honor job cancellation during a long-running simulation. | Switched to polled `Popen`, periodic heartbeat, cancellation checks, terminate/kill fallback, bounded captured output, and correct cancelled-job completion. | Fixed |
| EBD-010 | High | Initialization | `init_zephyr()` used a subprocess API without `check=True` while catching `CalledProcessError`; failures could therefore be ignored and initialization continue with a broken workspace. | Replaced with `subprocess.check_call` and explicit failure propagation. | Fixed |
| EBD-011 | Medium | Distributed security | Worker output path was formed from externally persisted `job_id` without verifying containment; a malicious/corrupt ID could escape the worker run root. | Resolve-and-containment check now rejects any output path outside the configured worker root. | Fixed |
| EBD-012 | Medium | Firmware / UF2 | UF2 format detection checked the wrong trailing magic representation, so standards-compliant UF2 files could be reported as raw binary. | Implemented standard UF2 start/end magic constants, 512-byte block validation, payload bounds, invalid-block/trailing-byte diagnostics. | Fixed |
| EBD-013 | Medium | Firmware / Intel HEX | Intel HEX records were not fully validated for exact length/checksum/special-record length and address ranges were merged in input order. Out-of-order valid records could create incorrect ranges. | Added strict record/checksum validation and sorted interval merge after parsing. | Fixed |
| EBD-014 | Medium | Firmware analysis | Binary compare allocated a list containing every changed byte offset, which scales poorly for large images; ELF symbol capping could continue scanning outer sections after the advertised cap. | Comparison now keeps only a changed-byte count and the ELF scan stops globally at the symbol limit. | Fixed |
| EBD-015 | Medium | Component library | FTS rows were appended on each upsert, leaving stale names/content and duplicate search hits after re-importing an entity. Existing databases retained the corruption. | FTS is rebuilt from canonical entities during initialization; upsert removes the entity's previous FTS row before inserting the current record. | Fixed |
| EBD-016 | Medium | Component library | Raw user search text was passed directly to FTS5. Punctuation/operator-like input could become malformed FTS syntax instead of a literal search. | Search terms are tokenized/quoted into a literal FTS expression; results are distinct and limits are bounded. | Fixed |
| EBD-017 | Medium | Asset store | Re-uploading identical bytes updated the metadata of the already content-addressed asset, so an old asset reference could unexpectedly change name/MIME. | Duplicate SHA inserts are immutable (`ON CONFLICT DO NOTHING`) and return the original record. | Fixed |
| EBD-018 | Medium | Upload handling | Component and binary uploads were effectively unbounded in the API, and successful component-library staging files accumulated indefinitely. Failed asset streams could also leave temp files. | Added 16 MiB component/512 MiB asset limits, extension/type validation, streamed writes, and guaranteed staging/temp cleanup. | Fixed |
| EBD-019 | Medium | Resource packaging | Core build/backend code still loaded `vsd.templates` / `vsd.spec_mods`, but those resource packages exist under `embeddyn`. Installed-package flows could fail at runtime. | Updated resource lookup to `embeddyn.templates` and `embeddyn.spec_mods`. | Fixed |
| EBD-020 | Medium | Packaging | Runtime templates/spec modifiers/Studio static and bundled asset data were not explicitly declared as package data, making wheel contents dependent on build behavior. | Added explicit setuptools package-data rules and verified the generated wheel contains all required resources. | Fixed |
| EBD-021 | Medium | Packaging | Studio CLI told users to install `.[studio]`, but no `studio` optional dependency group existed. | Added the documented Studio dependency extra plus a test extra. | Fixed |
| EBD-022 | Medium | Desktop packaging | PyInstaller helper still copied `vsd/local/static` and `vsd/local/assets`, paths that no longer match the repository. | Updated to `embeddyn/local/...` and added pre-build directory checks. | Fixed |
| EBD-023 | Medium | Test configuration | Plain `pytest` recursively collected imported/incomplete `externals/` projects, producing 34 collection errors before the Embeddyn suite could run. | Added pytest `testpaths = ["tests"]` and local `pythonpath`, isolating first-party tests by default. | Fixed |
| EBD-024 | Medium | Runtime model | Model validation accepted non-finite durations/steps/parameters, inconsistent scheduler macro steps, invalid ranges and malformed transform parameters. NaN/Inf can poison deterministic simulations silently. | Added finite/range/consistency validation, transform whitelist and parameter constraints, signal bound checks, and delay-kind validation. | Fixed |
| EBD-025 | Medium | Scheduler | A final partial macro step could schedule domain activations beyond the requested simulation end time. | Activation generation now uses bounded/floor-based counts and filters activations to the actual macro end. | Fixed |
| EBD-026 | Medium | Coupling runtime | A zero-delay bus coupling could attempt history lookup intended only for delayed scalar signals and raise `KeyError`. | Zero-delay coupling is handled before delayed-history access; delayed unsupported signal kinds receive an explicit error. | Fixed |
| EBD-027 | Medium | Runtime state | Snapshots retained mutable signal-value objects by reference, so later mutation could retroactively alter an earlier snapshot/checkpoint source. | Snapshot values are copied before storage/return. | Fixed |
| EBD-028 | Medium | Checkpoint restore | Restore accepted non-finite/out-of-run timestamps and unknown signal names, allowing incompatible/corrupt checkpoints to enter a run. | Restore validates time bounds/finite values and rejects unknown signal keys. | Fixed |
| EBD-029 | Medium | Distributed experiments | Experiment status was stored independently and could remain stale even after all jobs completed/failed/cancelled. | Status is derived from current jobs and terminal timestamps are persisted. | Fixed |
| EBD-030 | Medium | Artifact CAS | Content-addressed artifact writes used predictable shared temp names, creating collision/race and cleanup risks in concurrent runs. | Temp files now use unique UUID suffixes with cleanup in `finally` paths. | Fixed |
| EBD-031 | Medium | Bootstrap/download | Renode portable download used a shell pipeline (`curl | tar`) rather than checked argv calls, weakening error attribution and shell safety. | Replaced with checked `curl --fail ... --output` followed by checked `tar`, with temporary archive cleanup. | Fixed |
| EBD-032 | Low | Time handling | Several `timestamp or now` / truthiness checks treated legitimate epoch `0.0` as missing. The UI also rendered zero as no timestamp. | Replaced truthiness with explicit `None` checks in ingestion/store/parser/UI formatting. | Fixed |
| EBD-033 | Low | API robustness | Telemetry channel query used a mutable list default and the WebSocket endpoint did not reject an unknown session before subscribing. | Query default is `None`; WebSocket authenticates with constant-time compare and closes unknown sessions with 4404. | Fixed |
| EBD-034 | Low | Branding/migration | A first-party worker still invoked the legacy `python -m vsd` compatibility shim internally even though Embeddyn is now the primary identity. | Worker now invokes `python -m embeddyn`; the `vsd` module remains only as an intentional external compatibility shim. | Fixed |

## Detailed repair notes

### 1. Studio security boundary

Remote mode is now a real invariant rather than a CLI convention. `LocalConfig` rejects unsafe programmatic construction, empty token state self-repairs, bearer comparison uses `secrets.compare_digest`, and data-bearing endpoints require authorization. `/api/health` intentionally remains public for liveness checks but returns only coarse mode/authentication information until the caller authenticates.

This matters because Studio exposes project data and can start local emulation/custom command sessions. In remote mode, the bearer token is therefore an **administrative/RCE-equivalent secret** and must be treated accordingly.

### 2. Build and initialization safety

The Zephyr build path now keeps user/project-derived strings as argv elements all the way to process creation. A board or directory name containing spaces, semicolons, `$()`, etc. cannot be interpreted as shell syntax by Embeddyn's process launcher.

Initialization now also checks Zephyr/bootstrap subprocess status correctly. Renode portable retrieval was split into two checked non-shell processes so a download or extraction failure cannot be masked by pipeline behavior.

### 3. Firmware analysis correctness

UF2 recognition now follows the UF2 block specification instead of matching an incorrect byte suffix. Intel HEX input is treated as a record format rather than loose text: length, checksum, record-specific payload size, address extension and ordering are validated/normalized before ranges are emitted.

These changes are important because wrong format/range detection can propagate into firmware inspection, mapping, comparison and emulation decisions.

### 4. Mechatronics numerical correctness

Parameter overrides now follow this path:

`experiment -> distributed job.arguments -> WorkerAgent -> embeddyn mechatronics run --parameter-overrides -> MechatronicProject -> compiled manifest/provenance -> adapter inputs`

The bundled mock firmware adapter consumes `controller.kp` and `controller.ki`, so the supplied PID sweep no longer degenerates into repeated identical mock controller runs.

The runtime now separates scalar telemetry from event/bus records, validates finite physical/numerical configuration, avoids scheduler activations after end-of-run, validates checkpoint compatibility, and prevents mutable snapshot aliasing.

### 5. Distributed execution lifecycle

Long jobs now keep worker heartbeats alive and observe cancellation requests while executing. If a worker disappears, the coordinator atomically marks it offline, repairs `active_jobs`, and requeues work that can be retried. This prevents jobs from remaining in a permanent claimed/running state after worker loss.

### 6. Persistence and packaging

The component FTS index is repaired on DB initialization and kept one-row-per-entity during future upserts. Content-addressed binary metadata is now immutable for duplicate content. Package data has explicit build rules, and the wheel was inspected to confirm Studio JS/HTML/CSS, bundled components, the Renode overlay, templates and spec modifiers are present.

## Verification performed

### Baseline before fixes

- `python3 -m compileall -q embeddyn tests`: passed.
- Manually scoped first-party suite: **47 passed, 1 skipped**.
- Plain/unscoped `pytest`: **34 collection errors**, caused by recursive collection of incomplete imported external project trees.
- `node --check embeddyn/local/static/app.js`: passed.

### Final validation after fixes

The final first-party test suite result after all repairs is **72 passed, 1 skipped**.

The final validation run includes:

- `python3 -m compileall -q embeddyn vsd tests packaging`
- `node --check embeddyn/local/static/app.js`
- plain `pytest -q` using repository configuration
- packaging smoke build with `python -m pip wheel . --no-deps --no-build-isolation`
- wheel-content inspection for templates/spec modifiers/Studio static/assets
- resource import smoke checks through `importlib.resources`
- `python -m embeddyn --help` and mechatronics command registration smoke checks
- end-to-end supplied DC-motor mock co-simulation with CLI parameter overrides
- Python coverage run for the first-party suite

The end-to-end DC-motor run completed successfully with **501 telemetry rows/steps reported by the CLI**, 500 activations in each simulated domain, and a completed manifest containing `controller.kp` / `controller.ki` override provenance.

## Test additions

Regression coverage was added for:

- standards-compliant UF2 detection and malformed/out-of-order Intel HEX;
- content-addressed asset metadata and temp cleanup;
- epoch-zero telemetry/log timestamps;
- remote bind/token configuration invariants and protected GET endpoints;
- component FTS replacement/rebuild and punctuation-safe search;
- package resource paths and optional dependency declarations;
- scheduler end-boundary behavior;
- mixed event/bus/scalar telemetry;
- zero-delay bus coupling and snapshot isolation;
- parameter override effects/provenance and numerical validation;
- stale-worker requeue, worker parameter forwarding and experiment status derivation;
- Zephyr command argv/shell-boundary safety.

## Coverage / residual validation gaps

The measured first-party line coverage is approximately **51% overall**. Coverage is much stronger in the new mechatronics core than the aggregate number suggests, including approximately:

- orchestrator: 94%
- compiler: 93%
- artifact store: 92%
- model: 83%
- distributed coordinator: 82%
- local store: 83%
- Studio API: 72%

The largest remaining gaps are not hidden fixes; they are explicitly environment-dependent validation work:

1. **Real Renode/Webots/ngspice/LTspice integrations were not executed.** Their adapters need the corresponding external executables/models and, ideally, integration CI runners.
2. **Physical HIL was not exercised.** Mock HIL safety behavior is tested, but actual hardware transports and emergency-stop behavior need target hardware.
3. **Legacy Pipeline Manager/Zephyr workspace flows remain lightly unit-tested.** Their process boundaries were hardened and syntax/import-smoked, but full builds require a populated Zephyr/Embeddyn workspace.
4. **Third-party projects under `externals/` were not rewritten or certified by this review.** They should retain their own build/test pipelines. Embeddyn's default pytest configuration now intentionally excludes them.
5. **The Studio administrative token remains a high-value secret by design.** An authenticated remote caller can start emulation/custom commands; deployment should therefore use a trusted network boundary and protect the token from browser/log exposure.

## Recommended next hardening phase

These are follow-up improvements rather than unresolved defects from this repair batch:

- add CI jobs for a minimal real Renode co-simulation and headless Webots bridge;
- add a packaging CI job that builds both sdist and wheel in an isolated networked environment, then installs into a clean virtualenv and runs smoke tests;
- add browser-level Studio tests (Playwright) for project load/save, malformed persisted graphs, remote unlock, asset import, telemetry plots and session stop;
- add fault-injection tests that kill a distributed worker process mid-run and verify automatic job recovery end-to-end;
- gradually increase coverage of legacy `backend.py`, `build.py`, `init.py` and external adapters while keeping external vendor test suites separate.

## Files materially changed

Core repairs touch:

- `pyproject.toml`
- `packaging/build_desktop.py`
- `embeddyn/backend.py`
- `embeddyn/build.py`
- `embeddyn/init.py`
- `embeddyn/library/database.py`
- `embeddyn/local/api.py`
- `embeddyn/local/config.py`
- `embeddyn/local/firmware.py`
- `embeddyn/local/static/app.js`
- `embeddyn/local/store.py`
- `embeddyn/local/telemetry.py`
- `embeddyn/mechatronics/adapters/mock.py`
- `embeddyn/mechatronics/cli.py`
- `embeddyn/mechatronics/distributed/agent.py`
- `embeddyn/mechatronics/distributed/coordinator.py`
- `embeddyn/mechatronics/model.py`
- `embeddyn/mechatronics/orchestrator.py`
- `embeddyn/mechatronics/runtime/scheduler.py`
- `embeddyn/mechatronics/storage/artifacts.py`
- first-party regression tests under `tests/`

## Conclusion

The repaired repository is substantially safer and more deterministic than the uploaded baseline. The highest-risk defects were concentrated at trust/process boundaries (remote Studio and shell execution) and at engineering-result integrity boundaries (parameter sweeps, telemetry type separation, scheduling and distributed lifecycle). Those paths are now fixed and covered by targeted regression tests. The remaining work is primarily **integration validation with real external simulators/hardware and broader coverage of legacy upstream paths**, not known first-party correctness failures left unfixed by this review.
