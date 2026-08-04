# Release Operations

1. Update `CHANGELOG.md` and all package versions.
2. Run `make verify`.
3. Run Rust format, tests, Clippy and dependency audit.
4. Build native packages on clean Windows, Linux and macOS runners.
5. Sign binaries and plugin packages using organization-managed keys.
6. Generate an SBOM and checksums.
7. Publish the source archive, binaries and plugin catalog atomically.
8. Retain the previous release for rollback.

`python3 scripts/package_release.py` creates a deterministic source staging tree, ZIP archive and SHA-256 checksum. Native signing and notarization remain environment-specific CI responsibilities.
