# Contributor guide

Embeddyn is a multi-domain engineering platform. A good contribution preserves the boundary between declarative engineering data, orchestration, external tool adapters, local persistence, and UI presentation. This guide explains how to make changes without coupling subsystems unnecessarily.

## Before you change code

1. Read [Architecture](ARCHITECTURE.md) and the [C4 documentation](../c4/README.md).
2. Identify the subsystem that owns the behavior in [Code organization](CODE_ORGANIZATION.md).
3. Bootstrap the `dev` profile as described in [Development setup](DEVELOPMENT_SETUP.md).
4. Reproduce the issue/desired behavior with the smallest existing example or a new focused fixture.
5. Add/update tests at the lowest useful layer before or with the implementation.
6. Update user/C4 docs if the public behavior, deployment, data model, or architectural relationship changes.

## Repository expectations

### Keep first-party and external code separate

`externals/` contains bundled/synchronized external projects. Do not fix an Embeddyn issue by patching a vendor tree unless the change is intentionally maintained as a vendor fork and documented/locked accordingly. Prefer adapters or upstream contributions.

### Keep the project declarative

Graphs, YAML projects, binding manifests, HIL policies, and requirement files are data. Do not introduce arbitrary code execution to make configuration "more flexible". The mechatronics model intentionally uses typed transforms instead of arbitrary expressions.

### Preserve reproducibility

Dependency changes must flow through `embeddyn.yml` and `embeddyn.lock.json`. Normal sync reproduces the lock; explicit update advances it. Runtime parameter changes should appear in provenance.

### Preserve local-first behavior

Studio and analysis workflows should not require cloud access. New network behavior must be explicit, documented, and safe in offline mode.

### Distinguish simulation from measurement

Do not label inferred/mocked/pre-compliance data as physical validation. HIL, VNA, openEMS, regulatory EMC, and external simulator results have different evidence strength.

## Change checklist

Use this list for most pull requests:

- [ ] Correct subsystem/module selected.
- [ ] Public inputs validated.
- [ ] No new shell-string construction for untrusted values.
- [ ] No arbitrary evaluation of project/filter data.
- [ ] Paths constrained to intended roots when creating/executing artifacts.
- [ ] New persistent fields have defaults/migration strategy.
- [ ] Unit/provenance semantics are explicit for engineering values.
- [ ] Focused regression test added.
- [ ] First-party suite passes.
- [ ] Static syntax/compile checks pass.
- [ ] Studio UI visually checked if changed.
- [ ] External-tool behavior is mocked in unit tests and honestly marked if not integration-tested.
- [ ] User docs updated for user-visible behavior.
- [ ] C4 docs updated if containers/components/relationships/deployment changed.
- [ ] Dependency manifest/lock updated only when intended.

## Where to continue

- [Development setup](DEVELOPMENT_SETUP.md)
- [Architecture](ARCHITECTURE.md)
- [Code organization](CODE_ORGANIZATION.md)
- [Testing](TESTING.md)
- [Extension recipes](EXTENDING.md)
- [Data and migrations](DATA_AND_MIGRATIONS.md)
- [Security](SECURITY.md)
- [Release/dependency policy](RELEASE.md)
