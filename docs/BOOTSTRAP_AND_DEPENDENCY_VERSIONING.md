# Embeddyn bootstrap and dependency versioning

Embeddyn now ships with a zero-dependency bootstrap/dependency manager that uses a workflow intentionally similar to Zephyr's `west` workspace model.

## Goals

The bootstrap layer has four jobs:

1. create and populate the Python virtual environment;
2. acquire source dependencies and preserve exact revisions;
3. validate/install host prerequisites;
4. optionally initialize the full Zephyr + Zephyr SDK + Renode workspace.

The manager is designed to work both from a normal Git checkout and from a source ZIP such as the release archive. The ZIP contains large vendor trees without `.git` metadata, so those trees are fingerprinted rather than silently treated as unversioned files.

## Files

| File | Purpose |
| --- | --- |
| `bootstrap.py` | Cross-platform bootstrap and dependency manager. Uses only Python standard library. |
| `bootstrap.sh` | POSIX launcher. |
| `bootstrap.ps1` | PowerShell launcher. |
| `bootstrap.cmd` | Windows CMD launcher. |
| `embeddyn.yml` | Editable dependency manifest: remotes, allowed revisions, groups and profiles. It is JSON syntax, which is valid YAML 1.2, so `bootstrap.py` can parse it without first installing PyYAML. |
| `embeddyn.lock.json` | Frozen source-dependency state. Git dependencies store exact commits; source-archive dependencies store deterministic SHA-256 tree fingerprints. |
| `requirements.lock.txt` | Optional generated Python lock. Created by `freeze`; commit it when a Python environment has been qualified. |
| `.embeddyn/env.sh`, `.embeddyn/env.ps1`, `.embeddyn/env.cmd` | Generated activation/environment helpers. Runtime state; ignored by Git. |

## West-style command mapping

| Zephyr / west concept | Embeddyn command |
| --- | --- |
| materialize manifest revisions | `python bootstrap.py sync` |
| advance dependency revisions | `python bootstrap.py update` |
| list projects | `python bootstrap.py list` |
| check local changes / drift | `python bootstrap.py status` |
| frozen manifest | `python bootstrap.py lock` |
| freeze source + Python environment | `python bootstrap.py freeze` |
| environment diagnosis | `python bootstrap.py doctor` |

The important behavior is that **`sync` never follows a moving branch after a project has been locked**. It uses the exact commit in `embeddyn.lock.json`. `update` is the explicit operation that resolves the manifest ref again and writes the new exact commit into the lock.

## Profiles

The manifest currently defines:

- `core`: Embeddyn core + versioned design resources.
- `studio`: core plus Local Studio Python dependencies.
- `rf`: Studio + scikit-rf plus the recursively versioned openEMS full-wave source tree.
- `full`: Studio, RF, mechatronics storage and external engineering source trees.
- `dev`: full plus test dependencies.

Examples:

```bash
python bootstrap.py bootstrap --profile studio
python bootstrap.py bootstrap --profile rf
python bootstrap.py bootstrap --profile full
python bootstrap.py bootstrap --profile dev
```

## Full first-time setup

### Debian / Ubuntu / WSL

For a fully automated host-package installation plus Python/source setup:

```bash
python3 bootstrap.py bootstrap --profile full --install-system
```

To also initialize the Zephyr workspace, SDK and portable Renode runtime:

```bash
python3 bootstrap.py bootstrap --profile full --install-system --workspace
. ./.embeddyn/env.sh
```

If system packages are managed outside the project, omit `--install-system`. The script reports missing commands and prints the Debian/Ubuntu install command.

### Windows native

Python/source dependency synchronization and Local Studio setup are supported by the PowerShell/CMD launchers:

```powershell
.\bootstrap.ps1 bootstrap --profile studio
.\.embeddyn\env.ps1
```

The existing full Zephyr SDK initialization path is Linux-oriented. For the full firmware workspace on Windows, use WSL until a native Zephyr SDK backend is added to `embeddyn init`.

## Dependency synchronization

Normal deterministic synchronization:

```bash
python bootstrap.py sync --profile full
```

Synchronize only selected projects:

```bash
python bootstrap.py sync openocd openFPGALoader
```

The current lock is authoritative. If upstream `main`/`HEAD` changes, this command keeps the already-qualified commit.

## Updating dependencies

Advance all dependencies selected by the profile:

```bash
python bootstrap.py update --profile full
```

Advance one dependency:

