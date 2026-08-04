# Route Core

Route Core is deliberately headless. It exposes generic geometry services that can be reused by OpenHDL Designer, wiring-harness editors, block diagrams and future PCB-oriented plugins.

The initial algorithm uses deterministic A* search over an orthogonal grid. State includes the incoming direction so bend penalties are represented in the cost function. Obstacles are expanded by clearance before search.
