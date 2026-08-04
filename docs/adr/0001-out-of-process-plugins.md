# ADR 0001: Out-of-process plugins

- Status: Accepted
- Date: 2026-08-03

## Decision

Python and native plugins execute outside the desktop process and communicate using JSON-RPC. The default topology is one plugin per process.

## Consequences

Crashes and dependency conflicts are isolated. The API must be serializable and versioned. Large data should move through artifacts or a future binary transport instead of repeated JSON copies.
