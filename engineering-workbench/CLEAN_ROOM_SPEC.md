# Clean-Room Engineering Workbench Specification

## Goal

Build a reusable, web-first engineering workbench with dense IDE/EDA UX and a domain-independent component connection engine. Kactus2 may be used only as a behavioral reference through public documentation, standards, screenshots, and observable application behavior.

## Clean-room boundary

Do not copy Kactus2 source code, internal class structure, algorithms derived from source inspection, icons, artwork, strings, or source-specific serialization. IP-XACT interoperability must be implemented from IEEE/Accellera specifications and independently authored test fixtures.

## Required architecture

```text
Domain plugins
    ↓
Plugin API
    ↓
Workbench UI -> Commands / Validation / Graph services
                         ↓
                    Core model
                         ↓
           Router / Renderer projection
```

The project model must never be the renderer model. Semantic connection meaning, connection legality, route geometry, and rendering are separate concerns.

## Dense workbench shell

Default layout:

```text
Menu + compact command toolbar
+----------------+--------------------------+----------------+
| Library/Tree   | Main diagram canvas      | Inspector      |
|                |                          | properties     |
|                |                          | ports/config   |
+----------------+--------------------------+----------------+
| Problems / Connections / Console / Tables                 |
+-----------------------------------------------------------+
Status bar
```

Routine editing must not require modal dialogs. Docks must remain compact, tabbed, resizable, and keyboard accessible.

## Core model

- immutable reusable `ComponentDefinition`
- placed `ComponentInstance`
- stable-ID `PortDefinition`
- grouped `InterfaceDefinition`
- first-class `Connection`
- route stored separately from semantic endpoints
- optional hierarchy ports, portals, regions, annotations
- schema-versioned project persistence

Renaming display names must never break connectivity.

## Connection behavior

- pointer-drag from port to port
- visible target compatibility during drag
- normalize input-to-output gestures to semantic output-to-input direction
- reject output-output/input-input unless plugin permits them
- plugin-defined type/protocol/width compatibility
- duplicate edge protection
- cardinality checks
- fan-out for ports that explicitly allow it
- 1–2 px visible wire with 8–14 px invisible hit target
- selected/hovered/error/warning states
- retain broken references rather than silently deleting data

## Routing

Default engineering routing is orthogonal. The implemented MVP uses a sparse rectilinear visibility graph built from endpoint coordinates and inflated obstacle boundaries, then uses shortest-path search with bend penalty. Routing is independent of React/DOM/SVG.

Routes should minimize:

- path length
- bend count
- component intersection
- label/port collision
- unnecessary reroute instability

Future route caching should reroute only affected connections.

## Node geometry invariants

- ports live on dedicated rails
- port row height is fixed and non-overlapping
- node minimum height derives from port count
- node minimum width must leave a central clearance between left/right labels
- port marker hitbox is larger than its visible marker
- connection labels may never cover port labels
- warnings may never cover the component title
- resizing cannot collapse ports onto one another

## Validation

Validation returns structured issues with severity, code, message, object reference, and optional quick fixes. Problems panel navigation must select and focus the referenced object. Validation must remain plugin-extensible.

## Commands and undo

Every modifying interaction is a reversible command or transaction. Auto-connect, auto-route, auto-layout, and quick fixes must be explainable and undoable as a single user action when appropriate.

## Plugin boundary

Plugins may contribute:

- component definitions/providers
- compatibility providers
- validators
- inspectors/property schemas
- commands
- importers/exporters
- generators
- connection types and visual decorations

Plugins may not reach into renderer DOM/SVG internals.

## Hierarchy

The data model must support component instances referencing child diagrams, hierarchy ports, breadcrumbs, parent/child navigation, and portals/off-page continuation. UI implementation is a later milestone but the model must not preclude it.

## Performance

Small diagrams should maintain 60 FPS interaction. Medium diagrams require spatial indexing, selective reroute/validation, and virtualized tables. Large diagrams should permit Canvas/WebGL edge rendering without changing semantic data.

## Persistence

Native format is independent schema-versioned JSON. Renderer-library serialization is forbidden as the canonical project format. Migrations must be explicit.

## Acceptance baseline implemented by MVP

- docked dense shell
- library drag/drop
- reusable definitions/instances
- node drag and snapping
- pan/zoom
- port connection gesture
- compatibility highlighting
- duplicate/cardinality validation
- obstacle-aware orthogonal routing
- large edge hit targets
- connection selection/deletion
- problems and connections tables
- inspector and rename
- undo/redo foundation
- example electronics plugin
- headless type-checkable core packages
- zero-dependency runnable browser demo
