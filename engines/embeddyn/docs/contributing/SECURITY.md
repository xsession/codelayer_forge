# Contributor security model

Embeddyn handles untrusted files, executes external engineering tools, stores firmware and telemetry, and can optionally bind a web API beyond loopback. Security is therefore a design constraint, not an afterthought.

See also the user-facing [Local security](../SECURITY_LOCAL.md).

## Trust boundaries

Treat these as untrusted or semi-trusted inputs:

- uploaded firmware/assets/component libraries,
- project graphs and YAML,
- Touchstone/CSV files,
- remote API requests when remote mode is enabled,
- external tool output,
- distributed job specifications,
- paths and arguments supplied by users,
- source dependency repositories before review/lock.

Treat external simulators/toolchains as powerful local code execution: installing/running them is equivalent to trusting those binaries/scripts at the user's privilege level.

## Process execution

### Required pattern

Use argument arrays:

```python
subprocess.run([executable, "--flag", value], check=True)
```

Do not construct a shell string from user/project values and pass `shell=True`.

A shell-escaped display string is acceptable for logs/manual copy if it is not used as the execution path.

### Working directories and outputs

Resolve paths and constrain generated output under an intended root. Worker job IDs/output paths must not escape their root. Do not trust a filename from an upload as a storage path.

### Timeouts and cleanup

External tools need explicit timeout/cancellation handling. Kill/terminate child processes and close files/sockets on errors. Avoid orphaned simulators holding ports/hardware.

## Web/API exposure

### Default local-only

Studio binds to loopback by default. Non-loopback binding requires explicit `--allow-remote` behavior and a non-empty bearer token.

### Token handling

- Generate cryptographically random token material.
- Store with restrictive permissions where supported.
- Compare with constant-time comparison.
- Do not log the token repeatedly or include it in reports.
- Do not put it in project files.

### Public endpoints

Keep unauthenticated endpoints minimal. `/api/health` may expose a basic status/auth requirement but should not leak sensitive local paths/tool details before authentication in token mode.

### Browser/UI

Sanitize persisted strings/attributes before inserting into HTML/SVG/DOM contexts. Do not use `innerHTML` on untrusted metadata unless safely escaped/constructed.

## Uploads and parsers

- Enforce size limits before buffering entire content.
- Restrict expected extensions/types where the endpoint has a narrow purpose.
- Validate actual file structure/magic in the parser.
- Delete temporary import files on success and failure.
- Bound record lengths/counts and FFT arrays.
- Never execute uploaded firmware during static analysis.

## Configuration safety

Do not use arbitrary `eval`, `exec`, Jinja execution from untrusted templates, or unrestricted filter expressions.

The mechatronics coupling model intentionally supports typed transforms. Studio filtering uses a restricted parser/allowed operation set. Preserve these boundaries.

## Dependency/supply-chain safety

Dependency updates are explicit and reviewable:

- manifest requested ref,
- lock exact commit or bundled fingerprint,
- dirty-tree refusal,
- recursive dependency handling where declared.

Review upstream changes before committing a new lock. A locked malicious commit is still malicious; reproducibility is not trust by itself.

## Distributed execution

Worker jobs result in local process execution. Therefore:

- only point workers at a trusted coordinator/job database,
- validate project paths and output containment,
- keep worker capabilities/labels explicit,
- do not accept arbitrary custom shell commands as a generic job feature,
- use OS/container boundaries when workers process less-trusted workloads.

SQLite coordinator state is not a secure multi-tenant message broker. Do not expose it as one.

## HIL safety versus cybersecurity

HIL safety policy protects physical outputs from software/control faults, but it is not an authentication system. Conversely, API authentication does not make unsafe actuator commands physically safe. Preserve both layers.

For real hardware, independent hardware safety/enable/watchdog mechanisms are required.

## RF generated scripts

The patch openEMS generator produces a script from validated numeric values. Preserve this property. Do not add an API field that inserts arbitrary Python/openEMS statements into generated scripts.

## Secrets and bug reports

Do not commit:

- Studio tokens,
- proprietary firmware unless intentionally licensed for the repo,
- customer board files/logs,
- credentials/API keys,
- private network addresses if they are sensitive to the deployment.

When adding diagnostics, redact secrets and prefer hashes/IDs over full sensitive content.

## Security review triggers

Request deeper review when a change adds:

- a new network listener/protocol,
- authentication/authorization behavior,
- arbitrary file upload/extraction,
- subprocess execution,
- plugin/dynamic code loading,
- path traversal-sensitive behavior,
- new remote worker trust model,
- archive parsing,
- dependency installer/updater behavior,
- physical output control.
