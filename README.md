# CodeLayer Forge

CodeLayer Forge is a production-oriented, cross-platform engineering workbench for integrating domain tools as isolated plugins. The repository includes a Tauri desktop shell, a Rust plugin registry/CLI, a dependency-free Python plugin host and SDK, four initial engineering plugins, schemas, tests, CI, packaging scripts, security policy and an example workspace.

## Included integrations

- **Pin Configurator**: device/pin models, compatible-pin validation, automatic assignment and generated constraints.
- **Route Core**: obstacle-aware orthogonal A* routing with bend penalties and route validation.
- **OpenHDL Designer**: HDL graph validation, summary generation and synthesizable structural Verilog generation.
- **PyOnTrust Adapter**: a safe workflow adapter for JSON validation, template rendering and artifact writing. Its domain-specific API is intentionally isolated until the exact PyOnTrust contract is defined.

## Fastest local demonstration

Requirements: Python 3.11 or newer.

```bash
python3 scripts/doctor.py
python3 scripts/build_catalog.py
python3 scripts/demo.py
python3 -m http.server 4173 --directory apps/desktop/web
```

Open `http://localhost:4173`. The browser demo uses the checked-in plugin catalog. The same frontend is embedded by Tauri.

## Capability broker

The broker keeps plugin hosts alive, resolves commands and routes versioned capabilities to their providers:

```bash
python3 hosts/plugin-broker/forge_broker.py \
  --plugins-root plugins \
  --workspace examples/demo-workspace
```

Use `forge/callCapability` to call services such as `codelayer.routing.orthogonal` without depending on Route Core's implementation package.

## Plugin packaging

```bash
python3 scripts/pack_plugin.py plugins/route-core
python3 scripts/install_plugin.py dist/plugins/hu.codelayer.route-core-0.1.0.cforge-plugin \
  --target ~/.codelayer-forge/plugins
```

Packages contain a signed-ready file index with SHA-256 hashes. Installation rejects path traversal, duplicate paths, oversized archives and integrity mismatches, then swaps the verified plugin into place atomically.

## Plugin host demonstration

```bash
python3 hosts/python-plugin-host/forge_plugin_host.py \
  --plugin-dir plugins/pin-configurator \
  < examples/rpc/pin-configurator-session.jsonl
```

Protocol responses are written to standard output; logs go to standard error.

## Desktop development

Install Rust, the Tauri 2 prerequisites for your platform and Node.js 22+.

```bash
npm install
npm run desktop:dev
```

The frontend is checked in as dependency-free JavaScript so the application remains inspectable and demoable without a package installation. The TypeScript source is in `apps/desktop/src`.

## Verification

```bash
python3 -m unittest discover -s tests -v
python3 scripts/verify_repo.py
node --check apps/desktop/web/app.js
```

With Rust available:

```bash
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
```

## Repository map

- `apps/desktop`: Tauri shell and web frontend.
- `crates`: Rust protocol, registry/core and CLI crates.
- `hosts`: out-of-process plugin hosts and the capability broker.
- `sdk`: public plugin SDKs.
- `plugins`: first-party plugins.
- `schemas`: versioned JSON schemas.
- `examples`: workspace and JSON-RPC sessions.
- `docs`: architecture, plugin development, operations and ADRs.

## Production boundaries

This repository is a deployable platform foundation, not a claim of full feature parity with KiCad, FreeCAD or mature proprietary EDA suites. The process model, contracts, security boundaries, migrations, validation, tests and release automation are implemented; device databases, vendor importers and rich graphical editors are expected to grow as separate plugins.
