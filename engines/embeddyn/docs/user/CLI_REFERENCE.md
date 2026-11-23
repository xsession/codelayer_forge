# Command-line reference

The canonical CLI entry point is:

```bash
embeddyn --help
```

`python -m embeddyn` is equivalent and is useful inside worker/subprocess environments. The historical `vsd` console command remains an alias for compatibility.

## Top-level command groups

| Command | Purpose |
|---|---|
| `embeddyn init` | Initialize the classic Embeddyn workspace. |
| `embeddyn info` | Report initialized workspace components. |
| `embeddyn update` | Update selected classic workspace components. |
| `embeddyn prepare-zephyr-app` | Generate a board/application from a graph and build it with Zephyr/west. |
| `embeddyn run` | Start the classic Pipeline Manager + Embeddyn backend when full optional dependencies are installed. |
| `embeddyn simulate` | Run the classic Renode simulation workflow when pyrenode dependencies are installed. |
| `embeddyn library ...` | Manage the aggregated local component/media/graph library. |
| `embeddyn studio ...` | Run Local Studio and local firmware/catalog tools. |
| `embeddyn mechatronics ...` | Compile/run/store/distribute/HIL/digital-twin workflows. |
| `embeddyn rf ...` | Antenna/network/noise/openEMS workflows. |

The classic `run`, `simulate`, and `prepare-zephyr-app` commands are registered only when their optional import dependencies are available. If they do not appear in `--help`, use the full bootstrap profile and inspect `bootstrap.py doctor`.

## Bootstrap manager

The bootstrap manager intentionally remains a repository script because it must work before Embeddyn itself is installed:

```bash
python3 bootstrap.py --help
```

| Command | Purpose |
|---|---|
| `bootstrap` | Create venv, install profile Python dependencies, synchronize sources; optional system/workspace setup. |
| `sync` | Reproduce exact locked source revisions/content. |
| `update` | Advance selected dependencies to manifest refs and rewrite lock state. |
| `status` | Compare worktrees with the lock and detect drift/dirty state. |
| `list` | List dependency projects/revisions. |
| `lock` | Freeze current source revisions/content. |
| `freeze` | Freeze sources plus installed Python versions. |
| `doctor` | Check host tools/dependency state. |
| `system-deps` | Show/install declared host packages where supported. |

## `embeddyn studio`

### `studio run`

Start the local FastAPI UI/API.

Common options:

- `--data-dir PATH` — local DB/content store.
- `--workspace PATH` — engineering workspace visible to Studio.
- `--host HOST` — defaults to `127.0.0.1`.
- `--port PORT` — defaults to `9010`.
- `--open-browser/--no-open-browser`.
- `--allow-remote` — required for non-loopback binding; enables token protection.

### `studio doctor`

Checks database/catalog/toolchain discovery.

```bash
embeddyn studio doctor --data-dir ./studio-data --workspace ./workspace
```

### `studio analyze`

```bash
embeddyn studio analyze FIRMWARE [--architecture ARCH] [--output FILE]
```

Supports ELF/HEX/UF2/raw analysis.

### `studio catalog`

```bash
embeddyn studio catalog [QUERY] [--kind KIND] [--bus BUS] [--limit N]
```

Searches the bundled device catalog.

## `embeddyn library`

| Command | Behavior |
|---|---|
| `library init` | Create library directories/config/database. |
| `library source-list` | Show expected source directories. |
| `library sync` | Preview source clone/update by default; `--apply` performs Git operations unless offline mode blocks it. |
| `library import` | Import VSD resources, hardware components, media, and graphs into the library DB/store. |
| `library validate` | Confirm required library files/database and print stats. |
| `library build` | Emit `generated/components-specification.json` from indexed entities. |
| `library search QUERY` | Search indexed entities. |

Use `--root` to select a non-default library location.

## `embeddyn mechatronics`

### Project lifecycle

| Command | Purpose |
|---|---|
| `compile PROJECT` | Validate/compile the project into run-ready metadata. |
| `validate PROJECT` | Validate project structure, units, scheduler, couplings, and referenced configuration. |
| `run PROJECT` | Execute co-simulation; `--mock` replaces configured domains with deterministic mock adapters. |
| `doctor` | Inspect simulator/integration availability. |
| `integration-validate PROJECT` | Validate configured external integration inputs. |
| `catalog-list` | List mechatronics component catalog entries. |

