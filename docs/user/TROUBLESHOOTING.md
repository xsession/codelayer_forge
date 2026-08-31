# Troubleshooting

Use this document as a symptom-oriented checklist. For complex failures, reduce the problem to the smallest subsystem before changing multiple dependencies or model assumptions at once.

## Bootstrap/dependency problems

### `bootstrap.py status` reports dirty project

Do not force-sync immediately. Determine whether the changes are intentional.

```bash
git -C PATH status
```

Commit/stash/export your work first. Dirty-tree protection exists to prevent dependency synchronization from destroying local changes.

### Bundled source fingerprint mismatch

A bundled external tree without Git metadata is verified by SHA-256 tree fingerprint. A mismatch means its content differs from the lock. Either restore the released content or intentionally re-lock after reviewing the changes.

### `sync` does not pick up a newer upstream commit

That is expected. `sync` reproduces the lock. Use explicit `update` to advance a manifest ref, then review the new lock and run tests.

### Command missing after bootstrap

Activate the generated environment and check the selected profile:

```bash
. ./.embeddyn/env.sh
python3 bootstrap.py doctor --profile dev
python -m embeddyn --help
```

Some classic commands are conditionally registered only when their Git-pinned optional packages import successfully.

## Studio problems

### Studio refuses `0.0.0.0`

Use explicit remote mode:

```bash
embeddyn studio run --host 0.0.0.0 --allow-remote
```

This is a safety feature. Remote mode requires a bearer token.

### API returns 401

In token mode send:

```text
Authorization: Bearer <Studio token>
```

Check `/api/health`; before authentication it intentionally reveals limited state.

### Browser UI loads but data does not

Check:

1. browser developer console/network requests,
2. `/api/health`,
3. `embeddyn studio doctor`,
4. permissions on the Studio data directory,
5. whether a stale token is cached in the client/session.

### Database locked/timeouts

Studio uses SQLite WAL with busy timeout and short-lived connections. Persistent locking usually indicates an external process holding the DB, a problematic network filesystem, or a long manual transaction. Keep the data directory on a local filesystem.

## Firmware analysis problems

### Raw binary architecture cannot be inferred

Supply `--architecture` explicitly and compare with linker/map/target information. Raw binaries contain far less metadata than ELF.

### HEX/UF2 result looks wrong

Confirm the file really is Intel HEX/UF2 and was not renamed. The analyzer validates record/container structure; malformed/truncated programming files should be regenerated from the build toolchain.

## Zephyr generation/build problems

### `west` or Zephyr environment unavailable

Use the full workspace bootstrap and activate its environment:

```bash
python3 bootstrap.py bootstrap --profile full --workspace
. ./.embeddyn/env.sh
embeddyn info
```

### Graph build says SoC/component unsupported

Check:

- component exists in the resolved specification,
- the graph has one supported SoC,
- interface names/types match the specification,
- the connected sensor/LED is supported by current generation code,
- any spec modification file was supplied in the same order used to create the graph.

The generation path warns about unsupported remaining connections rather than inventing code for them.

## Mechatronics problems

### Validation fails

Common causes:

- unknown signal in coupling,
- non-finite initial/min/max/parameter value,
- min > max,
- initial outside bounds,
- multi-rate substep does not divide macro step,
- unsupported transform/scheduler policy,
- identity-like coupling between incompatible declared units,
- delayed event/bus source where only continuous/discrete delay is supported.

Fix validation before debugging external simulators.

### Real external run fails but `--mock` works

This is useful isolation. Test the failing external model standalone, then check adapter executable/model paths and bindings. Replace only one mock domain at a time.

### Simulation diverges/oscillates

Reduce to deterministic fixed step, shorten duration, inspect signal units/gains and algebraic loops, then consider smaller substeps or convergence behavior. A smaller step does not fix a fundamentally wrong sign/unit.

### Worker never receives jobs

Compare worker capabilities/labels against job requirements, check heartbeat/stale state, and confirm both commands point at the intended coordinator database.

### Parameter sweep jobs look identical

Inspect job arguments and run parameter provenance. Expanded `parameter_overrides` should be forwarded to the normal run command. If the simulator model itself ignores those parameters, the Embeddyn job can be different while the external model response remains identical.

## HIL problems

### Output trips to safe value

Check the safety event reason: watchdog expiry, e-stop, out-of-bounds command, slew-rate violation, deadline miss, or arm state. Do not disable the policy to make the symptom disappear; fix the timing/configuration/hardware condition.

### Host safety policy is not enough

Correct. Real HIL needs independent hardware/target fail-safe mechanisms. Treat host policy as one layer.

## RF/EMC problems

### S11 resonance missing from sweep

Widen the sweep. Check Touchstone frequency units and reference impedance. For an openEMS patch model, verify dielectric constant, substrate units, geometry, port/feed placement, mesh, and boundary/air volume.

### Resonance is far below target

The effective resonant path is likely too long or effective dielectric loading is higher than expected. Confirm units first, then shorten/tune geometry and rerun full-wave analysis.

### Resonance is correct but S11 is poor

Tune feed/matching impedance rather than aggressively changing resonant length. Use the Smith chart to see whether the target point is mainly reactive or resistive.

### FFT has no high-frequency content

Check Nyquist. You cannot analyze 100 MHz content from a 50 MHz sample rate. Also check that simulation/measurement output was not pre-filtered/decimated.

### FFT shows many unexpected harmonics

Inspect waveform clipping/ringing and sampling artifacts first. Compare harmonic spacing to PWM/clock/switching fundamentals. Windowing/leakage and non-integer record length can spread energy around tones.

### Mask says fail but lab says pass (or vice versa)

An engineering mask applied to a node-voltage FFT is not automatically equivalent to a regulatory receiver measurement. Reconcile units, impedance, RBW/detector, transducer factors, LISN/probe/antenna transfer, distance, and test configuration.

## Tests fail by collecting external repositories

The repository config scopes first-party pytest collection to `tests/`. Run:

```bash
pytest
```

Do not recursively point pytest at `externals/` unless you intentionally want to test those separate projects with their own dependency requirements.

## Get a useful diagnostic snapshot

For a bug report, include relevant output from:

```bash
python --version
python3 bootstrap.py --version
python3 bootstrap.py status
python3 bootstrap.py doctor --profile dev
python -m embeddyn --help
embeddyn studio doctor
embeddyn mechatronics doctor
embeddyn rf status
```

Also include the smallest project/fixture that reproduces the issue, but remove secrets and proprietary firmware/design data before sharing publicly.
