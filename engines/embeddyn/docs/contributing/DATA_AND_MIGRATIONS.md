# Data model, persistence, and migrations

Embeddyn has multiple persistent stores with different responsibilities. Treat schema/artifact changes as compatibility changes even when the Python API still imports successfully.

## Persistent stores

### Local Studio store

Owned by `embeddyn/local/store.py`.

Current conceptual records:

- metadata/schema state,
- bundled/imported components,
- content-addressed asset metadata,
- project graphs,
- emulation sessions,
- telemetry,
- logs,
- analysis records.

The physical asset blobs are stored under `assets/sha256/` and referenced from SQLite.

### Aggregated component library

Owned by `embeddyn/library/database.py` and `assets.py`.

Contains indexed entities, graphs, asset metadata and content-addressed media objects. It can be rebuilt from source directories when all source material is available, but local overrides/licensing metadata may make the store valuable user data.

### Mechatronics metadata/artifacts

Owned by `embeddyn/mechatronics/storage/`.

Contains run metadata, structured telemetry, and content-addressed artifacts. Distributed coordinator data is also SQLite-backed but represents queue/worker/experiment operational state rather than Studio projects.

## Schema change rules

1. Increment a schema version when the persistent representation is incompatible or requires a migration.
2. Make initialization idempotent.
3. Prefer additive nullable/defaulted columns for backward-compatible changes.
4. Never reinterpret an existing column's unit/meaning without migration and documentation.
5. Preserve foreign-key/cascade semantics intentionally.
6. Add indexes only for demonstrated/query-relevant access paths; remember they increase write cost.
7. Test both empty-store creation and prior-store migration where migration support exists.

## Content-addressed object rules

A content-addressed object name/hash means the bytes are immutable for that hash.

Do not:

- overwrite a SHA path with different bytes,
- use user-provided file names as storage paths,
- trust extension as the content identity.

Logical metadata (friendly name, MIME, source) may point to the same object hash.

## Telemetry compatibility

Telemetry is engineering evidence. When adding fields:

- keep timestamp semantics explicit,
- do not change channel names silently,
- include units in metadata/schema where available,
- preserve raw values even if UI pipelines transform them,
- keep event/bus/discrete/continuous kinds distinguishable.

If a new analysis requires resampling/filtering, store the settings/result separately rather than destructively rewriting raw telemetry.

## Project YAML compatibility

`MechatronicProject` supports `schema_version`. New keys should default safely when absent. Validation should fail with a clear error when old semantics cannot be safely inferred.

For a breaking schema evolution:

1. add a migration/translation path where practical,
2. preserve the original project file,
3. produce a new versioned representation,
4. update examples and docs,
5. add old/new fixtures.

## Units

Engineering values must not rely on comments for unit meaning. The model supports parsed quantities and signal unit strings. When changing units:

- migrate stored/default values,
- update transforms,
- update UI labels,
- update tests,
- update evidence thresholds.

A unit change is a data migration even if the JSON/YAML type remains `number`.

## Parameter provenance

Runtime/experiment overrides append provenance. Preserve:

- parameter name,
- numeric value,
- unit,
- source (`runtime-override`, experiment/job source, etc.).

If a new override source is added, name it explicitly. Do not just mutate `parameters` after compilation and lose the reason/value history.

## Dependency manifest/lock as persistent engineering data

`embeddyn.yml` and `embeddyn.lock.json` are part of reproducibility. Their schema changes should be versioned and backward-read if possible.

Manifest path handling must continue to reject traversal outside the repository root. Lock fields should remain stable enough for review tooling to compare source URLs, requested revisions, exact commits, and bundled fingerprints.

## RF result compatibility

RF reports are structured JSON-compatible dictionaries consumed by CLI/API/UI. When adding fields, prefer additive changes. If changing the definition of an existing metric (for example dB reference), introduce a new named field/version rather than silently changing numerical meaning.

## Backups and migrations

Before a destructive migration:

1. stop writers,
2. copy the database plus its associated content-addressed objects,
3. record the Embeddyn version/commit and schema version,
4. run migration on a copy,
5. verify object hashes and record counts,
6. keep rollback instructions.

For SQLite WAL databases, ensure the snapshot includes a consistent database state; stopping the application is the simplest safe path for user-managed backups.
