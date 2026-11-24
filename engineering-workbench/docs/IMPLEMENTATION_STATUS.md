# Implementation status

## Implemented now

- Dense web workbench shell.
- Component library, project/hierarchy tabs, document tabs, inspector, bottom tables, status bar.
- Stable-ID semantic graph model.
- Component definition/instance split.
- Ports, interfaces in core model, connection routes, hierarchy-ready fields.
- Plugin registry, compatibility providers, validators, importer/exporter/generator contracts.
- Example Electronics plugin.
- Interactive drag/drop node creation.
- Node movement with snapping.
- Pan/zoom.
- Port-to-port connection gesture.
- Compatibility highlighting and input/output normalization in standalone demo.
- Duplicate and single-cardinality protection.
- Orthogonal sparse visibility routing around component obstacles.
- Wide invisible connection hit areas.
- Connection selection and deletion.
- Problems and connections tables.
- Undo/redo command foundation.
- JSON persistence/migration boundary.
- Core TypeScript type-check configuration.
- Dependency-free browser demo and router self-test.

## Next production milestones

1. Cached route graph + worker-based reroute scheduling.
2. Full command coverage for property edits and multi-object transactions.
3. Multi-select, align, distribute, box-select.
4. Manual/semi-automatic waypoints and segment locking.
5. Interface bundle rendering and mapping editor.
6. Auto-connect candidate preview and batch transaction.
7. Hierarchical diagram navigation and hierarchy ports.
8. Portal/off-page connection UI.
9. IndexedDB autosave/recovery and schema migrations.
10. Renderer adapter abstraction plus Canvas/WebGL edge backend.
11. IP-XACT importer/exporter from IEEE/Accellera specifications.
12. OpenHDL plugin, HDL parser/generator integration, and domain-specific validation.
13. Geometry/property-based tests and screenshot regression CI.