```bash
python bootstrap.py update openocd
```

Review the source changes and the lock diff before committing them.

For a normal Git checkout, dependencies declared as Git submodules are initialized from the superproject gitlink. After an explicit `update`, the submodule checkout can intentionally differ from the old gitlink. Commit both the changed submodule pointer and `embeddyn.lock.json` after qualification.

## Source ZIP / bundled external trees

The release ZIP contains `externals/*` without Git metadata. The shipped lock therefore records a SHA-256 fingerprint for each bundled tree. `status` and `sync` detect accidental edits to those trees.

```bash
python bootstrap.py status --profile full
```

If you want to replace a bundled archive tree with a live Git checkout so that it can be advanced, use:

```bash
python bootstrap.py update openocd --adopt
```

By default the old tree is preserved as `openocd.bundled-backup`. Add `--discard-bundled` only when that backup is not needed.

## Dirty-tree protection

Managed Git dependencies are never reset over local modifications during normal operation. `sync`/`update` fail if a dependency has tracked or untracked changes. `--force` exists for deliberate recovery, but it should not be used in CI or routine updates.

## Python dependency locking

`pyproject.toml` remains the declaration of Python dependency ranges and already pins the critical VCS dependencies to exact Git commits. To freeze the complete resolved Python environment after qualification:

```bash
python bootstrap.py bootstrap --profile dev
python bootstrap.py freeze --profile dev
```

This writes:

- `embeddyn.lock.json` for source repositories;
- `requirements.lock.txt` for installed Python packages.

Commit both lock files. Reproducible/CI setup can then require the Python lock:

```bash
python bootstrap.py bootstrap --profile dev --locked
```

`--locked` fails instead of silently resolving fresh PyPI versions when `requirements.lock.txt` is absent.

## Status and diagnostics

```bash
python bootstrap.py list --profile full
python bootstrap.py status --profile full
python bootstrap.py doctor --profile full
```

Typical states are:

- `locked`: working tree/fingerprint matches the lock;
- `unlocked`: dependency exists but no lock entry exists yet;
- `dirty`: Git worktree contains local modifications;
- `drift`: current revision/content differs from the lock;
- `missing`: dependency has not been materialized;
- `bundled`: source-archive tree accepted and fingerprinted during synchronization.

CI should treat `dirty`, `drift`, and `missing` as errors unless it is intentionally validating a partial profile.

## Updating Embeddyn resources

`embeddyn init` and `embeddyn update resources` now participate in the same source lock when executed from a source checkout:

- `embeddyn init` uses the locked `embeddyn-resources` revision when one exists;
- `embeddyn update resources` explicitly advances the manifest ref and updates `embeddyn.lock.json`;
- Zephyr is then initialized/updated from the `zephyr-data/zephyr.version` file in that locked resources revision.

This removes the old behavior where a routine resource acquisition could silently consume a different `main` revision on different machines.

## Manifest policy

For release-quality changes:

1. edit the allowed revision/remote in `embeddyn.yml` if needed;
2. run `bootstrap.py update <project>`;
3. run the relevant build/tests/integration checks;
4. run `bootstrap.py freeze` in the qualified Python environment;
5. commit the dependency pointer changes and both lock files together.

That makes dependency movement explicit, reviewable and reproducible rather than an implicit side effect of setup.


## RF/full-wave dependency policy

The `rf` profile adds the optional `scikit-rf` Python extra and selects `openems-project` from `embeddyn.yml`. openEMS is a recursive Git project because the upstream workspace contains solver/geometry-library submodules. Embeddyn synchronizes those nested submodules after checking out the manifest/lock revision. The manifest currently follows the stable `v0.0.36` tag and the repository lock freezes it to commit `d0d2e8dad8a02388f1919bbcdd29a67e9199dd2c`. Normal sync reproduces that exact checkout; only explicit update advances it.

```bash
python bootstrap.py sync --profile rf
python bootstrap.py status --profile rf
```

The bootstrap controls the openEMS **source revision**. After syncing the RF profile, Embeddyn can invoke the pinned upstream build driver locally:

```bash
embeddyn rf openems-build --no-gui
```

The default prefix is `.embeddyn/tools/openems`; source/editable installs discover that prefix automatically. The upstream native build still requires the platform compiler/library prerequisites documented by openEMS. `embeddyn rf openems-run` remains available for pre-generated XML jobs. See `docs/RF_EMC_PERSPECTIVE.md`.
