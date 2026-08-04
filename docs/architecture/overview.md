# Architecture Overview

## Goals

CodeLayer Forge integrates engineering tools without coupling their implementation languages, dependency graphs or release cadence. The core owns workspace lifecycle, plugin discovery, command dispatch, permissions and process supervision. Domain behavior remains in plugins.

## Process model

```text
Desktop WebView
    │ Tauri invoke
    ▼
Rust desktop host ─── Rust registry/core
    │ newline-delimited JSON-RPC 2.0
    ▼
Dedicated Python plugin host
    │ registered commands/services
    ▼
One plugin instance
```

Each Python plugin receives a dedicated process. Standard output carries only protocol messages. Standard error carries structured operational logs. A plugin cannot invoke an unregistered command or service method.

## Stable boundaries

1. `plugin.toml` declares identity, compatibility, contributions, services and permissions.
2. JSON-RPC defines lifecycle and invocation messages.
3. The Python SDK exposes a restricted context rather than Tauri or UI internals.
4. Workspace documents use explicit schema versions.
5. Plugins depend on semantic capabilities, not implementation packages.

## Frontend strategy

The checked-in frontend uses browser-native modules and no runtime framework dependency. This keeps the shell bootable in restricted/offline environments and makes the Tauri asset bundle deterministic. The host API and plugin webview boundary allow a future React-based graph editor without changing core contracts.

## Data flow

A workspace contains source documents and generated artifacts. Plugins read/write only through workspace-relative paths when permissions allow it. Generated files are kept separate from editable graph and pin-plan sources. Long-running work will evolve toward cancellable task handles and progress events; the synchronous request/response implementation is intentionally narrow for the first release.
