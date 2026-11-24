# Release, packaging, and dependency policy

A release should be reproducible enough that another developer can identify the exact first-party source, source dependencies, Python dependencies, and validation level used to create it.

## Version sources

Current version-bearing locations include:

- `pyproject.toml` project version,
- bootstrap manifest `bootstrap_version`,
- dependency manifest/lock schema versions,
- API/schema versions where applicable.

When formalizing releases, keep product version and bootstrap/manifest format versions conceptually separate. A manifest parser format may remain stable across multiple product releases.

## Dependency update workflow

Normal development sync:

```bash
python3 bootstrap.py sync --profile dev
```

Intentional dependency advance:

```bash
python3 bootstrap.py update --profile dev
```

Then:

1. inspect `git diff embeddyn.lock.json`,
2. inspect upstream changelog/commits/licenses as appropriate,
3. run subsystem and full first-party tests,
4. run relevant external integration checks,
5. update docs if behavior/tool requirements changed,
6. commit manifest and lock changes together when both changed.

Do not edit exact lock commits casually by hand.

## Bundled external trees

A release archive may contain external trees without `.git` metadata. Their lock entries use tree SHA-256 fingerprints. Before packaging:

```bash
python3 bootstrap.py status
```

Unexpected fingerprint drift is a release blocker until explained/reviewed.

## Python lock

Use `bootstrap.py freeze` in a release environment when a frozen Python package list is part of the deliverable. Review platform-specific packages before treating one machine's freeze as universally portable.

## Package build

Build the Python wheel/sdist using the project build backend in a controlled environment. Verify the wheel contains runtime resources:

- `embeddyn/templates/*`,
- `embeddyn/spec_mods/*.json`,
- `embeddyn/local/static/*`,
- `embeddyn/local/assets/*`,
- all new runtime modules.

A packaging regression test should cover resource paths used through `importlib.resources`.

## Desktop/Studio packaging

`packaging/` contains Studio/desktop helpers. When changing package paths or compatibility names, run packaging smoke tests; do not rely on the source checkout masking missing wheel resources.

## Release validation matrix

Minimum software release checks:

| Area | Check |
|---|---|
| Python | `pytest`; `compileall`. |
| CLI | top-level and affected group `--help`; smoke commands. |
| Bootstrap | status/doctor; lock invariants. |
| Studio | API tests, JS syntax, visual smoke, package resources. |
| Mechatronics | mock E2E, storage/replay tests. |
| RF | S1P fixture, FFT fixture, patch generation syntax. |
| Package | build wheel and inspect contents/import from built artifact when feasible. |
| Docs | relative link checker and examples/path review. |

External validation is conditional on changed areas:

- Zephyr/west build,
- Renode integration,
- ngspice/LTspice,
- Webots,
- openEMS native FDTD,
- real HIL hardware,
- VNA/EMC instrumentation.

Release notes must state which of these were actually executed.

## Release archive

Before producing a source ZIP:

1. remove caches/build/test runtime state,
2. preserve intended bundled external trees,
3. include docs/examples/tests/source manifest and lock,
4. verify archive extraction/integrity,
5. calculate SHA-256,
6. smoke-test from the extracted archive rather than only the working directory.

## Compatibility

The `vsd` package/console alias exists for migration compatibility. Avoid removing it in a minor change without a deprecation plan. New docs/code should use Embeddyn naming.

## Documentation release rule

Every release should contain:

- current user guide,
- current contributor guide,
- C4 views matching the released architecture,
- specialist docs for changed subsystems,
- known validation gaps/limitations.

Architecture diagrams are not decorative: if they disagree with code, treat that as a documentation defect before release.