`run` supports runtime parameter overrides and adapter isolation. Use `embeddyn mechatronics run --help` for the current output-root/checkpoint/storage options.

### Run storage/replay

| Command | Purpose |
|---|---|
| `runs-list` | List stored runs. |
| `runs-inspect RUN_ID` | Inspect run metadata/artifacts. |
| `runs-export RUN_ID` | Export stored telemetry. |
| `artifacts-verify RUN_ID` | Verify content-addressed run artifacts. |
| `replay RUN_ID` | Replay/verify a stored run from recorded data. |

### KiCad/integration helpers

| Command | Purpose |
|---|---|
| `kicad-export` | Export project information for KiCad integration. |
| `kicad-plugin` | Print/generate the KiCad-side plugin helper as implemented. |
| `kicad-inspect` | Inspect supported KiCad project inputs. |

### Distributed execution

| Command | Purpose |
|---|---|
| `worker-register` | Register/update worker capabilities and labels. |
| `workers-list` | List known workers/health state. |
| `job-submit` | Submit a project job with requirements/arguments. |
| `jobs-list` | List queued/claimed/running/completed/failed/cancelled jobs. |
| `job-cancel JOB_ID` | Request cancellation. |
| `worker-run WORKER_ID` | Poll/claim/execute jobs; `--once` performs one iteration. |

Workers invoke the same `python -m embeddyn mechatronics run ...` path, preserving project semantics and parameter override handling.

### Experiments

| Command | Purpose |
|---|---|
| `experiment-expand FILE` | Expand variable ranges/value sets into deterministic job specifications. |
| `experiment-submit FILE` | Register experiment and enqueue all expanded jobs. |
| `experiment-status ID` | Summarize experiment/job states. |

The supplied `examples/mechatronics/experiments/pid-sweep.yaml` demonstrates explicit values and logarithmic ranges.

### HIL

```bash
embeddyn mechatronics hil-validate examples/mechatronics/hil/safe-motor.yaml
```

Validates watchdog, arm token, emergency stop, deadline handling, output bounds, safe values, and slew-rate limits.

### Digital twin / verification

| Command | Purpose |
|---|---|
| `twin-state` | Create a digital-twin state snapshot from project/run data. |
| `twin-compare` | Align simulated/measured data and calculate signal metrics. |
| `twin-calibrate` | Fit supported calibration transforms. |
| `uncertainty-run` | Sample declared parameter uncertainty and produce analysis results. |
| `requirements-verify` | Evaluate requirement thresholds against produced metrics. |
| `evidence-report` | Render verification evidence in Markdown. |

## `embeddyn rf`

### Backend status

```bash
embeddyn rf status
```

Reports availability of Python/network/full-wave capabilities.

### Touchstone

```bash
embeddyn rf touchstone antenna.s1p \
  --target-hz 2.45e9 \
  --return-loss-db 10 \
  --z0 50 \
  --output report.json
```

Computes resonance, S11/return loss, VSWR, impedance, accepted power, bandwidth, and first-order tuning guidance.

### Noise FFT

```bash
embeddyn rf noise waveform.csv \
  --time-column time \
  --value-column v_switch \
  --value-unit V \
  --impedance-ohms 50 \
  --max-fft-points 16384 \
  --top-peaks 20
```

If the CSV has no time column, supply `--sample-rate-hz`.

### Patch geometry

```bash
embeddyn rf patch-seed --target-hz 2.45e9 --epsilon-r 4.4 --substrate-mm 1.6
```

### openEMS script generation

```bash
embeddyn rf patch-openems-script patch.py \
  --target-hz 2.45e9 \
  --epsilon-r 4.4 \
  --substrate-mm 1.6 \
  --loss-tangent 0.02 \
  --z0 50
```

Optional geometry overrides include width, length, feed offset, sweep span, and sweep point count.

### Build/run openEMS

```bash
embeddyn rf openems-build --source externals/openEMS-Project --prefix .embeddyn/tools/openems --no-gui
embeddyn rf openems-run model.xml
```

The generated Python patch model is normally executed with the openEMS Python bindings; `openems-run` exists for trusted pre-generated native XML models.

## Discover exact options

The source and this guide describe behavior, but Typer help is the version-matched interface reference:

```bash
embeddyn COMMAND --help
embeddyn mechatronics COMMAND --help
embeddyn rf COMMAND --help
python3 bootstrap.py COMMAND --help
```
