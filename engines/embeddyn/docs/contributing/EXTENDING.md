# Extension recipes

This document gives concrete patterns for adding capabilities without breaking Embeddyn's architectural boundaries.

## Add a new top-level or subcommand

Embeddyn uses Typer.

### Subsystem command

Add the command to the subsystem's existing `Typer` app, for example `embeddyn/rf/cli.py` or `embeddyn/mechatronics/cli.py`:

```python
@rf_app.command("my-analysis")
def my_analysis(...):
    ...
```

Keep the CLI function thin:

1. validate/normalize user options,
2. call a domain function/class,
3. encode output,
4. translate known domain errors into `typer.BadParameter`/exit status.

Do not put reusable calculation logic in the CLI function.

### New command group

Create a module with a `typer.Typer` instance and register it in `embeddyn.__main__.py` with `app.add_typer(...)`. Avoid importing heavy optional libraries at module import time when the group should remain usable without them.

Tests should assert behavior and help/registration where relevant.

## Add a Local Studio API endpoint

1. Define a Pydantic request model in `embeddyn/local/api.py` or a dedicated module if the API grows large.
2. Add the route inside `create_app`.
3. Apply `Depends(require_token)` to data-bearing routes unless the route is deliberately public and exposes only safe limited information.
4. Delegate persistence to `LocalStore`, analysis to a domain module, and emulation to `EmulationManager`.
5. Bound uploads/collections and validate asset types/IDs.
6. Add an API regression test under `tests/local/` or the owning feature test directory.
7. Update `/api/docs` expectations/user docs when public.

Avoid accepting arbitrary executable strings or filesystem paths from the browser without explicit policy/path containment.

## Add a Studio UI capability

The current Studio UI is static HTML/CSS/JavaScript under `embeddyn/local/static`.

Guidelines:

- Put persistent/engineering calculations in Python when they are reusable or safety/semantic critical.
- Use JS for interaction, rendering, linked cursors, client-side presentation, and lightweight derivation from already validated API data.
- Keep DOM IDs unique and stable where tests/UI code depend on them.
- Reuse existing visual tokens/layout patterns before adding one-off styling.
- Show units next to engineering values.
- Distinguish unavailable, pending, stale, warning, fail, and pass states.
- Do not keep a green/result state after its underlying inputs are edited; mark stale and require recomputation.
- For heuristics, label them as heuristics.

Validation: syntax check, API/UI contract tests, browser console, representative fixture, desktop/narrow layout.

## Add a mechatronics simulator adapter

Implement `SimulatorAdapter` from `embeddyn/mechatronics/adapters/base.py`:

```python
class MyAdapter(SimulatorAdapter):
    name = "my-simulator"

    def prepare(self, context): ...
    def start(self, initial_signals): ...
    def step(self, time_seconds, step_seconds, inputs):
        return StepResult(outputs={...}, diagnostics={...})
    def stop(self): ...
```

Optional methods:

- `checkpoint` / `restore`,
- `health`,
- `capabilities`.

Then:

1. export/import it in `adapters/__init__.py`,
2. teach `factory.build_adapters` which backend string/config creates it,
3. add path/model/executable validation,
4. if process isolation is supported, make `ProcessAdapterProxy` construction serializable,
5. add a binding manifest mechanism if external signal names differ from Embeddyn signals,
6. add unit/process mock tests,
7. add an optional real integration test/guide.

### Adapter invariants

- `step` must not silently advance beyond the requested simulation time.
- Outputs must use stable declared signal semantics.
- On failure, stop/cleanup external processes/resources.
- Timeouts should be explicit.
- `capabilities` must be truthful; do not claim checkpoint support if restore is not implemented.
- Executable invocation uses argument arrays, not untrusted shell strings.

## Add a scheduler strategy

Implement `SchedulerStrategy.activations(macro_start, macro_end)` and return deterministic `ScheduledActivation` items. Add configuration validation in the project model and registration in `build_scheduler`.

Document ordering, determinism, step divisibility, and real-time semantics. Add tests for boundary floating-point cases.

## Add a signal transform

Transforms are intentionally typed. To add one:

1. extend `Transform.apply`,
2. extend project validation and parser mapping,
3. define unit behavior,
4. add tests for non-finite/boundary values,
5. document it in user project-format docs.

Do not reintroduce arbitrary expression evaluation.

## Add an aggregated library importer

Add a focused function to `embeddyn/library/importers.py` or a new importer module if complex.

Importer responsibilities:

1. walk only the intended source root,
2. validate/parse the source format,
3. produce stable entity IDs based on source + relative identity,
4. preserve source metadata/provenance,
5. ingest binary assets through content-addressed storage,
6. use upsert semantics for repeatable imports,
7. avoid fetching from the network inside the importer.

Wire it into `library import` and update default config/source listing only if it becomes a first-class source.

## Add a firmware format/architecture analyzer

Keep format detection separate from format-specific parsing. For a new format:

1. add a strict detector using file structure/magic, not only extension,
2. add a parser that bounds record lengths/offsets,
3. return normalized report fields,
4. reuse hash/entropy/string/security helpers where appropriate,
5. add malformed/truncated fixtures.

Do not execute uploaded firmware during static analysis.

## Add an RF/network calculation

Pure RF math belongs in `embeddyn/rf/analysis.py` or `models.py` depending on whether it analyzes input data or generates a model.

Rules:

- carry frequency in Hz internally,
- carry impedance in ohms,
- state dB convention and reference explicitly,
- reject non-finite/physically invalid inputs,
- distinguish numerical/engineering estimates from calibrated measurement,
- return structured JSON-serializable results for CLI/API/UI reuse.

Add deterministic fixtures and tolerances with physical meaning.

## Add a full-wave backend/model

Keep solver-specific launch/build logic in an adapter-style module like `rf/openems.py`. Model generation should use validated numeric/declarative data rather than user-supplied code snippets.

If adding a source dependency:

1. add it to `embeddyn.yml` with a group/profile,
2. pin/update to an intentional revision,
3. run explicit `bootstrap.py update`/lock workflow,
4. test sync/status semantics,
5. document native dependencies and validation level.

## Add a distributed job argument

The coordinator model, experiment expansion, WorkerAgent forwarding, and `mechatronics run` must all agree. Add tests that prove the argument survives submission -> claim -> worker subprocess -> run provenance.

Never add a job field that is persisted but silently ignored at execution.

## Add HIL output/device capability

Safety policy is the outer contract. A new device/output should:

- define safe state,
- obey min/max and slew restrictions,
- participate in watchdog/e-stop handling,
- fail safe on transport/process error,
- expose health explicitly.

Hardware-side independent safety remains required.

## Add digital-twin evidence

New metrics should be pure/testable, unit-aware, and tied to stable names consumed by requirement verification. If a metric depends on time alignment/filtering, include those assumptions in the result/evidence metadata.

## Update C4 when extending

If your extension creates a new external relationship, runtime process, store, worker role, or major component, update the matching C1/C2/C3/dynamic/deployment view. If it is just a new class inside an existing component, update C3 only if it materially changes responsibilities.
