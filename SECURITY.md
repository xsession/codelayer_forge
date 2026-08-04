# Security Policy

## Supported versions

Security fixes are applied to the latest minor release on the current major line.

## Reporting

Report suspected vulnerabilities privately to `security@codelayer.hu`. Do not open a public issue until a coordinated disclosure date is agreed.

Include the affected version, operating system, plugin package, reproduction steps, impact and any proposed mitigation.

## Security model

Plugins run out of process by default. Standard output is reserved for JSON-RPC. Plugin permissions are declared in `plugin.toml`; the host enforces workspace path boundaries and safe service dispatch. Native plugins and arbitrary process execution are disabled unless explicitly enabled by policy.

The current Python host provides process isolation and capability checks but is not a complete operating-system sandbox. Deploy untrusted third-party plugins inside an OS sandbox, container or restricted user account until platform-specific sandbox backends are enabled.
