# Architecture

## Dependency direction

```text
Example/domain plugins
        ↓
   Plugin API
        ↓
Workbench UI ─────→ Graph / Validation / Commands
        ↓                     ↓
   Renderer layer          Core model
        ↓
   SVG / DOM today
```

`core`, `commands`, `graph`, `graph-router`, `validation`, and `plugin-api` are intentionally React-independent.

## Semantic graph vs geometry

A `Connection` stores semantic endpoints. Route geometry is produced by `graph-router` from endpoint positions and obstacles. The current UI calculates routes on render; a later worker-backed route cache can be introduced without changing the project model.

## Connection pipeline

```text
pointer gesture
    ↓
EndpointRef pair
    ↓
duplicate check
    ↓
CompatibilityProvider(s)
    ↓
CompatibilityResult
    ↓
AddConnectionCommand
    ↓
Connection in semantic model
    ↓
router derives geometry
    ↓
SVG renderer
```

## Plugin boundary

A plugin may contribute definitions, compatibility providers, and validators. Future revisions should add declarative inspectors, commands, generators, importers/exporters, and visual badges. Plugins must not directly mutate DOM/SVG renderer internals.

## Next implementation milestones

1. Route cache + Web Worker routing.
2. Multi-selection and transactional commands.
3. Manual/semi-automatic waypoints.
4. Interfaces and bundle expansion/collapse.
5. Hierarchical diagrams and hierarchy ports.
6. Port-mapping editor and Auto Connect preview.
7. JSON persistence/migrations and IndexedDB recovery.
8. Renderer abstraction interface plus optional Canvas/WebGL edge renderer.
9. IP-XACT plugin implemented from IEEE/Accellera specifications.
10. OpenHDL Designer plugin and HDL generation adapters.
