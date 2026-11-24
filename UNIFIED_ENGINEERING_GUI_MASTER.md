# Unified Engineering GUI — Master Documentation

This file merges all unique Markdown documentation produced for the dense engineering GUI demo, its design system, connector fixes, layout-safety rules, implementation notes, iteration history, and validation reports.

## Document Map

1. [Project README](#project-readme) — `README.md`
2. [Unified GUI Design System](#unified-gui-design-system) — `DESIGN.md`
3. [Diagram Layout Safety Rules](#diagram-layout-safety-rules) — `DIAGRAM_LAYOUT_SAFETY_RULES.md`
4. [Layout Safety Implementation](#layout-safety-implementation) — `LAYOUT_SAFETY_IMPLEMENTATION.md`
5. [Iteration Record](#iteration-record) — `ITERATIONS.md`
6. [Connector Rendering Fix Report](#connector-rendering-fix-report) — `FIX_REPORT.md`
7. [Original Smoke Test Report](#original-smoke-test-report) — `TEST_REPORT.md`
8. [Layout Safety Test Report](#layout-safety-test-report) — `TEST_REPORT_LAYOUT_SAFETY.md`

## Merge Notes

- The top-level and project copies of `DESIGN.md` were byte-identical, so the design specification is included once.
- Original document content is preserved; headings are demoted one level so the merged file has one master title.
- Relative project references remain relative to the demo project directory.


---

## Project README

**Original file:** `README.md`  
**SHA-256:** `a001050d973d65998bf1594cffb388d9c2a6a322e64bbd91871748a24faa7682`

## Unified Engineering GUI Demo

A dependency-free browser demo implementing the dense engineering workstation patterns from `DESIGN.md`.

### Included interactions

- Dense application shell with command bar, navigation rail, project explorer, document tabs, inspector, diagnostics panel, and status bar.
- Draggable engineering nodes with ports on all four sides.
- Dynamic SVG arrow routing recalculated from actual DOM geometry.
- Orthogonal Manhattan routing with candidate path scoring and node-collision avoidance.
- Route labels placed on the longest usable horizontal segment.
- Route selection, animated flow indication, and route details in the inspector.
- Node selection synchronized to the inspector.
- Resizable left, right, and bottom panels.
- Collapsible panels.
- Live minimap synchronized with node positions and routes.
- Fit-layout, avoid/direct routing, flow animation, and canvas status controls.
- Three complete implementation iterations with real 1920A�1080 screenshots.

### Run

#### Windows

Double-click `run-demo.bat`, then open the shown local address.

#### Linux or macOS

```bash
./run-demo.sh
```

Alternatively, open `index.html` directly in a modern browser. Serving it locally is recommended:

```bash
python3 -m http.server 8080
```

Then open `http://127.0.0.1:8080`.

### Controls

- Drag a node by its header; every route updates immediately.
- Click a node to inspect it.
- Click a connection to select it and show animated flow.
- Use **Avoid nodes** or **ORTHO · AVOID** to toggle obstacle-aware routing.
- Drag the narrow splitters between panels to resize them.
- Use the small chevrons in panel headers to collapse panels.
- Use **Fit** to restore the default node layout.

### Iterations

1. `iterations/iteration-1/` — dense workstation shell and static visual layout.
2. `iterations/iteration-2/` — DOM-geometry routing and draggable nodes.
3. `iterations/iteration-3/` — collision-aware routing, minimap, panel resizing, route selection, and synchronized inspector.

Screenshots are in `screenshots/`.

### Architecture

The demo uses plain HTML, CSS, and JavaScript so it is easy to embed in a larger Electron, Tauri, React, Vue, or plugin-host application. The routing engine is isolated in `app.js` and can be replaced later by Route Core or exposed through a plugin API.


---

## Unified GUI Design System

**Original file:** `DESIGN.md`  
**SHA-256:** `3ef867c54c743d7d1c1a2eafff2ee5462719c8e013a630faba03833af1dc6d0d`

## Unified Engineering GUI Design System

**Document:** `DESIGN.md`  
**Status:** Normative  
**Applies to:** Unified Developer Platform, PyOnTrust, Pin Configurator, Route Core, OpenHDL Designer, future plugins  
**Design mode:** Dense engineering workstation UI  
**Primary targets:** Desktop Windows and Linux  
**Secondary targets:** macOS, large tablets in review-only mode

---

### 1. Purpose

This document defines the visual, interaction, layout, and extension rules for the unified engineering application.

The interface shall feel like a professional engineering workstation rather than a consumer dashboard. It must support long sessions, large projects, high information density, keyboard-driven workflows, multiple synchronized views, and predictable plugin integration.

The design system is optimized for:

- hardware and software architecture work;
- schematic, HDL, pin, route, and dependency editing;
- large tables and property sets;
- source-linked diagnostics;
- simulation and build output;
- side-by-side comparison;
- plugin-provided tools;
- traceable, deterministic engineering operations.

The GUI shall prioritize correctness, visibility of system state, and efficient manipulation over decorative presentation.

---

### 2. Core Design Principles

#### 2.1 Engineering density

Use available screen space efficiently. Avoid oversized cards, large empty margins, marketing-style hero areas, and touch-first spacing on desktop.

Dense does not mean visually chaotic. Density shall be created through:

- compact controls;
- consistent alignment;
- strict grouping;
- stable panel locations;
- restrained color;
- clear hierarchy;
- progressive disclosure;
- user-configurable columns and panels.

#### 2.2 Stable workspace

Tools, panels, inspectors, and output areas shall remain in predictable locations. Opening a command shall not unexpectedly replace unrelated content.

The application shell shall support:

- docked panels;
- tabbed documents;
- split editors;
- floating windows where supported;
- saved workspace layouts;
- per-project layout restoration;
- per-tool default layouts.

#### 2.3 Data first

The primary visual objects are engineering data, not containers.

Prefer:

- tables over card grids;
- trees over nested accordions;
- direct labels over tooltips;
- inline status over modal messages;
- compact inspectors over multi-step forms;
- live validation over submit-and-fail workflows.

#### 2.4 Explicit state

Every operation that changes files, devices, generated output, or project state shall expose:

- current state;
- pending state;
- validation state;
- dirty state;
- generated state;
- source of truth;
- last successful operation;
- last error;
- recovery action.

#### 2.5 Keyboard and mouse parity

Every frequent action shall be accessible by keyboard. Every keyboard action shall have an discoverable GUI equivalent.

The application shall provide:

- global command palette;
- context-specific command search;
- configurable shortcuts;
- focus indicators;
- predictable tab order;
- keyboard navigation for trees and tables;
- editor-local shortcuts;
- shortcut conflict detection.

#### 2.6 Plugin consistency

Plugins may extend the platform, but shall not invent incompatible visual systems.

Plugins shall use shared:

- typography;
- spacing;
- icons;
- commands;
- notifications;
- tree and table components;
- inspectors;
- forms;
- status conventions;
- docking APIs;
- theme tokens;
- accessibility rules.

---

### 3. Application Shell

The default desktop layout uses six persistent regions.

```text
�S──────────────────────────────────────────────────────────────────────────────┐
│ Menu Bar │ Project Selector │ Context Actions │ Global Search │ Run Controls │
�s───────┬───────────────────────────────────────────────────────┬──────────────┤
│       │ Document Tabs / Breadcrumbs / Local Toolbar           │              │
│ Nav   �s───────────────────────────────────────────────────────┤ Inspector /  │
│ Rail  │                                                       │ Properties   │
│       │ Main Editor / Canvas / Table / Diagram                │              │
│       │                                                       │              │
�s───────┴───────────────────────────────────────────────────────┴──────────────┤
│ Problems │ Output │ Terminal │ Simulation │ Trace │ Tests │ Logs             │
�s──────────────────────────────────────────────────────────────────────────────┤
│ Branch │ Target │ Connection │ Build │ Diagnostics │ Cursor │ Notifications │
└──────────────────────────────────────────────────────────────────────────────�?
```

#### 3.1 Top command bar

Height: `32–38 px`.

Contains:

- application menu;
- active project and configuration;
- active target or device;
- navigation history;
- command palette;
- global search;
- build, run, simulate, program, and stop actions;
- connection state;
- user/workspace menu.

Rules:

- no oversized logo;
- no decorative gradients;
- actions shall display text only when ambiguity exists;
- destructive actions shall not be placed next to primary run actions;
- disabled controls shall include an explanatory tooltip;
- current target and current configuration shall remain visible.

#### 3.2 Navigation rail

Width: `40–48 px`.

Provides top-level tool switching:

- Project;
- Design;
- Pins;
- Routes;
- HDL;
- Simulation;
- Build;
- Test;
- Devices;
- Packages;
- Plugins;
- Settings.

A plugin may contribute one navigation entry only when it represents a major workspace. Minor plugin functions shall contribute views inside an existing workspace.

#### 3.3 Primary side panel

Default width: `240–320 px`.  
Minimum width: `180 px`.  
Maximum recommended width: `420 px`.

Common contents:

- project tree;
- hierarchy browser;
- design object tree;
- netlist tree;
- source browser;
- build targets;
- plugin explorer;
- search results.

The panel shall support:

- filtering;
- pinning;
- collapse;
- multi-selection;
- context commands;
- reveal-in-editor;
- badges;
- source and generated-object differentiation.

#### 3.4 Main document area

The main area supports:

- text editors;
- block diagrams;
- schematic canvases;
- routing views;
- pin maps;
- register views;
- timing views;
- tables;
- reports;
- diff views;
- generated previews.

Documents open as tabs. Tabs shall show:

- title;
- type icon;
- dirty marker;
- validation marker;
- generated/read-only marker;
- close action;
- optional preview-state marker.

Tabs support split-left, split-right, split-up, split-down, move-to-group, pin, duplicate view, and close others.

#### 3.5 Inspector

Default width: `280–360 px`.

The inspector displays properties for the current selection. It shall not become a generic dumping area.

Property groups:

- Identity;
- Source;
- Electrical;
- Logical;
- Physical;
- Timing;
- Constraints;
- Connections;
- Generated values;
- Validation;
- Metadata.

Inspector behavior:

- edit in place;
- show units;
- show inherited values;
- identify overridden values;
- expose source location;
- show validation immediately;
- support multi-edit;
- preserve group expansion per object type;
- provide copy property path;
- provide reset-to-default;
- distinguish calculated values from editable values.

#### 3.6 Bottom panel

Default height: `180–280 px`.

Tabs:

- Problems;
- Output;
- Terminal;
- Build;
- Test;
- Simulation;
- Trace;
- Device Log;
- Generated Files;
- Tasks.

The panel opens automatically only for high-severity failures or explicit commands. It shall not steal editor focus.

#### 3.7 Status bar

Height: `22–26 px`.

Always visible unless presentation mode is active.

Displays:

- repository branch and dirty state;
- project configuration;
- active target;
- toolchain;
- connection state;
- build state;
- simulation state;
- diagnostics count;
- selected object summary;
- cursor coordinates or line/column;
- zoom;
- background task count.

Status items shall be clickable and open the relevant selector or diagnostic view.

---

### 4. Density Scale

The platform provides three density modes:

| Mode | Row Height | Control Height | Intended Use |
|---|---:|---:|---|
| Compact | 22 px | 24 px | Large tables, experienced users |
| Standard | 26 px | 28 px | Default engineering mode |
| Comfortable | 32 px | 34 px | Accessibility and touch-assisted use |

Default: `Standard`.

Density is a user preference and shall affect all core and plugin components consistently.

---

### 5. Spatial System

Use a `4 px` base grid.

Allowed spacing values:

- `2 px`: optical correction only;
- `4 px`: tight related elements;
- `8 px`: normal control separation;
- `12 px`: group separation;
- `16 px`: section separation;
- `24 px`: major structural separation;
- `32 px`: rare, page-level separation.

Avoid arbitrary spacing values.

Panel padding:

- compact: `4–6 px`;
- standard: `8 px`;
- comfortable: `12 px`.

No content panel shall use more than `16 px` internal padding on desktop unless it is a document preview.

---

### 6. Typography

Use a neutral, highly legible sans-serif UI font and a dedicated monospace font for technical values.

Recommended stack:

```css
--font-ui: Inter, "Segoe UI", Roboto, Arial, sans-serif;
--font-mono: "JetBrains Mono", "Cascadia Code", Consolas, monospace;
```

Typography scale:

| Token | Size | Weight | Usage |
|---|---:|---:|---|
| `text-xs` | 11 px | 400–500 | metadata, badges |
| `text-sm` | 12 px | 400–500 | dense tables, status bar |
| `text-md` | 13 px | 400–500 | default UI |
| `text-lg` | 15 px | 600 | section headers |
| `text-xl` | 18 px | 600 | document titles |
| `text-2xl` | 22 px | 600 | rare page headings |

Rules:

- use monospace for identifiers, addresses, paths, signals, pins, values, masks, code, timestamps, and coordinates;
- use tabular numerals for numeric tables;
- do not use all-uppercase labels except short electrical or protocol abbreviations;
- truncate only when the full value is available through tooltip or expandable field;
- identifiers shall preserve case exactly.

---

### 7. Color System

The platform supports dark and light themes through semantic tokens.

Color shall communicate state, not decorate the interface.

Required semantic tokens:

```css
--surface-app
--surface-panel
--surface-editor
--surface-raised
--surface-selected
--surface-hover
--surface-disabled

--border-subtle
--border-default
--border-strong
--border-focus

--text-primary
--text-secondary
--text-muted
--text-disabled
--text-inverse

--accent-primary
--accent-secondary

--state-info
--state-success
--state-warning
--state-error
--state-running
--state-paused
--state-offline
--state-generated
--state-modified
```

Rules:

- do not rely on color alone;
- state colors shall include icons or text;
- avoid saturated full-panel backgrounds;
- reserve strong red for errors and destructive actions;
- warning amber shall not be used for ordinary dirty-state indication;
- generated data shall use a distinct neutral/technical treatment;
- selected objects shall remain distinguishable under all state colors.

---

### 8. Borders, Elevation, and Shape

Engineering UI uses borders and grouping more than shadows.

Rules:

- default corner radius: `3 px`;
- large radius: `6 px`, only for dialogs and overlays;
- pills are reserved for short tags and states;
- avoid rounded card grids;
- use `1 px` borders for panel separation;
- use shadows only for floating menus, dialogs, tooltips, and drag previews;
- docked surfaces shall not cast shadows.

---

### 9. Icons

Use a single technical icon family with consistent stroke weight.

Icons shall be:

- `14–16 px` in controls;
- `16 px` in trees;
- `18–20 px` in the navigation rail;
- paired with text for uncommon actions;
- visually distinct for edit, generate, validate, simulate, build, program, connect, disconnect, and stop.

Never use icons as the only indicator for:

- destructive operations;
- device connection failures;
- validation errors;
- unsaved changes;
- generated versus source objects.

---

### 10. Command Model

Every action is registered as a command.

Each command includes:

```ts
interface CommandDefinition {
  id: string;
  title: string;
  category: string;
  icon?: IconId;
  defaultShortcut?: string;
  when?: ContextExpression;
  enableWhen?: ContextExpression;
  visibleWhen?: ContextExpression;
  destructive?: boolean;
  telemetryClass?: "none" | "usage" | "diagnostic";
}
```

Command IDs use reverse-domain namespaces:

```text
codelayer.project.open
codelayer.build.run
codelayer.pin.assign
codelayer.route.autoroute
codelayer.hdl.generate
plugin.vendor.tool.command
```

Commands may appear in:

- menus;
- toolbars;
- context menus;
- command palette;
- keyboard shortcuts;
- task definitions;
- scripting APIs.

The GUI shall not implement actions outside the command registry.

---

### 11. Toolbar Pattern

Toolbars shall contain only frequent, context-relevant actions.

Order:

1. navigation;
2. create/add;
3. edit;
4. validate;
5. generate/build;
6. execute/simulate/program;
7. view controls;
8. overflow.

Rules:

- group with separators;
- show active modes;
- expose keyboard shortcuts in tooltips;
- move low-frequency commands to overflow;
- avoid more than 10 directly visible actions in one toolbar;
- do not hide critical stop or cancel actions in overflow.

---

### 12. Tree Pattern

Trees are used for hierarchy, ownership, and containment.

Each row may include:

- expand control;
- type icon;
- primary label;
- secondary label;
- state badge;
- diagnostics count;
- source/generated marker;
- visibility toggle;
- lock marker.

Required behaviors:

- multi-select;
- range select;
- drag and drop;
- keyboard expand/collapse;
- incremental search;
- type-to-select;
- inline rename;
- reveal source;
- copy path;
- filter by type/state;
- preserve expansion state.

Tree indentation shall remain compact. Deep hierarchies should optionally switch to path or flattened filtered mode.

---

### 13. Table Pattern

Tables are the primary dense-data component.

Required capabilities:

- sortable columns;
- reorderable columns;
- resizable columns;
- pinned columns;
- hidden columns;
- multi-column sort;
- filtering;
- grouping;
- multi-selection;
- copy/paste;
- inline edit;
- validation;
- unit-aware values;
- export;
- saved views;
- keyboard navigation;
- column presets;
- row virtualization.

Table header height shall not exceed `32 px` in standard density.

Numeric alignment:

- integers and floating-point values: right;
- hexadecimal values: right, monospace;
- units: separate column or structured suffix;
- identifiers: left, monospace;
- states: left with icon;
- boolean values: centered only when represented by checkbox.

Do not place multiple unrelated values in one cell.

---

### 14. Form and Property Editing Pattern

Forms shall be used for configuration, not for browsing large engineering datasets.

Field anatomy:

```text
Label
[ Input value                         ] [unit] [source/reset]
Helper text or validation message
```

Rules:

- labels above fields in narrow panels;
- labels left-aligned in wide property grids;
- units always visible;
- valid ranges visible or discoverable;
- show default, inherited, calculated, and overridden state;
- validation occurs on edit;
- invalid values remain visible and editable;
- do not erase invalid user input;
- destructive changes require confirmation only when recovery is difficult;
- prefer undo over repeated confirmation dialogs.

---

### 15. Canvas and Diagram Pattern

The unified canvas is used by architecture, HDL, schematic, route, and system-design tools.

#### 15.1 Canvas layers

1. background;
2. grid;
3. guides;
4. groups/containers;
5. nodes/components;
6. ports/pins;
7. routes/connections;
8. annotations;
9. diagnostics;
10. selection and interaction overlays.

#### 15.2 Navigation

Required:

- wheel zoom;
- cursor-centered zoom;
- middle-button pan;
- space-drag pan;
- zoom-to-fit;
- zoom-to-selection;
- overview/minimap;
- navigation history;
- breadcrumb hierarchy;
- keyboard nudge;
- grid and snap controls.

#### 15.3 Nodes

Nodes shall expose:

- type;
- instance name;
- status;
- key ports;
- collapsed/expanded state;
- source/generated state;
- diagnostics;
- lock state.

Avoid excessive decoration. Node headers shall use semantic color only for type or state.

#### 15.4 Ports

Ports shall have:

- visible direction;
- type;
- width;
- name;
- connection state;
- compatibility state;
- optional electrical/protocol metadata.

Compatible connection targets may highlight during routing. Incompatible targets shall explain why they are rejected.

#### 15.5 Connections

Connections shall support:

- orthogonal routing by default;
- manual bend points;
- automatic cleanup;
- route locking;
- bus representation;
- direction indicators;
- labels placed on clear segments;
- crossing minimization;
- hover isolation;
- source-to-destination trace.

Connection labels shall not overlap nodes, ports, or other labels.

#### 15.6 Selection

Selection shall remain visible regardless of object state.

Support:

- click;
- Ctrl/Cmd toggle;
- Shift range where applicable;
- marquee;
- lasso when useful;
- select connected;
- select same type;
- select by query;
- invert selection.

#### 15.7 Large-design behavior

For large designs:

- use level-of-detail rendering;
- virtualize off-screen labels;
- defer expensive validation;
- cluster repeated objects;
- provide filtered focus mode;
- allow hiding inactive layers;
- show performance indicators when rendering is degraded.

---

### 16. Source and Generated Data

The application must clearly distinguish editable source from generated output.

Source objects:

- normal text and icons;
- editable;
- participate in undo/redo;
- display dirty state.

Generated objects:

- generated marker;
- read-only by default;
- display generator and timestamp;
- provide �sopen source definition�t;
- provide �sregenerate�t;
- provide diff against previous generation;
- must not silently accept edits that will be overwritten.

Derived values:

- show formula, source, or dependency path;
- allow copy;
- remain visually distinct from manual values.

---

### 17. Diagnostics Pattern

Diagnostics are first-class objects.

Severity:

- Error;
- Warning;
- Information;
- Hint.

Each diagnostic shall include:

- code;
- message;
- object or file;
- location;
- source subsystem;
- timestamp when relevant;
- quick fix when available;
- suppression status;
- documentation link;
- related locations.

Diagnostics appear in:

- editor/canvas;
- tree badges;
- inspector;
- Problems table;
- status bar.

Diagnostic codes shall be stable and searchable.

Example:

```text
PIN-0042  Voltage-domain mismatch: GPIO_A12 is assigned to a 1.8 V bank
but the selected peripheral requires 3.3 V.
```

---

### 18. Build, Generate, Simulate, and Program States

Use a shared execution state machine:

```text
idle
queued
preparing
running
paused
waiting-for-input
cancelling
succeeded
succeeded-with-warnings
failed
cancelled
disconnected
```

Every running task shall expose:

- task name;
- target;
- elapsed time;
- current phase;
- progress when measurable;
- log stream;
- cancel action;
- owning plugin/tool;
- output artifacts.

Do not show fake percentage progress. Use phase-based progress when completion cannot be measured.

---

### 19. Notifications

Use four notification levels:

- transient status;
- non-blocking toast;
- persistent notification;
- modal blocking dialog.

Default to the least disruptive level.

Modal dialogs are allowed only for:

- unrecoverable destructive actions;
- permission or credential requirements;
- mandatory conflict resolution;
- operations requiring explicit user choice before continuing.

A successful routine action should usually update the status bar or output panel, not create a toast.

---

### 20. Dialog Pattern

Dialog widths:

- small: `360–440 px`;
- medium: `520–720 px`;
- large: `800–1100 px`.

Rules:

- one primary action;
- primary action on the right;
- cancel always available unless technically impossible;
- Enter activates primary action only when safe;
- Esc cancels;
- destructive actions use explicit verbs;
- preserve entered data after validation failure;
- show affected targets and files before destructive operations.

Avoid nested dialogs.

---

### 21. Search and Filtering

The platform provides four search scopes:

1. command search;
2. project text search;
3. design-object search;
4. current-view filter.

Global search syntax should support structured queries:

```text
type:pin bank:3 voltage:3.3V status:error
type:signal width:>32 unconnected:true
path:src/ protocol:spi
owner:plugin.openhdl generated:false
```

Search results shall be navigable, filterable, and source-linked.

---

### 22. Context Menus

Context menus contain only actions valid for the current selection.

Ordering:

1. primary action;
2. open/reveal;
3. edit;
4. create/add;
5. generate/validate/run;
6. view;
7. clipboard;
8. destructive;
9. properties.

Menus shall not exceed roughly 20 visible commands. Use submenus for structured groups, not to hide arbitrary overflow.

---

### 23. Undo, Redo, and Transactions

All editable engineering operations shall participate in undo/redo where feasible.

A user-visible operation may include multiple internal changes but shall appear as one semantic transaction.

Examples:

- assign peripheral to pins;
- move a diagram group;
- rename a signal and update references;
- apply route optimization;
- accept generated constraint changes.

The history view shall show semantic action names, affected objects, tool owner, and timestamp.

External operations such as device programming are not undoable, but their configuration changes are.

---

### 24. Workspace Layouts

Provide built-in layouts:

#### Design

- project tree left;
- canvas center;
- inspector right;
- diagnostics bottom.

#### HDL

- hierarchy left;
- source editor center;
- symbol/outline right;
- build/simulation bottom.

#### Pin Configuration

- peripheral tree left;
- pin map center;
- assignment table lower center;
- electrical inspector right.

#### Routing

- net tree left;
- route canvas center;
- constraint inspector right;
- route analysis bottom.

#### Debug and Simulation

- source/design center;
- variables/registers right;
- call stack left;
- trace/terminal bottom.

Users may save named layouts. Plugins may provide templates but shall not overwrite user layouts.

---

### 25. Plugin Contribution Model

Plugins may contribute:

- commands;
- menu items;
- toolbar actions;
- navigation views;
- dock panels;
- editors;
- inspectors;
- property sections;
- tree nodes;
- table columns;
- status items;
- diagnostics;
- tasks;
- settings;
- themes only through token overrides;
- file types;
- object renderers.

Example manifest:

```json
{
  "id": "codelayer.openhdl",
  "displayName": "OpenHDL Designer",
  "version": "1.0.0",
  "contributes": {
    "commands": [
      {
        "id": "codelayer.openhdl.generate",
        "title": "Generate HDL",
        "category": "OpenHDL"
      }
    ],
    "views": [
      {
        "id": "codelayer.openhdl.hierarchy",
        "container": "design.left",
        "title": "HDL Hierarchy"
      }
    ],
    "editors": [
      {
        "id": "codelayer.openhdl.blockEditor",
        "fileExtensions": [".ohdl", ".hdb"]
      }
    ],
    "propertySections": [
      {
        "id": "codelayer.openhdl.timing",
        "appliesTo": "hdl.instance",
        "title": "Timing"
      }
    ]
  }
}
```

Plugin UI requirements:

- use platform components;
- use semantic tokens;
- register commands;
- support density modes;
- support keyboard navigation;
- provide loading, empty, and error states;
- clean up contributed views on unload;
- avoid blocking the main UI thread;
- expose long operations as tasks;
- use platform diagnostics;
- respect project trust and permissions.

---

### 26. Settings Architecture

Settings scopes:

- application;
- workspace;
- project;
- tool;
- language/file type;
- device/target.

Every setting includes:

```ts
interface SettingDefinition<T> {
  key: string;
  title: string;
  description: string;
  type: "boolean" | "number" | "string" | "enum" | "array" | "object";
  default: T;
  scope: "application" | "workspace" | "project" | "target";
  requiresRestart?: boolean;
  validation?: SettingValidation;
  owner: string;
}
```

Settings shall be searchable. Modified settings shall show scope, default, and source.

---

### 27. Empty, Loading, and Error States

#### Empty state

State what is empty and provide one relevant next action.

Good:

```text
No pin assignments match the current filter.
Clear filter
```

Bad:

```text
Nothing here yet!
```

#### Loading state

Use skeleton rows for tables and trees. Use progress indicators for explicit operations. Do not block unrelated panels.

#### Error state

Show:

- what failed;
- impact;
- likely cause when known;
- relevant diagnostic code;
- retry action;
- open log action;
- recovery or fallback action.

Never replace technical errors with vague �sSomething went wrong�t messages.

---

### 28. Accessibility

Minimum requirements:

- WCAG 2.2 AA contrast;
- complete keyboard navigation;
- visible focus;
- screen-reader labels;
- non-color state cues;
- configurable font scaling;
- density controls;
- reduced-motion support;
- high-contrast theme;
- accessible canvas object list;
- accessible diagnostics;
- keyboard alternatives for drag operations.

Canvas tools shall provide a synchronized hierarchical object view so users are not forced to interact only through spatial graphics.

---

### 29. Motion

Motion shall be minimal and functional.

Allowed:

- panel open/close;
- tab movement;
- focus transition;
- route preview;
- progress activity;
- drag feedback.

Duration:

- micro interaction: `80–120 ms`;
- panel transition: `120–180 ms`;
- modal transition: `140–200 ms`.

Disable nonessential motion in reduced-motion mode.

---

### 30. Performance Requirements

Target performance on a typical engineering workstation:

- initial shell interactive: under `2 s` after process launch;
- panel switch: under `100 ms`;
- command palette open: under `50 ms`;
- local filter update: under `100 ms`;
- table scrolling: sustained `60 fps`;
- canvas pan/zoom: sustained `60 fps`;
- selection feedback: under `50 ms`;
- background task reporting: under `250 ms`;
- diagnostic appearance after validation: under `500 ms` for local checks.

Large datasets shall use virtualization. Long-running work shall run outside the UI thread.

---

### 31. Responsive and Minimum Window Behavior

Primary design target: `1920 A� 1080`.

Supported minimum desktop window: `1280 A� 720`.

Below minimum width:

- inspector collapses first;
- secondary side panels collapse next;
- toolbars move actions into overflow;
- bottom panel becomes tabbed overlay;
- navigation rail remains available;
- the main editor remains usable.

The desktop application is not required to transform into a card-based mobile interface.

---

### 32. Naming and Microcopy

Use engineering terminology consistently.

Preferred verbs:

- Open;
- Create;
- Add;
- Assign;
- Connect;
- Route;
- Validate;
- Generate;
- Build;
- Simulate;
- Program;
- Export;
- Compare;
- Apply;
- Revert;
- Remove;
- Delete.

Avoid vague labels:

- Do it;
- Go;
- Fix;
- Process;
- Magic;
- Smart action;
- Continue, when the actual operation can be named.

Messages shall state object and outcome.

Good:

```text
Generated 14 HDL files in build/generated/hdl.
```

Bad:

```text
Generation complete.
```

---

### 33. Visual Review Checklist

A view is acceptable only when:

- the primary object is immediately identifiable;
- the current project and target are visible;
- selection is unambiguous;
- source and generated data are distinguishable;
- error, warning, and dirty states are distinguishable;
- no essential action depends on hover;
- keyboard navigation is complete;
- labels do not overlap;
- tables remain usable with large datasets;
- canvas routes remain readable at normal zoom;
- plugin UI matches core density and tokens;
- the view works in light, dark, and high-contrast themes;
- resizing does not hide the primary workflow;
- loading, empty, and error states are implemented;
- long operations expose progress and cancellation;
- destructive actions identify their impact;
- all actions are registered commands.

---

### 34. Definition of Done for New GUI Features

A GUI feature is complete when it includes:

1. command registrations;
2. keyboard shortcuts where appropriate;
3. context conditions;
4. dense, standard, and comfortable layouts;
5. light and dark theme support;
6. high-contrast validation;
7. keyboard navigation;
8. screen-reader labels;
9. loading state;
10. empty state;
11. error state;
12. diagnostics integration;
13. undo/redo behavior;
14. persistence behavior;
15. plugin lifecycle cleanup;
16. automated component tests;
17. visual regression tests;
18. performance test with realistic data;
19. documentation;
20. acceptance against this `DESIGN.md`.

---

### 35. Canonical Desktop Composition

The canonical unified workspace shall use:

- a narrow global navigation rail;
- a compact hierarchy/project panel;
- a large central editor or engineering canvas;
- a context-sensitive inspector;
- a collapsible diagnostics/output panel;
- a persistent technical status bar;
- tabbed and split document groups;
- command-driven actions;
- shared tables, trees, forms, and diagnostics;
- plugin contributions that appear native to the platform.

The final experience should resemble a coherent engineering IDE/CAD workstation, not a collection of embedded web applications.

---

### 36. Non-Goals

The unified GUI shall not:

- imitate a marketing website;
- use card grids as the default information structure;
- hide technical state to appear simple;
- require a mouse for core workflows;
- allow plugins to ship isolated design systems;
- use modal dialogs for routine operations;
- silently modify generated or source files;
- sacrifice traceability for visual minimalism;
- replace precise engineering terms with generic consumer language;
- prioritize animation over response time.

---

### 37. Reference Component Inventory

Core shared components:

```text
ApplicationShell
CommandBar
NavigationRail
DockManager
Panel
DocumentTabs
SplitView
StatusBar
TreeView
DataGrid
PropertyGrid
Inspector
FormField
UnitInput
CodeEditor
EngineeringCanvas
MiniMap
Breadcrumbs
Toolbar
CommandPalette
ContextMenu
ProblemsView
OutputView
TerminalView
TaskProgress
NotificationCenter
Dialog
DiffViewer
ObjectPicker
TargetSelector
ProjectSelector
ConnectionIndicator
DiagnosticBadge
GeneratedBadge
DirtyIndicator
```

No plugin should reimplement these components unless a capability gap is documented and accepted into the core design system.

---

### 38. Recommended Initial Theme

The default theme should be a neutral dark engineering theme:

- low-glare dark gray application background;
- slightly lighter panels;
- subtle borders;
- off-white primary text;
- muted secondary text;
- restrained blue focus/accent;
- green success;
- amber warning;
- red error;
- cyan or violet generated/derived state;
- no gradients;
- no glass effects;
- no oversized shadows.

A corresponding light theme shall preserve the same semantic hierarchy and density.

---

### 39. Governance

Changes to this document require review from:

- platform architecture;
- UI engineering;
- accessibility;
- at least one domain-tool owner;
- plugin API owner.

A plugin-specific exception must document:

- reason;
- affected component;
- user benefit;
- accessibility impact;
- maintenance cost;
- migration path back to the shared pattern.

The shared design system is the default. Exceptions are temporary and explicit.


---

## Diagram Layout Safety Rules

**Original file:** `DIAGRAM_LAYOUT_SAFETY_RULES.md`  
**SHA-256:** `d0c783b2c3f1342521d981b92e1fd6b910a72f54ac0971d9761bee08f4ea6adf`

## Generic Diagram Layout Safety Rules

**Document:** `DIAGRAM_LAYOUT_SAFETY_RULES.md`  
**Status:** Normative  
**Applies to:** node editors, block diagrams, schematics, HDL diagrams, routing views, topology canvases, generated screenshots, plugin-provided diagram elements  
**Primary objective:** make text, ports, routes, badges, and node content non-overlapping by construction

---

### 1. Scope

These rules prevent recurring layout defects such as:

- port labels overlapping node content;
- two labels occupying the same visual lane;
- arrowheads terminating underneath nodes or ports;
- route labels covering ports, nodes, or other labels;
- content shifting into reserved connector areas;
- text becoming unreadable after zoom, localization, density changes, or font loading;
- screenshots being accepted even though the actual geometry is invalid.

These rules are not visual recommendations. They are implementation constraints and release gates.

---

### 2. Core Principle

No diagram element may be positioned only by visual approximation.

Every visible object shall have a measured bounding rectangle:

```ts
type Rect = {
  x: number;
  y: number;
  width: number;
  height: number;
};
```

The renderer shall derive the final layout from measured geometry, not from fixed text offsets.

The layout sequence shall always be:

```text
measure
→ allocate zones
→ place content
→ place ports and labels
→ route connections
→ detect collisions
→ resolve collisions
→ validate
→ render
→ capture screenshot
```

A screenshot shall never be used as proof of correctness without geometric validation.

---

### 3. Mandatory Node Zones

Every node shall be divided into explicit, non-overlapping zones.

```text
�S────────────────────────────────────────────┐
│ Header zone                                │
�s───────────────┬────────────────────────────┤
│ Left port lane│ Content safe area          │
│               │                            │
│               │                            │
�s───────────────┴────────────────────────────┤
│ Footer/status zone                         │
└────────────────────────────────────────────�?
```

Optional right, top, and bottom port lanes may also exist.

Required zones:

```ts
interface NodeLayoutZones {
  outerRect: Rect;
  headerRect: Rect;
  contentRect: Rect;
  footerRect?: Rect;
  leftPortLane?: Rect;
  rightPortLane?: Rect;
  topPortLane?: Rect;
  bottomPortLane?: Rect;
}
```

Rules:

1. Port labels shall not be rendered inside `contentRect`.
2. Content rows shall not be rendered inside a port lane.
3. Badges shall remain inside `headerRect`.
4. Routes shall not cross `contentRect`.
5. The node shall grow when its required zones do not fit.

---

### 4. Reserved Port Lane Rule

A node side containing ports shall reserve a dedicated port lane.

The lane width shall be calculated from the longest visible port label:

```ts
portLaneWidth =
  outerGap +
  portDiameter +
  portToLabelGap +
  maxVisiblePortLabelWidth +
  contentGap;
```

Minimum recommended values at standard density:

```text
outer gap:          4 px
port diameter:      8 px
port-to-label gap:  6 px
content gap:       12 px
minimum lane:      56 px
```

The content safe area begins only after the complete port lane.

Invariant:

```text
leftPortLabel.right + minimumContentGap <= contentRect.left
```

For right-side ports:

```text
contentRect.right + minimumContentGap <= rightPortLabel.left
```

This invariant must be checked programmatically.

---

### 5. Port Label Placement

A port label shall occupy one of these legal positions:

1. outside the node, aligned with the port;
2. inside a reserved port lane;
3. in a dedicated port row spanning the node width.

A port label shall never be placed over a normal property row.

Preferred direction:

| Port side | Preferred label placement |
|---|---|
| Left | immediately right of port, inside left port lane |
| Right | immediately left of port, inside right port lane |
| Top | below port, inside top port lane |
| Bottom | above port, inside bottom port lane |

If the preferred placement collides, the layout engine shall try, in order:

1. expand the port lane;
2. expand the node;
3. move the label outside the node;
4. stack the port label in a dedicated row;
5. abbreviate only when a full tooltip remains available.

The renderer shall not accept overlap as a fallback.

---

### 6. Node Auto-Sizing

Node dimensions shall be content-derived.

```ts
nodeWidth = max(
  configuredMinimumWidth,
  headerRequiredWidth,
  leftPortLaneWidth + contentRequiredWidth + rightPortLaneWidth,
  footerRequiredWidth
);

nodeHeight = max(
  configuredMinimumHeight,
  headerHeight +
  max(contentRequiredHeight, portStackRequiredHeight) +
  footerHeight
);
```

Rules:

- fixed node sizes may define a minimum, not an absolute maximum;
- node dimensions shall expand for long labels;
- node dimensions shall expand after font metrics become available;
- node dimensions shall be recalculated after density or locale changes;
- clipping shall not substitute for layout unless explicitly configured by the user.

---

### 7. Text Measurement

All labels shall be measured using the exact rendered font, weight, size, and letter spacing.

Do not estimate label width from character count.

Required flow:

```ts
await document.fonts.ready;
const metrics = measureText(label, fontDescriptor);
```

The layout shall be recalculated when:

- web fonts finish loading;
- application font changes;
- zoom changes;
- operating-system text scaling changes;
- density changes;
- locale changes;
- a label changes;
- a badge appears or disappears;
- a plugin contributes new content.

---

### 8. Text Overflow Policy

Text handling priority:

1. expand available space;
2. wrap where semantically valid;
3. use a second line;
4. abbreviate using a domain-approved abbreviation;
5. truncate with ellipsis and full tooltip.

Never:

- draw text outside its assigned rectangle;
- allow two text rectangles to overlap;
- reduce font size below the application minimum to force a fit;
- hide a port label that identifies a live connection;
- place transparent text over another field.

Minimum readable sizes:

```text
desktop default: 12 px
dense metadata:  11 px
absolute minimum: 10 px
```

---

### 9. Content Row Grid

Node body content shall use a structured grid.

Recommended model:

```css
.node-content-row {
  display: grid;
  grid-template-columns:
    minmax(72px, max-content)
    minmax(0, 1fr);
  column-gap: 12px;
  min-height: 24px;
  align-items: center;
}
```

Rules:

- property names and values shall use separate columns;
- port labels shall not participate in the property grid;
- value text may truncate, but its full value shall be available;
- columns shall not be positioned using arbitrary absolute offsets;
- content rows shall remain inside `contentRect`.

---

### 10. Port Stack Spacing

Ports on the same side shall be vertically separated.

```ts
minimumPortCenterDistance =
  max(
    portDiameter + 8,
    max(labelHeightA, labelHeightB) + 6
  );
```

If the required stack does not fit:

1. increase node height;
2. group compatible ports into a bus;
3. collapse optional ports;
4. introduce scrolling only for specialized inspectors, never ordinary nodes.

Ports shall not be compressed until their labels collide.

---

### 11. Connector Endpoint Rule

A connector shall terminate at the visible perimeter of the port, not at the node center and not underneath the node.

For a circular destination port:

```ts
visibleEndpoint =
  portCenter - normalize(incomingVector) * portRadius;
```

If an arrow marker is used:

```ts
pathEndpoint =
  visibleEndpoint - normalize(incomingVector) * markerTipInset;
```

The marker tip, not merely the SVG path endpoint, shall visually touch the port perimeter.

Required invariant:

```text
distance(markerTip, destinationPortPerimeter) <= 1 px
```

At high-DPI scaling, tolerance may be:

```text
max(1 CSS px, 1 physical pixel)
```

---

### 12. Connector Exit Rule

The first route segment shall exit perpendicular to the source side.

Examples:

- left-side port: first segment travels left;
- right-side port: first segment travels right;
- top-side port: first segment travels up;
- bottom-side port: first segment travels down.

The same applies to the final approach into the destination.

Minimum straight segment next to a port:

```text
12 px compact
16 px standard
20 px comfortable
```

This prevents an immediate bend from visually covering the port label.

---

### 13. Connector Keep-Out Areas

Each node creates a route keep-out rectangle:

```ts
routeKeepOut = inflate(node.outerRect, routeClearance);
```

Recommended clearance:

```text
compact:     6 px
standard:   10 px
comfortable:14 px
```

Each text label also creates a keep-out rectangle:

```ts
labelKeepOut = inflate(label.rect, 4 px);
```

Routes may not cross:

- node content;
- node header text;
- port labels;
- badges;
- route labels;
- domain titles;
- active selection handles.

Exceptions require an explicit crossing style, such as a bridge or jump.

---

### 14. Route Label Placement

Route labels shall be placed only on segments that satisfy all conditions:

```text
segment length >= label width + 2 A� label padding
segment is not inside a node keep-out area
segment is not adjacent to a port
segment does not overlap another label
segment is not under a selection handle
```

Preferred route-label order:

1. longest horizontal segment;
2. longest vertical segment;
3. dedicated label leader;
4. suppress optional metadata.

Route labels shall never be placed directly over a port label.

---

### 15. Collision Detection

The layout engine shall test collisions between these classes:

```text
port label ↔ content row
port label ↔ port label
port label ↔ badge
route label ↔ route label
route label ↔ node
route label ↔ port label
route ↔ node
route ↔ label
badge ↔ title
title ↔ subtitle
content row ↔ content row
selection handles ↔ text
```

Rectangle overlap:

```ts
function overlaps(a: Rect, b: Rect, gap = 0): boolean {
  return !(
    a.x + a.width + gap <= b.x ||
    b.x + b.width + gap <= a.x ||
    a.y + a.height + gap <= b.y ||
    b.y + b.height + gap <= a.y
  );
}
```

A positive safety gap shall be used for text:

```text
text-to-text:      4 px
text-to-icon:      4 px
text-to-port:      6 px
text-to-route:     6 px
content-to-lane:  12 px
```

---

### 16. Collision Resolution Priority

When a collision is found, resolve it in this order:

1. move the lower-priority label inside its legal zone;
2. increase local padding;
3. expand the node;
4. move the port to the next legal slot;
5. reroute the connector;
6. move the route label;
7. wrap or abbreviate optional text;
8. hide optional metadata.

Never resolve a collision by:

- reducing opacity;
- changing z-index so one item covers another;
- rendering one label above another;
- moving content outside its assigned zone;
- accepting the overlap because it is �ssmall.�t

---

### 17. Z-Order Rules

Recommended render order:

```text
canvas background
grid
domain containers
routes
route labels
nodes
node content
ports
port labels
selection overlays
drag overlays
tooltips
```

Important:

- ports and port labels shall remain above routes;
- arrowheads shall not be hidden beneath node bodies;
- z-index shall not be used to conceal geometric errors;
- all overlapping text remains a failure even if one label is visually on top.

---

### 18. Dynamic Update Triggers

The complete geometry pipeline shall rerun after:

- node drag;
- node resize;
- panel resize;
- canvas resize;
- zoom;
- font load;
- density change;
- theme change when typography changes;
- label edit;
- port add/remove;
- route add/remove;
- inspector-driven property edit;
- plugin activation/deactivation;
- localization;
- device-pixel-ratio change;
- window movement between monitors;
- browser zoom;
- undo/redo;
- loading a saved workspace.

Updates shall be scheduled through a single layout coordinator.

```ts
requestLayout({
  reason: "node-drag",
  affectedNodes: [nodeId],
  affectedRoutes: connectedRouteIds
});
```

Avoid independent components changing positions without triggering route and collision recalculation.

---

### 19. Layout Stabilization

A screenshot or export shall wait until the layout is stable.

Stable means:

```text
fonts loaded
all nodes measured
all ports measured
all routes recalculated
collision pass completed
no pending ResizeObserver callback
no pending animation frame affecting geometry
no pending asynchronous plugin contribution
```

Suggested API:

```ts
await layoutEngine.waitForStable({
  consecutiveStableFrames: 2,
  timeoutMs: 3000
});
```

Do not capture immediately after page load or after changing iteration state.

---

### 20. Screenshot Acceptance Gate

Every generated screenshot shall pass automated geometry checks before publication.

Required checks:

```text
zero text-to-text overlaps
zero port-label-to-content overlaps
zero connector-to-node penetrations
zero hidden arrowheads
all active routes attached to source and destination
all visible ports have readable labels
all visible labels remain inside canvas or legal node zones
```

A screenshot shall fail if any overlap area exceeds:

```text
1 CSS pixel�?
```

For anti-aliasing tolerance, edge touching is allowed, but rectangle intersection is not.

The screenshot filename shall include a unique version or content hash to prevent stale-cache confusion.

Example:

```text
iteration-1-shell-v3-8f13c2.png
```

---

### 21. Geometric Validation API

Recommended validation result:

```ts
interface LayoutValidationResult {
  valid: boolean;
  overlaps: Array<{
    aId: string;
    bId: string;
    area: number;
    severity: "error" | "warning";
  }>;
  detachedEndpoints: Array<{
    routeId: string;
    endpoint: "source" | "destination";
    distancePx: number;
  }>;
  outOfBounds: string[];
  hiddenLabels: string[];
}
```

Release condition:

```ts
if (!result.valid) {
  throw new Error("Layout validation failed");
}
```

Do not merely log layout failures.

---

### 22. Runtime Development Overlay

Provide a debug mode that draws:

- node outer rectangles;
- content safe rectangles;
- port lanes;
- text bounding boxes;
- route keep-out rectangles;
- collision areas;
- route endpoint normals;
- marker-tip positions.

Example toggle:

```text
View → Developer → Show Layout Bounds
```

Colors should distinguish:

```text
green: legal bounds
yellow: minimum-gap violation
red: overlap
magenta: detached endpoint
```

This overlay shall be available in development builds and screenshot CI.

---

### 23. Automated Test Matrix

Every node type shall be tested across:

#### Text cases

- shortest names;
- longest expected names;
- uppercase identifiers;
- lowercase identifiers;
- numeric-heavy labels;
- Unicode;
- Hungarian;
- German;
- CJK;
- RTL text where supported.

#### Display cases

- 100%, 125%, 150%, and 200% OS scaling;
- browser/application zoom from 75% to 200%;
- compact, standard, comfortable density;
- light, dark, high-contrast themes;
- narrow and wide node widths;
- multiple monitor DPI values.

#### Content cases

- zero ports;
- one port;
- maximum supported port count;
- long port names;
- badges enabled and disabled;
- diagnostics enabled;
- generated-state marker;
- selection state;
- hover state;
- plugin-added fields.

#### Interaction cases

- drag every node;
- resize every dock panel;
- zoom and pan;
- collapse and expand nodes;
- add and remove routes;
- edit labels live;
- undo and redo;
- save and restore workspace.

---

### 24. Property-Based Layout Tests

Generate random but valid node content:

```ts
for (const seed of seeds(0, 1000)) {
  const node = randomNode(seed);
  const layout = layoutNode(node);
  const result = validateLayout(layout);

  expect(result.overlaps).toHaveLength(0);
  expect(result.detachedEndpoints).toHaveLength(0);
}
```

Randomize:

- label lengths;
- port counts;
- port sides;
- content row counts;
- badge widths;
- font scaling;
- node widths;
- route directions.

This catches cases not represented by handcrafted screenshots.

---

### 25. Visual Regression Tests

Visual regression is supplemental, not the primary geometry test.

Required process:

1. run geometric validation;
2. capture screenshot only if geometry is valid;
3. compare screenshot against approved baseline;
4. manually review changes above threshold;
5. store layout validation JSON next to each screenshot.

Recommended artifacts:

```text
screenshots/iteration-1-v3.png
screenshots/iteration-1-v3.validation.json
screenshots/iteration-1-v3.diff.png
```

---

### 26. Component Contract

Every diagram node component shall expose:

```ts
interface DiagramNodeComponent {
  measure(context: MeasureContext): NodeMeasurements;
  layout(measurements: NodeMeasurements): NodeLayoutZones;
  getPorts(): PortDefinition[];
  getObstacles(): Rect[];
  getTextBounds(): Array<{ id: string; rect: Rect }>;
  validate(): LayoutValidationResult;
}
```

Plugins shall not provide nodes that bypass these methods.

A plugin node that cannot produce geometry metadata shall not be allowed on the production canvas.

---

### 27. Safe CSS Rules

Prefer CSS Grid or Flexbox inside node bodies.

Avoid absolute positioning for ordinary text.

Allowed absolute positioning:

- ports;
- connection handles;
- selection handles;
- canvas nodes;
- route labels after collision-aware placement.

Unsafe pattern:

```css
.port-label {
  position: absolute;
  left: 8px;
  top: 54px;
}
```

Preferred pattern:

```css
.node-body {
  display: grid;
  grid-template-columns:
    var(--left-port-lane-width)
    minmax(0, 1fr)
    var(--right-port-lane-width);
}

.left-port-lane {
  grid-column: 1;
}

.node-content {
  grid-column: 2;
}
```

---

### 28. Safe Port Row Pattern

Recommended HTML structure:

```html
<div class="node">
  <header class="node-header">...</header>

  <div class="node-body">
    <div class="port-lane port-lane-left">
      <div class="port-row">
        <span class="port-handle"></span>
        <span class="port-label">SPI3_TX</span>
      </div>
    </div>

    <div class="node-content">
      <div class="node-content-row">
        <span>Part</span>
        <span>XC7A35T</span>
      </div>
    </div>
  </div>
</div>
```

The port row and content grid are siblings, not overlapping layers.

---

### 29. Minimum Node Template

Recommended dimensions at standard density:

```text
header height:             44 px
content row height:        24 px
footer height:             24 px
horizontal inner padding:  12 px
vertical inner padding:     8 px
port lane minimum width:   72 px
port circle diameter:       8 px
port-label gap:             6 px
lane-to-content gap:       12 px
```

These are defaults. Measured content may increase them.

---

### 30. Domain Label Rule

Domain titles such as `CONTROL DOMAIN` and `POWER DOMAIN` shall have their own keep-out area.

Nodes and routes shall maintain:

```text
minimum vertical gap below domain title: 16 px
minimum horizontal gap from title:       12 px
```

Domain lines shall not cross node headers or route labels.

---

### 31. Selection and Hover Rule

Selection outlines and handles shall be rendered outside the node’s measured content bounds.

Selection state shall not alter text position.

Hover state shall not:

- insert new text without reserving space;
- change border width in a way that shifts layout;
- change font weight if it changes measured width;
- expand badges over neighboring labels.

Use outline or box-shadow instead of changing element dimensions.

---

### 32. Badge Rule

Header badges shall occupy a dedicated right-aligned badge area.

The title/subtitle area shall have a maximum width derived from the remaining header space.

Invariant:

```text
titleRect.right + headerGap <= badgeRect.left
```

If it does not fit:

1. increase node width;
2. move secondary badges to a second header row;
3. abbreviate optional badge text.

Do not overlap the title.

---

### 33. Responsive Rule

When available width decreases:

1. preserve port labels;
2. preserve node title;
3. preserve primary values;
4. truncate secondary metadata;
5. collapse optional footer fields;
6. increase node height if wrapping is allowed.

Do not shrink port lanes below their measured requirement.

---

### 34. Localization Rule

No layout may assume English string lengths.

The localization test shall use expansion pseudo-localization:

```text
Original: Configuration
Expanded: [!! Coonffiigguurraattiioonn !!]
```

All nodes and panels shall remain collision-free at approximately 150% text expansion.

---

### 35. Plugin Enforcement

Plugin-contributed nodes shall:

- use platform node templates;
- declare all ports;
- provide label measurement data;
- expose obstacles;
- pass collision validation;
- respond to density and zoom;
- use semantic font and spacing tokens;
- pass the standard test matrix.

The host shall reject plugin UI contributions that report invalid layout geometry.

---

### 36. Build and CI Gates

A pull request changing diagram layout shall fail CI when:

- any overlap is detected;
- any route endpoint is detached;
- any label is outside its legal zone;
- any screenshot is captured before layout stability;
- any node type lacks property-based tests;
- any approved screenshot lacks validation JSON;
- any plugin node bypasses the geometry contract.

Recommended CI sequence:

```text
unit tests
→ property-based layout tests
→ browser interaction tests
→ geometry validation
→ screenshot capture
→ visual regression
→ package
```

---

### 37. Definition of Done

A diagram feature is complete only when:

1. all text has measured bounds;
2. every node has explicit layout zones;
3. every port side has a reserved lane;
4. content does not enter port lanes;
5. all routes terminate on visible port perimeters;
6. route labels avoid all keep-out areas;
7. node size responds to content;
8. font loading triggers relayout;
9. density and localization tests pass;
10. drag and resize tests pass;
11. no geometric overlaps exist;
12. validation JSON is generated;
13. screenshots use unique names;
14. visual regression passes;
15. debug layout overlay shows no red regions.

---

### 38. Non-Negotiable Invariants

These invariants shall be implemented as assertions:

```text
A. Port-label rectangles never intersect content rectangles.
B. Text rectangles never intersect other text rectangles.
C. Connector paths never enter node content rectangles.
D. Arrow tips terminate on the visible port perimeter.
E. Node dimensions grow when measured content does not fit.
F. Screenshot capture waits for stable geometry.
G. A failed layout validator blocks export and release.
```

If one of these invariants fails, the application shall report a layout error rather than render an ambiguous diagram.

---

### 39. Recommended Diagnostic Codes

```text
LAYOUT-0001  Port label overlaps node content
LAYOUT-0002  Text labels overlap
LAYOUT-0003  Connector enters node keep-out area
LAYOUT-0004  Connector endpoint detached from port
LAYOUT-0005  Route label has no legal placement
LAYOUT-0006  Node content exceeds allocated bounds
LAYOUT-0007  Layout did not stabilize before capture
LAYOUT-0008  Plugin node lacks geometry metadata
LAYOUT-0009  Minimum spacing invariant violated
LAYOUT-0010  Screenshot validation failed
```

Diagnostics shall identify both elements, their rectangles, and the measured overlap.

---

### 40. Final Rule

Never solve diagram overlap defects manually per screenshot.

The permanent solution is:

```text
explicit zones
+ exact measurement
+ reserved lanes
+ automatic growth
+ collision-aware routing
+ geometric validation
+ CI enforcement
```

Any renderer that cannot prove these conditions shall not be treated as production-ready.


---

## Layout Safety Implementation

**Original file:** `LAYOUT_SAFETY_IMPLEMENTATION.md`  
**SHA-256:** `96d5a134fa5c512e963732902f9431948a826805321cbd7f310152bb6e792d1b`

## Layout Safety Implementation

### Structural change

Every node uses sibling layout zones rather than overlapping layers:

```text
header
left port lane | content-safe area | right port lane
top or bottom port lane when required
```

Port labels and property rows therefore cannot occupy the same rectangle.

### Measurement

`measureNode()` reads the exact rendered font metrics after `document.fonts.ready`, calculates lane widths from the longest label, calculates the content width from property labels and values, and expands the node when the minimum geometry cannot fit.

### Routing

Routes begin and end on the visible perimeter of the port circle. The first segment exits in the port's outward normal direction and the final segment approaches from the opposite direction. The validator requires a minimum endpoint stub and measures endpoint error.

### Label placement

Route labels are tested against node, port-label, domain-title, and previously placed route-label keep-out boxes. Multiple segment positions are tried. When the full label cannot legally fit, a predefined compact engineering label is used and the full label remains in the SVG title tooltip.

### Validation gate

The gate rejects:

- port label versus content overlap;
- text versus text overlap;
- route versus unrelated node intersection;
- detached endpoint;
- missing route label;
- invalid endpoint stub;
- node outside the legal canvas area.

Screenshot capture waits for multiple stable animation frames and fails immediately if the gate is not green.


---

## Iteration Record

**Original file:** `ITERATIONS.md`  
**SHA-256:** `b28bf6ddbba505d03f0e050da5403f8e69abcfc53e311b66b7ae33cc20305073`

## Iteration Record

### Iteration 1 — Workstation shell

Established the six-region engineering application shell from `DESIGN.md`: compact command bar, navigation rail, project tree, central design canvas, inspector, diagnostics/output panel, and status bar.

Screenshot: `screenshots/iteration-1-shell.png`

### Iteration 2 — Live arrow routing

Replaced static SVG paths with routes computed from the actual center position of each port. Added draggable nodes, automatic SVG viewport sizing, route labels, route type styling, and continuous recalculation through `ResizeObserver` and pointer movement.

Screenshot: `screenshots/iteration-2-routing.png`

### Iteration 3 — Production interaction pass

Added four-sided ports, collision-aware candidate path selection, route scoring, selected-route animation, route and node inspector synchronization, minimap rendering, fit-layout action, obstacle toggle, resizable/collapsible panels, improved label placement, and a fifth fieldbus route.

Screenshot: `screenshots/iteration-3-final.png`


---

## Connector Rendering Fix Report

**Original file:** `FIX_REPORT.md`  
**SHA-256:** `8a75bb7307ede3cacaa7d182378a26e5e69f3d3d22da4e713a60dce0c507f2b5`

## Connector Rendering Fix — V2

### Reported issue

The first iteration screenshot showed arrowheads that appeared detached from their ports. Replacing the image at the same path also allowed the client to continue displaying a cached copy.

### Root cause

The SVG path ended at the center of the destination port. Because nodes and ports render above the SVG connection layer, the final part of the marker was hidden beneath the port/node. The visible remainder looked like a floating arrowhead. Iteration 1 also exposed ports that had no active route.

### Implemented fix

- Route endpoints now terminate at the outer perimeter of each source and destination port.
- Arrow marker tips remain outside the node layer and visibly touch the destination port.
- Only ports participating in an active route are shown in staged screenshots.
- Iteration 1 was simplified to three visible nodes and two unambiguous routes.
- Iteration screenshots now use new V2 filenames to prevent stale-cache reuse.
- Legacy screenshot filenames are also overwritten with byte-identical V2 captures.

### Validation

Iteration 1:

- Visible nodes: 3
- Visible ports: 4
- Active routes: 2
- Maximum route-to-port-perimeter error: 0 px
- SVG marker present on both routes: yes
- JavaScript page errors: none
- Both route paths changed after moving destination nodes: yes
- Anchor error after moving nodes: 0 px

Machine-readable reports:

- `screenshots/validation-v2.json`
- `screenshots/live-reroute-validation-v2.json`


---

## Original Smoke Test Report

**Original file:** `TEST_REPORT.md`  
**SHA-256:** `1fe400b9781ee1b964b7251fa34c92b3df4e901f116b1c70dd264c3ef2bba390`

## Smoke Test Report

Result: **PASS**

Validated in a 1920A�1080 Chromium viewport:

- five engineering nodes render;
- five SVG routes render;
- dragging the FPGA node changes live route geometry;
- selecting a route updates the inspector;
- dragging the explorer splitter changes panel width;
- collapsing the bottom panel changes workspace state;
- no JavaScript page errors were emitted.


---

## Layout Safety Test Report

**Original file:** `TEST_REPORT_LAYOUT_SAFETY.md`  
**SHA-256:** `58ecace276995684e8c3556d5dd88c2a915657239c7eb83f78406ad1e0ba636f`

## Layout Safety Test Report

**Result:** PASS

Validated viewports:

| Viewport | Overlaps | Detached endpoints | Node penetrations | Missing labels | Stub violations |
|---|---:|---:|---:|---:|---:|
| 1672A�941 | 0 | 0 | 0 | 0 | 0 |
| 1440A�900 | 0 | 0 | 0 | 0 | 0 |
| 1280A�720 | 0 | 0 | 0 | 0 | 0 |

The 1672A�941 test additionally moved the Artix-7 and Power Stage nodes, waited for dynamic rerouting and layout stabilization, and re-ran the same gate. It passed with zero violations.

Measured application objects:

- 4 nodes;
- 10 ports;
- 4 live routes;
- maximum endpoint error: 0 px;
- JavaScript page errors: 0.

Machine-readable evidence is stored in `screenshots/iteration-4-validation.json`.


---

## Included Source Files

- `/mnt/data/unified-engineering-gui-demo/README.md` — `a001050d973d65998bf1594cffb388d9c2a6a322e64bbd91871748a24faa7682`
- `/mnt/data/unified-engineering-gui-demo/DESIGN.md` — `3ef867c54c743d7d1c1a2eafff2ee5462719c8e013a630faba03833af1dc6d0d`
- `/mnt/data/DIAGRAM_LAYOUT_SAFETY_RULES.md` — `d0c783b2c3f1342521d981b92e1fd6b910a72f54ac0971d9761bee08f4ea6adf`
- `/mnt/data/unified-engineering-gui-demo/LAYOUT_SAFETY_IMPLEMENTATION.md` — `96d5a134fa5c512e963732902f9431948a826805321cbd7f310152bb6e792d1b`
- `/mnt/data/unified-engineering-gui-demo/ITERATIONS.md` — `b28bf6ddbba505d03f0e050da5403f8e69abcfc53e311b66b7ae33cc20305073`
- `/mnt/data/unified-engineering-gui-demo/FIX_REPORT.md` — `8a75bb7307ede3cacaa7d182378a26e5e69f3d3d22da4e713a60dce0c507f2b5`
- `/mnt/data/unified-engineering-gui-demo/TEST_REPORT.md` — `1fe400b9781ee1b964b7251fa34c92b3df4e901f116b1c70dd264c3ef2bba390`
- `/mnt/data/unified-engineering-gui-demo/TEST_REPORT_LAYOUT_SAFETY.md` — `58ecace276995684e8c3556d5dd88c2a915657239c7eb83f78406ad1e0ba636f`
