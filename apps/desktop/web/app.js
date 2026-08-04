const state = {
  catalog: { plugins: [], generatedAt: null, platformApiVersion: "0.1.0" },
  selectedPluginId: null,
  activeView: "start",
  output: ["CodeLayer Forge initialized.", "Plugin runtime is ready."],
  latestResult: null,
};

const demoArguments = {
  "hu.codelayer.pin-configurator": {
    pins: [
      { name: "A1", capabilities: ["GPIO", "UART_TX", "SPI_MOSI"] },
      { name: "A2", capabilities: ["GPIO", "UART_RX", "SPI_MISO"] },
      { name: "A3", capabilities: ["GPIO", "SPI_SCK", "I2C_SCL"] },
      { name: "A4", capabilities: ["GPIO", "SPI_CS", "I2C_SDA"] },
      { name: "B1", capabilities: ["GPIO", "PWM"] },
      { name: "VCC", capabilities: ["POWER"], reserved: true },
    ],
    signals: [
      { id: "uart_tx", requires: ["UART_TX"], preferred: ["A1"] },
      { id: "uart_rx", requires: ["UART_RX"], preferred: ["A2"] },
      { id: "status_led", requires: ["GPIO"], preferred: ["B1", "A4"] },
    ],
  },
  "hu.codelayer.route-core": {
    source: { x: 20, y: 40 },
    target: { x: 420, y: 240 },
    obstacles: [{ x: 140, y: 20, width: 120, height: 180 }],
    grid: 10,
    clearance: 10,
    bendPenalty: 30,
  },
  "hu.codelayer.openhdl-designer": {
    name: "motor_control_top",
    topPorts: [
      { name: "clk", direction: "input" },
      { name: "enable", direction: "input" },
      { name: "pwm", direction: "output" },
    ],
    nodes: [
      {
        id: "controller",
        module: "pwm_controller",
        sequential: true,
        ports: { inputs: ["clk", "enable"], outputs: ["pwm_out"] },
        parameters: { PERIOD: 1000 },
      },
    ],
    nets: [
      { from: "top.clk", to: "controller.clk" },
      { from: "top.enable", to: "controller.enable" },
      { from: "controller.pwm_out", to: "top.pwm" },
    ],
  },
  "hu.codelayer.pyontust-adapter": {
    workflow: {
      name: "demo-artifact-flow",
      steps: [
        { id: "check", action: "validate-json", value: { project: "forge", valid: true } },
        { id: "message", action: "render-template", template: "Build {project} completed" },
      ],
    },
    variables: { project: "CodeLayer Forge" },
  },
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function pluginManifest(plugin) {
  return plugin.manifest ?? plugin;
}

function pluginRoot(plugin) {
  return plugin.root ?? "";
}

async function invokeTauri(command, args = {}) {
  const invoke = window.__TAURI__?.core?.invoke ?? window.__TAURI_INTERNALS__?.invoke;
  if (!invoke) return null;
  return invoke(command, args);
}

async function loadCatalog() {
  try {
    const discovered = await invokeTauri("discover_plugins", { pluginsRoot: "plugins" });
    if (Array.isArray(discovered) && discovered.length) {
      state.catalog.plugins = discovered;
      state.output.push(`Discovered ${discovered.length} plugins through the desktop host.`);
      return;
    }
  } catch (error) {
    state.output.push(`Desktop discovery fallback: ${error}`);
  }

  const response = await fetch("catalog.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`catalog request failed: ${response.status}`);
  state.catalog = await response.json();
  state.output.push(`Loaded ${state.catalog.plugins.length} plugins from the static catalog.`);
}

function workbenches() {
  return state.catalog.plugins.flatMap((plugin) => {
    const manifest = pluginManifest(plugin);
    return (manifest.contributes?.workbenches ?? []).map((workbench) => ({
      ...workbench,
      pluginId: manifest.id,
      pluginName: manifest.name,
    }));
  }).sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
}

function commands() {
  return state.catalog.plugins.flatMap((plugin) => {
    const manifest = pluginManifest(plugin);
    return (manifest.contributes?.commands ?? []).map((command) => ({
      ...command,
      pluginId: manifest.id,
      pluginName: manifest.name,
    }));
  });
}

function selectedPlugin() {
  return state.catalog.plugins.find((plugin) => pluginManifest(plugin).id === state.selectedPluginId) ?? null;
}

function runtimeLetter(runtime) {
  return ({ python: "PY", native: "RS", wasm: "WA", webview: "UI" })[runtime] ?? "PL";
}

function permissionRows(manifest) {
  const permissions = manifest.permissions ?? {};
  const entries = [
    ["Workspace read", permissions.workspace_read],
    ["Workspace write", permissions.workspace_write],
    ["Network", permissions.network],
    ["Serial", permissions.serial],
    ["USB", permissions.usb],
  ];
  return entries.map(([name, enabled]) => `
    <div class="property">
      <span class="property-name">${escapeHtml(name)}</span>
      <span class="property-value permission"><span class="dot ${enabled ? "" : "off"}"></span>${enabled ? "Allowed" : "Denied"}</span>
    </div>`).join("");
}

function renderExplorer() {
  const items = workbenches().map((workbench) => `
    <div class="tree-row indent" data-open-plugin="${escapeHtml(workbench.pluginId)}">
      <span class="tree-bullet">◇</span>
      <span>${escapeHtml(workbench.title)}</span>
    </div>`).join("");
  return `
    <aside class="sidebar">
      <div class="panel-title"><span>Workspace</span><span>•••</span></div>
      <div class="explorer">
        <div class="tree-row"><span class="tree-bullet">▾</span><strong>DEMO-WORKSPACE</strong></div>
        <div class="tree-row indent"><span class="tree-bullet">▸</span><span>devices</span><span class="badge">1</span></div>
        <div class="tree-row indent"><span class="tree-bullet">▸</span><span>pin-plans</span><span class="badge">1</span></div>
        <div class="tree-row indent"><span class="tree-bullet">▾</span><span>hdl</span></div>
        <div class="tree-row indent muted"><span class="tree-bullet">&nbsp;</span><span>motor_control.hdlgraph</span></div>
        <div class="tree-row indent"><span class="tree-bullet">▸</span><span>routes</span></div>
        <div class="tree-row indent"><span class="tree-bullet">▸</span><span>constraints</span></div>
        <div class="tree-row"><span class="tree-bullet">▾</span><strong>WORKBENCHES</strong></div>
        ${items}
      </div>
    </aside>`;
}

function renderStart() {
  const plugins = state.catalog.plugins;
  const serviceCount = plugins.reduce((sum, plugin) => sum + Object.keys(pluginManifest(plugin).provides ?? {}).length, 0);
  const commandCount = commands().length;
  const cards = plugins.map((plugin) => {
    const manifest = pluginManifest(plugin);
    const provided = Object.keys(manifest.provides ?? {});
    return `
      <article class="card">
        <div class="card-header">
          <div class="plugin-icon">${runtimeLetter(manifest.runtime)}</div>
          <div>
            <h2>${escapeHtml(manifest.name)}</h2>
            <div class="metric-label">${escapeHtml(manifest.id)} · v${escapeHtml(manifest.version)}</div>
          </div>
        </div>
        <p>${escapeHtml(manifest.description)}</p>
        <div class="card-meta">
          <span class="pill">${escapeHtml(manifest.runtime)}</span>
          <span class="pill">${provided.length} services</span>
          <span class="pill">API ${escapeHtml(manifest.platform_api)}</span>
        </div>
        <div class="card-actions">
          <button class="primary-button" data-open-plugin="${escapeHtml(manifest.id)}">Open workbench</button>
          <button class="secondary-button" data-run-demo="${escapeHtml(manifest.id)}">Run demo</button>
        </div>
      </article>`;
  }).join("");

  return `
    <div class="hero">
      <div class="hero-heading">
        <div>
          <div class="eyebrow">Engineering platform</div>
          <h1>Build tools that work together.</h1>
          <p class="subtitle">A versioned, process-isolated workbench for pin planning, HDL design, orthogonal routing and engineering automation.</p>
        </div>
        <button class="primary-button" data-command-palette>Run command</button>
      </div>
      <div class="metric-grid">
        <div class="metric"><div class="metric-value">${plugins.length}</div><div class="metric-label">Installed plugins</div></div>
        <div class="metric"><div class="metric-value">${workbenches().length}</div><div class="metric-label">Workbenches</div></div>
        <div class="metric"><div class="metric-value">${serviceCount}</div><div class="metric-label">Versioned services</div></div>
        <div class="metric"><div class="metric-value">${commandCount}</div><div class="metric-label">Registered commands</div></div>
      </div>
      <div class="card-grid">${cards}</div>
      ${state.latestResult ? renderResult(state.latestResult) : ""}
    </div>`;
}

function renderPluginEditor(plugin) {
  const manifest = pluginManifest(plugin);
  const contributions = manifest.contributes ?? {};
  const services = Object.entries(manifest.provides ?? {});
  const commandRows = (contributions.commands ?? []).map((command) => `
    <div class="property">
      <span class="property-name">Command</span>
      <span class="property-value">${escapeHtml(command.id)}<br><small>${escapeHtml(command.title)}</small></span>
    </div>`).join("");
  const serviceRows = services.map(([name, version]) => `
    <div class="property">
      <span class="property-name">Service</span>
      <span class="property-value">${escapeHtml(name)} <span class="pill">${escapeHtml(version)}</span></span>
    </div>`).join("");
  return `
    <div class="hero">
      <div class="hero-heading">
        <div>
          <div class="eyebrow">${escapeHtml((contributions.workbenches ?? [])[0]?.title ?? "Headless service")}</div>
          <h1>${escapeHtml(manifest.name)}</h1>
          <p class="subtitle">${escapeHtml(manifest.description)}</p>
        </div>
        <button class="primary-button" data-run-demo="${escapeHtml(manifest.id)}">Run verified demo</button>
      </div>
      <div class="metric-grid">
        <div class="metric"><div class="metric-value">${services.length}</div><div class="metric-label">Provided services</div></div>
        <div class="metric"><div class="metric-value">${(contributions.commands ?? []).length}</div><div class="metric-label">Commands</div></div>
        <div class="metric"><div class="metric-value">${(contributions.views ?? []).length}</div><div class="metric-label">Contributed views</div></div>
        <div class="metric"><div class="metric-value">${manifest.runtime}</div><div class="metric-label">Runtime</div></div>
      </div>
      <div class="card-grid">
        <section class="card"><h2>Capabilities</h2>${serviceRows || "<p>No public services.</p>"}</section>
        <section class="card"><h2>Commands</h2>${commandRows || "<p>No commands.</p>"}</section>
      </div>
      ${state.latestResult ? renderResult(state.latestResult) : ""}
    </div>`;
}

function renderResult(result) {
  return `<section class="result-box"><div class="result-title">Latest command result</div><pre>${escapeHtml(JSON.stringify(result, null, 2))}</pre></section>`;
}

function renderInspector() {
  const plugin = selectedPlugin();
  if (!plugin) {
    return `
      <aside class="inspector">
        <div class="panel-title"><span>Platform</span><span>⚙</span></div>
        <div class="property-list">
          <div class="property"><span class="property-name">Product</span><span class="property-value">CodeLayer Forge</span></div>
          <div class="property"><span class="property-name">Version</span><span class="property-value">0.1.0</span></div>
          <div class="property"><span class="property-name">API</span><span class="property-value">${escapeHtml(state.catalog.platformApiVersion ?? "0.1.0")}</span></div>
          <div class="property"><span class="property-name">Isolation</span><span class="property-value">One process per plugin</span></div>
          <div class="property"><span class="property-name">Protocol</span><span class="property-value">JSON-RPC 2.0 / stdio</span></div>
        </div>
      </aside>`;
  }
  const manifest = pluginManifest(plugin);
  return `
    <aside class="inspector">
      <div class="panel-title"><span>Plugin</span><span>⚙</span></div>
      <div class="property-list">
        <div class="property"><span class="property-name">Identifier</span><span class="property-value">${escapeHtml(manifest.id)}</span></div>
        <div class="property"><span class="property-name">Version</span><span class="property-value">${escapeHtml(manifest.version)}</span></div>
        <div class="property"><span class="property-name">Runtime</span><span class="property-value">${escapeHtml(manifest.runtime)}</span></div>
        <div class="property"><span class="property-name">Root</span><span class="property-value">${escapeHtml(pluginRoot(plugin) || "bundled")}</span></div>
        ${permissionRows(manifest)}
      </div>
    </aside>`;
}

function renderCommandPalette() {
  return `
    <div class="modal-backdrop hidden" id="command-modal" role="dialog" aria-modal="true" aria-label="Command palette">
      <div class="modal">
        <input id="command-search" placeholder="Type a command" autocomplete="off" />
        <div class="command-list" id="command-list">
          ${commands().map((command) => `
            <div class="command-row" data-run-command="${escapeHtml(command.id)}" data-plugin-id="${escapeHtml(command.pluginId)}">
              <span>${escapeHtml(command.title)}</span>
              <span class="command-category">${escapeHtml(command.category ?? command.pluginName)}</span>
            </div>`).join("")}
        </div>
      </div>
    </div>`;
}

function render() {
  const plugin = selectedPlugin();
  document.querySelector("#app").innerHTML = `
    <div class="shell">
      <header class="titlebar">
        <div class="brand"><span class="brand-mark">CF</span><span>CodeLayer Forge</span></div>
        <button class="menu-button">File</button><button class="menu-button">Edit</button><button class="menu-button">View</button><button class="menu-button">Workbench</button><button class="menu-button">Help</button>
        <button class="command-trigger" data-command-palette><span>Search commands and workbenches</span><span class="shortcut">Ctrl K</span></button>
      </header>
      <main class="main-grid">
        <nav class="activity-bar" aria-label="Primary navigation">
          <button class="icon-button active" data-show-start title="Start">⌂</button>
          <button class="icon-button" title="Explorer">▱</button>
          <button class="icon-button" data-command-palette title="Commands">⌘</button>
          <button class="icon-button" title="Plugins">⬡</button>
          <div class="activity-spacer"></div>
          <button class="icon-button" title="Settings">⚙</button>
        </nav>
        ${renderExplorer()}
        <section class="editor-area">
          <div class="tabs">
            <div class="tab ${plugin ? "" : "active"}" data-show-start><span>◆</span>Start</div>
            ${plugin ? `<div class="tab active"><span>◇</span>${escapeHtml(pluginManifest(plugin).name)}</div>` : ""}
          </div>
          <div class="editor">${plugin ? renderPluginEditor(plugin) : renderStart()}</div>
        </section>
        ${renderInspector()}
        <section class="bottom-panel">
          <div class="bottom-tabs"><span class="active">Output</span><span>Problems</span><span>Tasks</span><span>Plugin Host</span></div>
          <pre class="console">${escapeHtml(state.output.join("\n"))}</pre>
        </section>
      </main>
      <footer class="statusbar"><span>◉ Ready</span><span>Workspace: demo-workspace</span><span>Plugins: ${state.catalog.plugins.length}</span><div class="status-right"><span>API ${escapeHtml(state.catalog.platformApiVersion ?? "0.1.0")}</span><span>UTF-8</span></div></footer>
      ${renderCommandPalette()}
    </div>`;
  attachEvents();
}

function attachEvents() {
  document.querySelectorAll("[data-open-plugin]").forEach((element) => {
    element.addEventListener("click", () => {
      state.selectedPluginId = element.dataset.openPlugin;
      state.latestResult = null;
      render();
    });
  });
  document.querySelectorAll("[data-show-start]").forEach((element) => {
    element.addEventListener("click", () => {
      state.selectedPluginId = null;
      state.latestResult = null;
      render();
    });
  });
  document.querySelectorAll("[data-run-demo]").forEach((element) => {
    element.addEventListener("click", () => runDemo(element.dataset.runDemo));
  });
  document.querySelectorAll("[data-command-palette]").forEach((element) => {
    element.addEventListener("click", openCommandPalette);
  });
  document.querySelectorAll("[data-run-command]").forEach((element) => {
    element.addEventListener("click", () => {
      closeCommandPalette();
      runCommand(element.dataset.pluginId, element.dataset.runCommand);
    });
  });
  document.querySelector("#command-modal")?.addEventListener("click", (event) => {
    if (event.target.id === "command-modal") closeCommandPalette();
  });
  document.querySelector("#command-search")?.addEventListener("input", (event) => {
    const query = event.target.value.toLowerCase();
    document.querySelectorAll(".command-row").forEach((row) => {
      row.classList.toggle("hidden", !row.textContent.toLowerCase().includes(query));
    });
  });
}

function openCommandPalette() {
  document.querySelector("#command-modal")?.classList.remove("hidden");
  document.querySelector("#command-search")?.focus();
}

function closeCommandPalette() {
  document.querySelector("#command-modal")?.classList.add("hidden");
}

async function runDemo(pluginId) {
  const plugin = state.catalog.plugins.find((item) => pluginManifest(item).id === pluginId);
  const manifest = pluginManifest(plugin);
  const command = manifest.contributes?.commands?.[0]?.id;
  if (!command) return;
  await runCommand(pluginId, command, demoArguments[pluginId] ?? {});
}

async function runCommand(pluginId, command, explicitArguments = undefined) {
  state.selectedPluginId = pluginId;
  state.output.push(`> ${command}`);
  state.latestResult = { status: "running", command };
  render();
  const args = explicitArguments ?? demoArguments[pluginId] ?? {};
  try {
    const desktopResult = await invokeTauri("run_plugin_command", {
      pluginId,
      command,
      arguments: args,
      pluginsRoot: "plugins",
      workspaceRoot: "examples/demo-workspace",
    });
    state.latestResult = desktopResult ?? browserDemo(pluginId, command, args);
    state.output.push(`Completed ${command}.`);
  } catch (error) {
    state.latestResult = { error: String(error), command };
    state.output.push(`Failed ${command}: ${error}`);
  }
  render();
}

function browserDemo(pluginId, command, args) {
  if (pluginId === "hu.codelayer.pin-configurator") {
    const assignments = {};
    const used = new Set();
    for (const signal of args.signals ?? []) {
      const pin = (args.pins ?? []).find((candidate) =>
        !candidate.reserved && !used.has(candidate.name) && signal.requires.every((item) => candidate.capabilities.includes(item))
      );
      if (pin) { assignments[signal.id] = pin.name; used.add(pin.name); }
    }
    return { browserPreview: true, result: { solved: Object.keys(assignments).length === args.signals.length, assignments } };
  }
  if (pluginId === "hu.codelayer.route-core") {
    return { browserPreview: true, result: { routed: true, points: [args.source, { x: 110, y: args.source.y }, { x: 110, y: 230 }, { x: args.target.x, y: 230 }, args.target], note: "Desktop mode runs the obstacle-aware A* service." } };
  }
  if (pluginId === "hu.codelayer.openhdl-designer") {
    return { browserPreview: true, result: { valid: true, nodes: args.nodes?.length ?? 0, nets: args.nets?.length ?? 0, note: "Desktop mode executes full graph validation and Verilog generation." } };
  }
  return { browserPreview: true, result: { completed: true, workflow: args.workflow?.name, steps: args.workflow?.steps?.length ?? 0 } };
}

window.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    openCommandPalette();
  } else if (event.key === "Escape") {
    closeCommandPalette();
  }
});

try {
  await loadCatalog();
  render();
} catch (error) {
  document.querySelector("#app").innerHTML = `<pre class="console">Failed to initialize CodeLayer Forge: ${escapeHtml(error)}</pre>`;
}
