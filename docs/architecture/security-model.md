# Security Model

## Trust levels

- **First-party signed plugin**: may receive declared hardware/process permissions after review.
- **Enterprise plugin**: distributed by a controlled repository and restricted by organization policy.
- **Untrusted plugin**: must run with no network, no arbitrary process execution and a restricted workspace.

## Implemented controls

- One process per Python plugin.
- Workspace path canonicalization and traversal prevention.
- Atomic JSON writes.
- Declarative permission checks for workspace access.
- No shell action in the PyOnTrust workflow adapter.
- Private method dispatch blocked by the service registry.
- Protocol logs separated from stdout.
- CSP applied to the desktop webview.

## Remaining hardening

Process isolation is not an operating-system sandbox. Production deployments accepting untrusted plugins should add platform sandbox adapters: AppContainer on Windows, sandbox-exec/seatbelt alternatives on macOS where applicable, and bubblewrap/landlock/seccomp on Linux. Plugin package signatures and repository trust roots are designed but not yet backed by a signing service in version 0.1.0.
