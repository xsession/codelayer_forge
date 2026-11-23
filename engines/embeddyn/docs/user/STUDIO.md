# Local Studio user guide

Local Studio is Embeddyn's local browser application for component discovery, project/asset management, firmware inspection, emulation sessions, telemetry/observability, and RF/EMC analysis. The browser UI is served by the FastAPI application in `embeddyn.local.api`; persistent state is stored locally through `LocalStore`.

## Start Studio

```bash
embeddyn studio run
```

Useful options:

```bash
embeddyn studio run \
  --data-dir ./my-studio-data \
  --workspace ./workspace \
  --host 127.0.0.1 \
  --port 9010 \
  --no-open-browser
```

Run a preflight check with:

```bash
embeddyn studio doctor
```

`doctor` reports the selected data directory/workspace, database path, catalog import statistics, and discovered local toolchain capabilities.

## UI mental model

Think of Studio as four layers:

1. **Construction/design data** — projects and the component catalog describe what the system is.
2. **Artifacts** — firmware, model, data, and RF files are immutable-ish content-addressed inputs.
3. **Sessions** — a session represents a running or completed emulation/telemetry source.
4. **Analysis/perspectives** — firmware analysis, plots/filters, and RF/EMC turn stored inputs into interpretable engineering evidence.

A useful discipline is to keep project topology separate from generated results. Reuse the same project while storing multiple firmware assets/sessions/runs so comparisons remain traceable.

## Component catalog

The Studio automatically imports its bundled component CSV into the local store. Search supports text plus structured filters such as kind, bus, and tier.

CLI equivalent:

```bash
embeddyn studio catalog STM32 --bus SPI --limit 50
```

The catalog is intentionally useful without network access. For a larger aggregated engineering library, see the top-level `embeddyn library` commands in [Projects and data](PROJECTS_AND_DATA.md).

## Project management

Projects stored by Local Studio contain:

- an ID,
- a human-readable name,
- graph JSON,
- created/updated timestamps.

The UI and API can list, create/update, inspect, and delete projects. The graph is persisted as JSON rather than executable code. Persisted coordinates and graph attributes are treated as data and sanitized before visual use.

Recommended workflow:

1. Create/import the structural graph first.
2. Associate firmware/model assets through sessions rather than embedding large binaries in the graph.
3. Use stable project names and asset names that describe board/revision/configuration.
4. Use separate sessions for materially different firmware or simulator configurations.

## Asset storage

Uploaded assets are stored content-addressed by SHA-256 under the Studio data directory. The SQLite database maps the logical asset record to the stored blob. This avoids silently keeping multiple physical copies of identical data.

Component-library imports are bounded and validated. Firmware/RF assets should still be treated as untrusted input: Studio parses them locally and does not need to upload them to a cloud service.

## Firmware analysis

CLI form:

```bash
embeddyn studio analyze firmware.elf
embeddyn studio analyze firmware.hex --architecture arm
embeddyn studio analyze firmware.uf2 --output analysis.json
```

The analyzer can identify or inspect ELF, Intel HEX, UF2, and raw binary content. Depending on file type and installed optional libraries, results may include:

- file format and size,
- hashes/entropy,
- architecture inference,
- section/segment information,
- strings,
- vector-table candidates,
- disassembly samples,
- security-oriented pattern findings.

Firmware analysis is static inspection, not proof that the image is safe or correct. Confirm hardware-specific assumptions using the target's linker map, vendor documentation, debugger, or simulator.

## Emulation sessions

Studio's `EmulationManager` discovers available tools and creates sessions backed by the local store and telemetry hub. A session can reference:

- project ID,
- target backend,
- firmware asset,
- platform asset,
- script asset,
- extra arguments,
- a constrained/custom command where supported by the implementation.

The session records its status, command metadata, start/stop time, logs, and telemetry. Stop sessions from the UI before changing assets/configuration to keep provenance clear.

## Telemetry

Telemetry points contain:

- timestamp,
- channel,
- value,
- kind (`analog` by default),
- optional metadata.

Studio can ingest telemetry through the API/session mechanism and stream it over WebSocket. Persisted points can be queried by channel/time range and transformed for plotting.

### Filtering and plot pipelines

Studio uses a restricted filtering implementation rather than evaluating arbitrary Python expressions. Plot processing is structured as a pipeline. Use filtering to narrow channels/time spans and processing stages to produce display data rather than modifying raw stored telemetry.

For reproducible debugging, keep the raw data and record the filter/pipeline assumptions separately in notes or exported artifacts.

## RF / EMC cockpit

The RF/EMC perspective intentionally brings construction, network matching, and noise analysis into one visual cockpit.

At a glance it shows:

- target/resonance/EMI/construction status cards,
- scale-relative patch/substrate/ground/feed view,
- likely high-edge-rate source hints from the project graph,
- S11 with target/pass regions,
- Smith chart and impedance trajectory,
- VSWR/accepted power/bandwidth/tuning guidance,
- log-frequency noise spectrum,
- harmonic and mask exceedance markers,
- FFT quality/Nyquist information,
- stale-result warnings after assumptions change.

The construction source map is a heuristic inspection aid; it is not an electromagnetic coupling solver. The EMI FFT is pre-compliance unless the acquisition chain is calibrated and representative of the applicable test method.

See [RF / EMC](RF_EMC.md).

## Local API

Interactive OpenAPI documentation is exposed at `/api/docs` while Studio is running.

Important route families:

| Route family | Purpose |
|---|---|
| `/api/health` | Health/auth/toolchain summary. |
| `/api/components*` | Search, stats, and component-library import. |
| `/api/assets*` | Content-addressed asset upload/list/fetch. |
| `/api/projects*` | Project graph persistence. |
| `/api/firmware/analyze` | Static firmware analysis for a stored asset. |
| `/api/rf/*` | Patch seed/model generation, Touchstone, and noise analysis. |
| `/api/toolchain` | Discovered emulation/tool availability. |
| `/api/sessions*` | Session start/list/stop and telemetry. |
| `/api/logs` | Persisted session logs. |
| `/ws/telemetry/{session_id}` | Live telemetry WebSocket. |

Data-bearing API routes require a bearer token when Studio is configured with one. The health endpoint intentionally returns only limited information before successful authentication in remote/token mode.

## Remote mode

Default loopback mode is the preferred deployment. To bind to a non-loopback interface:

```bash
embeddyn studio run --host 0.0.0.0 --allow-remote
```

This produces/requires an API token. Send it as:

```text
Authorization: Bearer <token>
```

Do not expose Local Studio directly to the public internet. Use a VPN, SSH tunnel, or trusted network boundary if remote access is required.

## Backups

Back up the entire configured Studio data directory while Studio is stopped, especially:

- `embeddyn-local.db`,
- `assets/sha256/`,
- `exports/`,
- logs that matter to your investigation,
- `studio.token` if you intentionally need to preserve the same remote token.

SQLite WAL mode is used for concurrency; stopping Studio before a filesystem-level backup avoids incomplete multi-file snapshots.
