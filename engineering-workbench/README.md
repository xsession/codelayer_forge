# Engineering Workbench

A clean-room, domain-independent web engineering workbench inspired by publicly observable dense EDA/CAD workflows. It intentionally does **not** copy Kactus2 source code or internal implementation details.

## What works in this starter

- Dense IDE/EDA-style shell with menu, toolbar, left library/project/hierarchy dock, canvas, right inspector, bottom problems/connections/console dock, and status bar.
- Reusable `ComponentDefinition` vs `ComponentInstance` model.
- Stable ID-based ports and connections.
- Drag components from the library onto the canvas.
- Drag components on the canvas with 10-unit snapping.
- Port-to-port connection gesture with live compatibility highlighting.
- Duplicate-connection rejection.
- Plugin-defined compatibility rules and validators.
- Orthogonal A* router with obstacle avoidance and bend penalty.
- Wide invisible edge hit areas for reliable selection.
- Connection inspector and delete action.
- Incremental-style validation API, required-port diagnostics, unresolved endpoint diagnostics, semantic connection diagnostics.
- Undo/redo command foundation for add/move/rename/connect/delete-connection operations.
- Example Electronics plugin with clock/reset/CPU/interconnect/RAM/UART/SPI/GPIO components.
- Unit tests for compatibility, routing, and command history.

## Run

```bash
npm install
npm run dev
```

Then open the Vite URL shown in the terminal.

## Test and build

```bash
npm test
npm run build
```

## Architectural rule

The project model is not the renderer model. The same semantic graph can later be rendered through SVG, Canvas, WebGL, a desktop shell, or headless tooling without changing the project format.

## Packages

- `packages/core` — domain-independent project/diagram/component/port/connection model
- `packages/commands` — reversible editing commands and history
- `packages/graph` — graph queries, connection creation, compatibility pipeline
- `packages/graph-router` — renderer-independent orthogonal routing
- `packages/validation` — diagnostics aggregation
- `packages/plugin-api` — plugin contracts and registry
- `packages/workbench-ui` — React dense workbench and diagram interaction
- `plugins/example-electronics` — example HDL/electronics semantics
- `apps/demo` — working example application

## Clean-room boundary

Kactus2 is used only as a behavioral/UX reference through public documentation, screenshots, standards, and observed functionality. Do not copy its source, assets, icons, strings, internal class layout, or source-derived algorithms into this project.

## Zero-dependency validated demo

A dependency-free version is included in `standalone/`. It exercises the same clean-room interaction model without React or a build tool, which makes it useful for visual QA and as a fallback demo.

Run it with any static file server, for example:

```bash
cd standalone
python3 -m http.server 8080
```

Then open `http://localhost:8080/`.
