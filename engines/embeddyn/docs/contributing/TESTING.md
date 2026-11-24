# Testing and validation

Embeddyn's test strategy must account for pure Python logic, browser UI, subprocess adapters, external simulators, and physical/HIL behavior. No single test layer can prove all of them.

## First-party suite

The repository's `pyproject.toml` scopes pytest to `tests/` so vendor project test suites under `externals/` are not accidentally collected.

Run:

```bash
pytest
```

During development, use a narrower target first:

```bash
pytest tests/local -q
pytest tests/mechatronics -q
pytest tests/rf -q
pytest tests/test_dependency_manager.py -q
```

## Test pyramid

### Level 1 — pure unit tests

Use for:

- parsers,
- validation,
- transforms/math,
- manifest/lock operations,
- path safety,
- FFT/network/patch math,
- digital-twin metrics,
- scheduler ordering.

These should be deterministic, fast, and independent of network/external tools.

### Level 2 — component/storage/API tests

Use temporary directories/databases for:

- LocalStore/library DB,
- FastAPI routes,
- asset ingest,
- telemetry persistence,
- coordinator/worker job state,
- run artifact storage,
- package resource presence.

Avoid sharing a developer's real Studio data directory.

### Level 3 — mocked process/adapter tests

Mock executable/process boundaries to verify:

- argument-vector construction,
- timeout behavior,
- exit-code propagation,
- cancellation,
- cleanup,
- stdout/stderr handling,
- capability/health behavior.

Do not fake shell quoting by asserting a pretty command string; assert the argument vector passed to the process API.

### Level 4 — end-to-end with built-in mocks

The DC motor `--mock` workflow is the baseline mechatronics E2E test. It exercises model loading, scheduler, couplings, orchestrator, storage, parameter overrides, and reporting without external simulator variance.

### Level 5 — external simulator integration

Use explicitly provisioned environments for:

- Renode,
- Zephyr/west,
- ngspice/LTspice,
- Webots,
- openEMS.

Pin tool versions where possible and report them with failures. These tests may be slower/optional and should not be disguised as unit tests.

### Level 6 — physical/HIL/lab validation

This is required for claims involving:

- real output safety timing,
- debugger/programmer hardware,
- physical plant dynamics,
- antenna performance,
- calibrated EMC/pre-compliance/compliance measurement.

Automated software tests cannot substitute for this layer.

## Static/syntax checks

Python:

```bash
python -m compileall -q embeddyn vsd
```

Studio JavaScript:

```bash
node --check embeddyn/local/static/app.js
```

Also verify package build/resource inclusion after changing packaged files.

## Studio UI tests

At minimum for a UI change:

1. run the API/unit contract tests,
2. run JS syntax check,
3. start Studio with a temporary data directory,
4. load representative project/telemetry/RF fixtures,
5. visually inspect desktop and narrower layout,
6. check browser console for errors,
7. verify stale-analysis/status semantics after editing inputs.

Prefer deterministic fixture data over screenshots that depend on external services.

## Database tests

For schema changes test:

- creation from an empty directory,
- use of an existing previous-version fixture/migration when migration support exists,
- idempotent initialization,
- constraints/cascades/index behavior relevant to the change,
- concurrent/short-lived connection assumptions where applicable.

## Dependency manager tests

Important invariants:

- `sync` stays on the lock even when upstream advances,
- `update` explicitly advances and rewrites lock,
- dirty Git trees are refused/protected,
- bundled tree fingerprints detect drift,
- manifest paths cannot escape the repository root,
- profile/group selection is deterministic.

## RF numerical tests

Use fixtures with analytically predictable behavior when possible:

- known S1P resonance,
- known impedance/reference behavior,
- synthesized sine/switching waveform with known tones,
- patch geometry formula regression,
- generated openEMS script parses/compiles as Python.

Do not make a unit test depend on the exact floating-point output of a native solver across versions unless that tolerance is physically and numerically justified.

## Distributed tests

Use a temporary coordinator database and short polling intervals. Cover:

- worker register/heartbeat,
- requirement matching,
- claim/start/complete/fail,
- cancellation,
- stale recovery,
- experiment expansion bounds,
- parameter override forwarding,
- output-root path containment.

## HIL safety tests

Test the controller as a state machine:

- unarmed output -> safe,
- arm requirements,
- limits/clamping or trip semantics as designed,
- watchdog expiration,
- e-stop,
- deadline misses,
- slew rate,
- reset/re-arm behavior.

A unit test passing does not certify the physical fail-safe chain.

## Documentation tests

Documentation is part of the interface. When behavior changes, verify:

- commands/path names still exist,
- relative links resolve,
- example snippets match the current schema,
- C4 diagrams reflect current boundaries.

The repository includes `tools/check_docs.py` to perform lightweight local link/required-document checks once added by this documentation set.

## Bug regression rule

Every fixed defect should get the smallest regression test that would have failed before the fix, unless the behavior can only be validated with unavailable physical equipment. For the latter, add the closest automated contract test and document the remaining physical validation requirement.
