'use strict';

const TOKEN_KEY = 'embeddynStudioToken';
const LEGACY_TOKEN_KEY = 'vsdStudioToken';

const state = {
  token: localStorage.getItem(TOKEN_KEY) || localStorage.getItem(LEGACY_TOKEN_KEY) || '',
  health: null,
  components: [],
  assets: [],
  projects: [],
  sessions: [],
  graph: { nodes: [], connections: [] },
  selectedNode: null,
  connecting: false,
  connectionSource: null,
  activeProjectId: null,
  firmwareReport: null,
  reportTab: 'summary',
  plotPaused: false,
  plotTimer: null,
  logs: [],
  rfCapabilities: null,
  rfTouchstone: null,
  rfNoise: null,
  rfPatch: null,
  rfPatchDirty: false,
  rfS11Dirty: false,
  rfNoiseDirty: false,
};

const colors = ['#55d6be', '#63a8ff', '#ffca69', '#ff7c91', '#b394ff', '#8dde72', '#ff9f5a', '#66e0ff'];
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function toast(message, error = false) {
  const element = $('#toast');
  element.textContent = message;
  element.style.borderColor = error ? '#ff6f7d' : '#55d6be';
  element.classList.add('show');
  clearTimeout(element._timer);
  element._timer = setTimeout(() => element.classList.remove('show'), 2800);
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.token) headers.set('Authorization', `Bearer ${state.token}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try { detail = (await response.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  const type = response.headers.get('content-type') || '';
  return type.includes('application/json') ? response.json() : response.text();
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  })[character]);
}

function formatTime(timestamp) {
  return timestamp === null || timestamp === undefined ? '—' : new Date(Number(timestamp) * 1000).toLocaleString();
}

function safeCoordinate(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? Math.max(0, numeric) : 0;
}

function normalizeGraph(graph) {
  const source = graph && typeof graph === 'object' ? graph : {};
  const nodes = Array.isArray(source.nodes) ? source.nodes.map((node, index) => ({
    ...(node && typeof node === 'object' ? node : {}),
    id: String(node?.id ?? `node-${index}`),
    componentId: String(node?.componentId ?? ''),
    label: String(node?.label ?? ''),
    kind: String(node?.kind ?? ''),
    bus: String(node?.bus ?? ''),
    vendor: String(node?.vendor ?? ''),
    className: String(node?.className ?? ''),
    x: safeCoordinate(node?.x),
    y: safeCoordinate(node?.y),
    properties: node?.properties && typeof node.properties === 'object' && !Array.isArray(node.properties) ? node.properties : {},
  })) : [];
  const nodeIds = new Set(nodes.map(node => node.id));
  const connections = Array.isArray(source.connections) ? source.connections
    .filter(connection => connection && typeof connection === 'object')
    .map((connection, index) => ({
      id: String(connection.id ?? `connection-${index}`),
      from: String(connection.from ?? ''),
      to: String(connection.to ?? ''),
      type: String(connection.type ?? 'bus'),
    }))
    .filter(connection => nodeIds.has(connection.from) && nodeIds.has(connection.to)) : [];
  return { nodes, connections };
}

function formatBytes(value) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / 1024 ** 2).toFixed(1)} MiB`;
}

async function bootstrap() {
  installTabNavigation();
  installDesignerEvents();
  installMonitorEvents();
  installRFEvents();
  renderRFConstruction();
  renderRFDashboard();
  installFirmwareEvents();
  installEmulationEvents();
  installLogEvents();
  installSettingsEvents();
  window.addEventListener('resize', () => {
    renderConnections();
    if (state.lastPlot) drawPlot(state.lastPlot);
    if (state.rfTouchstone) renderRFTouchstone(state.rfTouchstone);
    if (state.rfNoise) renderRFNoise(state.rfNoise);
    renderRFConstruction();
  });

  try {
    await refreshStudioData();
  } catch (error) {
    toast(`Startup failed: ${error.message}`, true);
  }
}

async function refreshStudioData() {
  state.health = await api('/api/health');
  renderHealth();
  if (state.health.auth_required && !state.health.authenticated) {
    toast('Remote Studio is locked. Enter the API token in Settings.', true);
    return;
  }
  await Promise.all([loadComponents(), loadAssets(), loadProjects(), loadSessions(), loadRFCapabilities()]);
  renderRFConstruction();
  renderRFDashboard();
  startPlotLoop();
}

function installTabNavigation() {
  $$('.tab').forEach(button => button.addEventListener('click', () => {
    $$('.tab').forEach(item => item.classList.toggle('active', item === button));
    $$('.panel-view').forEach(panel => panel.classList.toggle('active', panel.id === button.dataset.tab));
    if (button.dataset.tab === 'monitor') refreshPlot();
    if (button.dataset.tab === 'rf') { loadRFCapabilities(); renderRFConstruction(); renderRFDashboard(); }
    if (button.dataset.tab === 'logs') refreshLogs();
    if (button.dataset.tab === 'emulation') loadSessions();
  }));
}

function renderHealth() {
  const health = state.health;
  const locked = health.auth_required && !health.authenticated;
  $('#localMode').textContent = health.local_only ? 'LOCAL' : (locked ? 'REMOTE LOCKED' : 'REMOTE TOKEN');
  $('#localMode').className = `pill ${health.local_only ? 'ok' : 'warning'}`;
  $('#catalogCount').textContent = locked ? 'authentication required' : `${health.catalog?.total ?? 0} components`;
  $('#dataPath').textContent = locked ? 'Protected until authenticated' : (health.data_dir || '—');
  $('#healthDetails').innerHTML = locked ? `
    <div class="empty-state">Remote mode requires the bearer token. Enter it in Settings to load local data.</div>` : `
    <table>
      <tr><th>Data directory</th><td>${escapeHtml(health.data_dir)}</td></tr>
      <tr><th>Workspace</th><td>${escapeHtml(health.workspace)}</td></tr>
      <tr><th>Catalog</th><td>${Number(health.catalog?.total ?? 0)} local entries</td></tr>
      <tr><th>Mode</th><td>${health.local_only ? 'loopback-only' : 'remote/token-protected'}</td></tr>
    </table>`;
  renderToolchain(health.toolchain || {});
}

function renderToolchain(toolchain) {
  $('#toolchainCards').innerHTML = Object.entries(toolchain).map(([name, path]) => `
    <div class="stat"><span>${escapeHtml(name)}</span><strong>${path ? 'Ready' : 'Missing'}</strong><small class="muted">${escapeHtml(path || 'configure environment variable')}</small></div>
  `).join('');
}

async function loadComponents() {
  const query = encodeURIComponent($('#componentSearch').value.trim());
  const kind = encodeURIComponent($('#componentKind').value);
  const bus = encodeURIComponent($('#componentBus').value);
  state.components = await api(`/api/components?query=${query}&kind=${kind}&bus=${bus}&limit=250`);
  renderComponents();
}

function renderComponents() {
  const list = $('#componentList');
  list.innerHTML = state.components.map(component => `
    <article class="component-card" draggable="true" data-component="${escapeHtml(component.id)}">
      <strong>${escapeHtml(component.model)}</strong>
      <small>${escapeHtml(component.vendor)}</small>
      <div class="component-meta"><span>${escapeHtml(component.kind)}</span><span>${escapeHtml(component.bus)}</span><span>${escapeHtml(component.tier)}</span></div>
    </article>`).join('') || '<div class="empty-state">No matching components.</div>';
  list.querySelectorAll('.component-card').forEach(card => {
    card.addEventListener('dragstart', event => {
      event.dataTransfer.setData('application/x-embeddyn-component', card.dataset.component);
    });
    card.addEventListener('dblclick', () => addComponentNode(card.dataset.component, 80, 80));
  });
}

function installDesignerEvents() {
  let searchTimer;
  ['#componentSearch', '#componentKind', '#componentBus'].forEach(selector => {
    $(selector).addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(loadComponents, 180);
    });
  });
  const surface = $('#designSurface');
  surface.addEventListener('dragover', event => event.preventDefault());
  surface.addEventListener('drop', event => {
    event.preventDefault();
    const componentId = event.dataTransfer.getData('application/x-embeddyn-component');
    if (!componentId) return;
    const rect = surface.getBoundingClientRect();
    addComponentNode(componentId, event.clientX - rect.left + surface.scrollLeft, event.clientY - rect.top + surface.scrollTop);
  });
  $('#newProject').addEventListener('click', newProject);
  $('#saveProject').addEventListener('click', saveProject);
  $('#loadProject').addEventListener('click', loadSelectedProject);
  $('#connectNodes').addEventListener('click', () => {
    state.connecting = !state.connecting;
    state.connectionSource = null;
    $('#connectNodes').classList.toggle('primary', state.connecting);
    $('#designerHint').textContent = state.connecting ? 'Select two nodes to create a connection.' : 'Drag components from the catalog.';
  });
  $('#deleteNode').addEventListener('click', deleteSelectedNode);
  $('#fitCanvas').addEventListener('click', fitCanvas);
  surface.addEventListener('click', event => {
    if (event.target === surface || event.target.classList.contains('node-layer')) selectNode(null);
  });
}

function newProject() {
  state.graph = { nodes: [], connections: [] };
  state.activeProjectId = null;
  $('#projectName').value = 'Untitled system';
  selectNode(null);
  renderGraph();
}

function addComponentNode(componentId, x, y) {
  const component = state.components.find(item => item.id === componentId);
  if (!component) return;
  const node = {
    id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
    componentId: component.id,
    label: component.model,
    kind: component.kind,
    bus: component.bus,
    vendor: component.vendor,
    className: component.class_name,
    x: Math.max(10, Math.round(x / 12) * 12),
    y: Math.max(10, Math.round(y / 12) * 12),
    properties: {},
  };
  state.graph.nodes.push(node);
  renderGraph();
  selectNode(node.id);
}

function renderGraph() {
  const layer = $('#nodeLayer');
  layer.innerHTML = state.graph.nodes.map(node => `
    <div class="graph-node ${node.id === state.selectedNode ? 'selected' : ''}" data-node="${escapeHtml(node.id)}" style="left:${safeCoordinate(node.x)}px;top:${safeCoordinate(node.y)}px">
      <div class="node-head"><strong>${escapeHtml(node.label)}</strong><small>${escapeHtml(node.vendor)}</small></div>
      <div class="node-body"><span>${escapeHtml(node.kind)} · ${escapeHtml(node.bus)}</span><span class="port"></span></div>
    </div>`).join('');
  layer.querySelectorAll('.graph-node').forEach(element => {
    element.addEventListener('mousedown', beginNodeDrag);
    element.addEventListener('click', event => {
      event.stopPropagation();
      handleNodeClick(element.dataset.node);
    });
  });
  renderConnections();
  renderGraphSummary();
  renderRFSystemSources();
  renderRFDashboard();
}

function beginNodeDrag(event) {
  if (event.button !== 0 || state.connecting) return;
  event.preventDefault();
  const element = event.currentTarget;
  const node = state.graph.nodes.find(item => item.id === element.dataset.node);
  const startX = event.clientX;
  const startY = event.clientY;
  const originX = node.x;
  const originY = node.y;
  function move(moveEvent) {
    node.x = Math.max(0, Math.round((originX + moveEvent.clientX - startX) / 12) * 12);
    node.y = Math.max(0, Math.round((originY + moveEvent.clientY - startY) / 12) * 12);
    element.style.left = `${node.x}px`;
    element.style.top = `${node.y}px`;
    renderConnections();
  }
  function end() {
    document.removeEventListener('mousemove', move);
    document.removeEventListener('mouseup', end);
    renderGraphSummary();
  }
  document.addEventListener('mousemove', move);
  document.addEventListener('mouseup', end);
}

function handleNodeClick(nodeId) {
  if (state.connecting) {
    if (!state.connectionSource) {
      state.connectionSource = nodeId;
      selectNode(nodeId);
      $('#designerHint').textContent = 'Select destination node.';
    } else if (state.connectionSource !== nodeId) {
      const exists = state.graph.connections.some(connection => connection.from === state.connectionSource && connection.to === nodeId);
      if (!exists) state.graph.connections.push({ id: crypto.randomUUID(), from: state.connectionSource, to: nodeId, type: 'bus' });
      state.connectionSource = null;
      $('#designerHint').textContent = 'Select another source or disable Connect.';
      renderGraph();
    }
  } else {
    selectNode(nodeId);
  }
}

function selectNode(nodeId) {
  state.selectedNode = nodeId;
  $$('.graph-node').forEach(node => node.classList.toggle('selected', node.dataset.node === nodeId));
  const node = state.graph.nodes.find(item => item.id === nodeId);
  if (!node) {
    $('#nodeInspector').className = 'empty-state';
    $('#nodeInspector').innerHTML = 'Select a node.';
    return;
  }
  $('#nodeInspector').className = 'inspector-grid';
  $('#nodeInspector').innerHTML = `
    <label>Label<input id="nodeLabel" value="${escapeHtml(node.label)}"></label>
    <label>Component<input value="${escapeHtml(node.componentId)}" disabled></label>
    <label>Bus<input value="${escapeHtml(node.bus)}" disabled></label>
    <label>Renode class<input value="${escapeHtml(node.className)}" disabled></label>
    <label>Properties JSON<textarea id="nodeProperties" rows="8">${escapeHtml(JSON.stringify(node.properties, null, 2))}</textarea></label>`;
  $('#nodeLabel').addEventListener('input', event => {
    node.label = event.target.value;
    renderGraph();
  });
  $('#nodeProperties').addEventListener('change', event => {
    try { node.properties = JSON.parse(event.target.value); toast('Node properties updated'); }
    catch (error) { toast(`Invalid JSON: ${error.message}`, true); }
  });
}

function renderConnections() {
  const svg = $('#connectionLayer');
  svg.setAttribute('viewBox', '0 0 2400 1600');
  svg.innerHTML = state.graph.connections.map(connection => {
    const from = state.graph.nodes.find(node => node.id === connection.from);
    const to = state.graph.nodes.find(node => node.id === connection.to);
    if (!from || !to) return '';
    const x1 = from.x + 190, y1 = from.y + 58;
    const x2 = to.x, y2 = to.y + 58;
    const bend = Math.max(50, Math.abs(x2 - x1) * .45);
    return `<path d="M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}"></path>`;
  }).join('');
}

function deleteSelectedNode() {
  if (!state.selectedNode) return;
  state.graph.nodes = state.graph.nodes.filter(node => node.id !== state.selectedNode);
  state.graph.connections = state.graph.connections.filter(connection => connection.from !== state.selectedNode && connection.to !== state.selectedNode);
  state.selectedNode = null;
  renderGraph();
  selectNode(null);
}

function fitCanvas() {
  const surface = $('#designSurface');
  if (!state.graph.nodes.length) { surface.scrollTo(0, 0); return; }
  const minX = Math.min(...state.graph.nodes.map(node => node.x));
  const minY = Math.min(...state.graph.nodes.map(node => node.y));
  surface.scrollTo({ left: Math.max(0, minX - 40), top: Math.max(0, minY - 40), behavior: 'smooth' });
}

function renderGraphSummary() {
  const counts = state.graph.nodes.reduce((acc, node) => { acc[node.kind] = (acc[node.kind] || 0) + 1; return acc; }, {});
  $('#graphSummary').textContent = JSON.stringify({ nodes: state.graph.nodes.length, connections: state.graph.connections.length, byKind: counts }, null, 2);
}

async function saveProject() {
  try {
    const project = await api('/api/projects', {
      method: 'POST',
      body: JSON.stringify({ id: state.activeProjectId, name: $('#projectName').value, graph: state.graph }),
    });
    state.activeProjectId = project.id;
    await loadProjects();
    $('#projectSelect').value = project.id;
    toast('Project saved locally');
  } catch (error) { toast(error.message, true); }
}

async function loadProjects() {
  state.projects = await api('/api/projects');
  $('#projectSelect').innerHTML = '<option value="">Select…</option>' + state.projects.map(project => `<option value="${escapeHtml(project.id)}">${escapeHtml(project.name)}</option>`).join('');
}

function loadSelectedProject() {
  const project = state.projects.find(item => item.id === $('#projectSelect').value);
  if (!project) return;
  state.activeProjectId = project.id;
  state.graph = normalizeGraph(project.graph);
  $('#projectName').value = project.name;
  selectNode(null);
  renderGraph();
}

async function loadAssets() {
  state.assets = await api('/api/assets?limit=1000');
  const options = '<option value="">None</option>' + state.assets.map(asset => `<option value="${asset.id}">${escapeHtml(asset.name)} (${formatBytes(asset.size)})</option>`).join('');
  ['#firmwareAsset', '#sessionFirmware', '#sessionPlatform', '#sessionScript', '#rfTouchstoneAsset', '#rfWaveformAsset'].forEach(selector => $(selector).innerHTML = options);
}

function installMonitorEvents() {
  $('#refreshPlot').addEventListener('click', refreshPlot);
  $('#pausePlot').addEventListener('click', event => {
    state.plotPaused = !state.plotPaused;
    event.target.textContent = state.plotPaused ? 'Resume' : 'Pause';
  });
  $('#injectPoint').addEventListener('click', injectPoint);
  $('#plotMode').addEventListener('change', refreshPlot);
}

function startPlotLoop() {
  clearInterval(state.plotTimer);
  state.plotTimer = setInterval(() => {
    if (!state.plotPaused && $('#monitor').classList.contains('active')) refreshPlot();
  }, 1000);
}

async function refreshPlot() {
  const sessionId = $('#monitorSession').value;
  if (!sessionId) {
    drawEmptyPlot('Select or start a session.');
    return;
  }
  const windowSeconds = Number($('#monitorWindow').value) || 30;
  const since = Date.now() / 1000 - windowSeconds;
  const channels = $('#monitorChannels').value.split(',').map(item => item.trim()).filter(Boolean);
  const params = new URLSearchParams({
    since: String(since),
    limit: '100000',
    expression: $('#filterExpression').value,
    pipeline: $('#filterPipeline').value || '[]',
    plot: $('#plotMode').value,
  });
  channels.forEach(channel => params.append('channel', channel));
  try {
    const response = await api(`/api/sessions/${sessionId}/telemetry?${params}`);
    state.lastPlot = response.plot;
    drawPlot(response.plot);
    renderPlotStats(response.points);
  } catch (error) { toast(`Plot: ${error.message}`, true); }
}

async function injectPoint() {
  const sessionId = $('#monitorSession').value;
  if (!sessionId) return toast('Select a session first', true);
  try {
    await api(`/api/sessions/${sessionId}/telemetry`, {
      method: 'POST',
      body: JSON.stringify({ points: [{ channel: $('#injectChannel').value, value: Number($('#injectValue').value), kind: $('#injectKind').value }] }),
    });
    refreshPlot();
  } catch (error) { toast(error.message, true); }
}

function canvasContext() {
  const canvas = $('#plotCanvas');
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * ratio));
  canvas.height = Math.max(1, Math.floor(rect.height * ratio));
  const context = canvas.getContext('2d');
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { canvas, context, width: rect.width, height: rect.height };
}

function drawEmptyPlot(message) {
  const { context, width, height } = canvasContext();
  context.clearRect(0, 0, width, height);
  context.fillStyle = '#90a2b7';
  context.textAlign = 'center';
  context.fillText(message, width / 2, height / 2);
}

function drawPlot(plot) {
  if (!plot) return drawEmptyPlot('No data.');
  const frame = canvasContext();
  const { context: ctx, width, height } = frame;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = '#0a1119'; ctx.fillRect(0, 0, width, height);
  drawGrid(ctx, width, height);
  if (plot.mode === 'time' || plot.mode === 'scope') drawLineSeries(ctx, width, height, plot.series || [], plot.mode === 'scope');
  else if (plot.mode === 'bar') drawBars(ctx, width, height, plot.labels || [], plot.values || []);
  else if (plot.mode === 'histogram') drawHistograms(ctx, width, height, plot.series || []);
  else if (plot.mode === 'spectrum') drawSpectrum(ctx, width, height, plot.series || []);
  else if (plot.mode === 'logic') drawLogic(ctx, width, height, plot.series || []);
  renderLegend(plot);
}

function drawGrid(ctx, width, height) {
  ctx.strokeStyle = 'rgba(90,120,150,.18)'; ctx.lineWidth = 1;
  for (let x = 45; x < width - 10; x += Math.max(40, (width - 55) / 10)) { ctx.beginPath(); ctx.moveTo(x, 10); ctx.lineTo(x, height - 30); ctx.stroke(); }
  for (let y = 10; y < height - 30; y += Math.max(30, (height - 40) / 8)) { ctx.beginPath(); ctx.moveTo(45, y); ctx.lineTo(width - 10, y); ctx.stroke(); }
}

function drawLineSeries(ctx, width, height, series, scopeMode) {
  const numeric = series.flatMap(item => item.y.map((value, index) => ({ x: Number(item.x[index]), y: Number(value) })).filter(point => Number.isFinite(point.x) && Number.isFinite(point.y)));
  if (!numeric.length) return;
  const minX = Math.min(...numeric.map(point => point.x)), maxX = Math.max(...numeric.map(point => point.x));
  let minY = Math.min(...numeric.map(point => point.y)), maxY = Math.max(...numeric.map(point => point.y));
  if (scopeMode) { const maxAbs = Math.max(Math.abs(minY), Math.abs(maxY), 1e-9); minY = -maxAbs; maxY = maxAbs; }
  if (minY === maxY) { minY -= 1; maxY += 1; }
  series.forEach((item, colorIndex) => {
    ctx.strokeStyle = colors[colorIndex % colors.length]; ctx.lineWidth = scopeMode ? 2 : 1.7; ctx.beginPath();
    let started = false;
    item.y.forEach((raw, index) => {
      const xValue = Number(item.x[index]), yValue = Number(raw);
      if (!Number.isFinite(xValue) || !Number.isFinite(yValue)) return;
      const x = 45 + ((xValue - minX) / Math.max(maxX - minX, 1e-9)) * (width - 60);
      const y = 10 + (1 - (yValue - minY) / (maxY - minY)) * (height - 45);
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    });
    ctx.stroke();
  });
  drawAxisLabels(ctx, width, height, minX, maxX, minY, maxY);
}

function drawBars(ctx, width, height, labels, values) {
  const numeric = values.map(Number); const max = Math.max(...numeric.map(value => Math.abs(value)), 1);
  const barWidth = (width - 65) / Math.max(labels.length, 1);
  numeric.forEach((value, index) => {
    const x = 50 + index * barWidth + 4; const h = Math.abs(value) / max * (height - 70); const y = height - 35 - h;
    ctx.fillStyle = colors[index % colors.length]; ctx.fillRect(x, y, Math.max(3, barWidth - 8), h);
    ctx.fillStyle = '#90a2b7'; ctx.font = '11px sans-serif'; ctx.fillText(labels[index].slice(0, 14), x, height - 15);
  });
}

function drawHistograms(ctx, width, height, series) {
  const maxCount = Math.max(1, ...series.flatMap(item => item.counts));
  series.forEach((item, colorIndex) => {
    const count = item.counts.length; const binWidth = (width - 60) / Math.max(count, 1);
    ctx.fillStyle = `${colors[colorIndex % colors.length]}88`;
    item.counts.forEach((value, index) => {
      const h = value / maxCount * (height - 55);
      ctx.fillRect(45 + index * binWidth, height - 35 - h, Math.max(1, binWidth - 1), h);
    });
  });
}

function drawSpectrum(ctx, width, height, series) {
  const lineSeries = series.map(item => ({ channel: item.channel, x: item.frequency, y: item.magnitude }));
  drawLineSeries(ctx, width, height, lineSeries, false);
  ctx.fillStyle = '#90a2b7'; ctx.fillText('Frequency (Hz)', width - 90, height - 12);
}

function drawLogic(ctx, width, height, series) {
  const transitions = series.flatMap(item => item.transitions);
  if (!transitions.length) return;
  const minX = Math.min(...transitions.map(item => item.timestamp)); const maxX = Math.max(...transitions.map(item => item.timestamp));
  const laneHeight = (height - 40) / Math.max(series.length, 1);
  series.forEach((item, index) => {
    const base = 15 + index * laneHeight + laneHeight * .7;
    ctx.strokeStyle = colors[index % colors.length]; ctx.lineWidth = 2; ctx.beginPath();
    let previousX = 45; let previousY = base;
    item.transitions.forEach(transition => {
      const x = 45 + ((transition.timestamp - minX) / Math.max(maxX - minX, 1e-9)) * (width - 60);
      const y = base - (transition.value ? laneHeight * .45 : 0);
      ctx.lineTo(x, previousY); ctx.lineTo(x, y); previousX = x; previousY = y;
    });
    ctx.lineTo(width - 10, previousY); ctx.stroke();
    ctx.fillStyle = '#90a2b7'; ctx.fillText(item.channel, 4, base - laneHeight * .18);
  });
}

function drawAxisLabels(ctx, width, height, minX, maxX, minY, maxY) {
  ctx.fillStyle = '#90a2b7'; ctx.font = '10px sans-serif';
  ctx.fillText(maxY.toPrecision(4), 4, 16); ctx.fillText(minY.toPrecision(4), 4, height - 32);
  ctx.fillText(new Date(minX * 1000).toLocaleTimeString(), 45, height - 12);
  ctx.textAlign = 'right'; ctx.fillText(new Date(maxX * 1000).toLocaleTimeString(), width - 10, height - 12); ctx.textAlign = 'left';
}

function renderLegend(plot) {
  const names = plot.series ? plot.series.map(item => item.channel) : plot.labels || [];
  $('#plotLegend').innerHTML = names.map((name, index) => `<span class="legend-item" style="--legend-color:${colors[index % colors.length]}">${escapeHtml(name)}</span>`).join('');
}

function renderPlotStats(points) {
  const channels = [...new Set(points.map(point => point.channel))];
  const numeric = points.map(point => Number(point.value)).filter(Number.isFinite);
  $('#plotStats').innerHTML = [
    ['Points', points.length], ['Channels', channels.length], ['Minimum', numeric.length ? Math.min(...numeric).toPrecision(6) : '—'],
    ['Maximum', numeric.length ? Math.max(...numeric).toPrecision(6) : '—'], ['Mean', numeric.length ? (numeric.reduce((a,b)=>a+b,0)/numeric.length).toPrecision(6) : '—']
  ].map(([label, value]) => `<div class="stat"><span>${label}</span><strong>${value}</strong></div>`).join('');
}

async function loadRFCapabilities() {
  try {
    state.rfCapabilities = await api('/api/rf/capabilities');
    const labels = {
      builtin: 'Built-in', openems: 'openEMS', scikit_rf: 'scikit-rf', nec2c: 'NEC2'
    };
    $('#rfCapabilities').innerHTML = Object.entries(state.rfCapabilities).map(([name, item]) =>
      `<span class="pill ${item.available ? 'ok' : ''}" title="${escapeHtml(item.purpose || '')}">${escapeHtml(labels[name] || name)}: ${item.available ? 'ready' : 'optional'}</span>`
    ).join('');
    renderRFConstruction();
    renderRFDashboard();
  } catch (error) {
    $('#rfCapabilities').innerHTML = `<span class="pill warning">RF capability check failed</span>`;
  }
}

function installRFEvents() {
  $('#rfStoreAsset').addEventListener('click', storeRFAsset);
  $('#rfAnalyzeTouchstone').addEventListener('click', analyzeRFTouchstone);
  $('#rfPatchSeed').addEventListener('click', generateRFPatchSeed);
  $('#rfPatchOpenEMS').addEventListener('click', downloadRFPatchModel);
  $('#rfApplyTuning').addEventListener('click', applyRFPatchTuning);
  $('#rfAnalyzeWaveform').addEventListener('click', analyzeRFAssetNoise);
  $('#rfAnalyzeSession').addEventListener('click', analyzeRFSessionNoise);
  ['#rfPatchEr','#rfPatchH','#rfPatchLoss','#rfPatchWidth','#rfPatchLength','#rfPatchFeed','#rfTargetMHz'].forEach(selector => {
    $(selector)?.addEventListener('input', () => {
      if (state.rfPatch) state.rfPatchDirty = true;
      if (selector === '#rfTargetMHz' && state.rfTouchstone) state.rfS11Dirty = true;
      renderRFConstruction(); renderRFDashboard();
      if (state.rfTouchstone && selector === '#rfTargetMHz') { drawRFS11Chart(state.rfTouchstone); drawRFSmithChart(state.rfTouchstone); }
    });
  });
  ['#rfReturnLoss','#rfZ0'].forEach(selector => $(selector)?.addEventListener('input', () => {
    if (state.rfTouchstone) state.rfS11Dirty = true;
    renderRFDashboard();
    if (state.rfTouchstone) drawRFS11Chart(state.rfTouchstone);
  }));
  ['#rfLimitMask','#rfImpedance','#rfValueUnit','#rfSampleRate'].forEach(selector => $(selector)?.addEventListener('input', () => {
    if (state.rfNoise) state.rfNoiseDirty = true;
    if (state.rfNoise) drawRFNoiseSpectrum(state.rfNoise);
    renderRFDashboard();
  }));
}


function rfPatchPayload(includeGeometry = true) {
  const targetMHz = Number($('#rfTargetMHz').value);
  const epsilonR = Number($('#rfPatchEr').value);
  const thicknessMm = Number($('#rfPatchH').value);
  const lossTangent = Number($('#rfPatchLoss').value);
  if (!Number.isFinite(targetMHz) || targetMHz <= 0) throw new Error('Target frequency must be positive');
  if (!Number.isFinite(epsilonR) || epsilonR <= 1) throw new Error('Patch εr must be greater than 1');
  if (!Number.isFinite(thicknessMm) || thicknessMm <= 0) throw new Error('Substrate thickness must be positive');
  const payload = {
    target_frequency_hz: targetMHz * 1e6,
    dielectric_constant: epsilonR,
    substrate_thickness_m: thicknessMm * 1e-3,
    loss_tangent: Number.isFinite(lossTangent) && lossTangent >= 0 ? lossTangent : 0.002,
    reference_impedance_ohms: Number($('#rfZ0').value) || 50,
  };
  if (includeGeometry) {
    const width = Number($('#rfPatchWidth').value);
    const length = Number($('#rfPatchLength').value);
    const feed = Number($('#rfPatchFeed').value);
    if (Number.isFinite(width) && width > 0) payload.width_m = width * 1e-3;
    if (Number.isFinite(length) && length > 0) payload.length_m = length * 1e-3;
    if ($('#rfPatchFeed').value.trim() && Number.isFinite(feed)) payload.feed_offset_m = feed * 1e-3;
  }
  return payload;
}

async function generateRFPatchSeed() {
  try {
    state.rfPatch = await api('/api/rf/patch/seed', { method: 'POST', body: JSON.stringify(rfPatchPayload(false)) });
    state.rfPatchDirty = false;
    $('#rfPatchWidth').value = (Number(state.rfPatch.patch_width_m) * 1e3).toFixed(3);
    $('#rfPatchLength').value = (Number(state.rfPatch.patch_length_m) * 1e3).toFixed(3);
    $('#rfPatchFeed').value = (Number(state.rfPatch.feed_offset_m) * 1e3).toFixed(3);
    renderRFPatchGeometry(state.rfPatch);
    renderRFConstruction();
    renderRFDashboard();
  } catch (error) { toast(error.message, true); }
}

async function downloadRFPatchModel() {
  try {
    const result = await api('/api/rf/patch/openems-script', { method: 'POST', body: JSON.stringify(rfPatchPayload(true)) });
    state.rfPatch = result.geometry;
    state.rfPatchDirty = false;
    renderRFPatchGeometry(result.geometry);
    renderRFConstruction();
    renderRFDashboard();
    const link = document.createElement('a');
    const url = URL.createObjectURL(new Blob([result.script], { type: 'text/x-python;charset=utf-8' }));
    link.href = url;
    link.download = result.filename || 'embeddyn_openems_patch.py';
    link.click();
    URL.revokeObjectURL(url);
    toast('openEMS patch model generated');
  } catch (error) { toast(error.message, true); }
}

function applyRFPatchTuning() {
  const tuning = state.rfTouchstone?.tuning;
  if (!tuning || !Number.isFinite(Number(tuning.geometry_scale))) return toast('Analyze S11 at a target frequency first', true);
  let lengthMm = Number($('#rfPatchLength').value);
  if (!Number.isFinite(lengthMm) || lengthMm <= 0) {
    lengthMm = Number(state.rfPatch?.patch_length_m) * 1e3;
  }
  if (!Number.isFinite(lengthMm) || lengthMm <= 0) return toast('Calculate a patch seed first', true);
  const updated = lengthMm * Number(tuning.geometry_scale);
  $('#rfPatchLength').value = updated.toFixed(3);
  const direction = Number(tuning.geometry_change_percent) >= 0 ? 'lengthened' : 'shortened';
  state.rfPatchDirty = true;
  renderRFConstruction();
  renderRFDashboard();
  toast(`Patch resonant length ${direction} to ${updated.toFixed(3)} mm; re-run openEMS`);
}

function renderRFPatchGeometry(geometry) {
  $('#rfPatchGeometry').classList.remove('empty-state');
  const warnings = geometry.warnings || [];
  $('#rfPatchGeometry').innerHTML = `<table>
    <tr><th>Patch W × L</th><td>${(Number(geometry.patch_width_m)*1e3).toFixed(3)} × ${(Number(geometry.patch_length_m)*1e3).toFixed(3)} mm</td></tr>
    <tr><th>Feed offset</th><td>${(Number(geometry.feed_offset_m)*1e3).toFixed(3)} mm along resonant length</td></tr>
    <tr><th>Effective εr</th><td>${Number(geometry.effective_dielectric_constant).toFixed(4)}</td></tr>
    <tr><th>Substrate / ground seed</th><td>${(Number(geometry.substrate_width_m)*1e3).toFixed(2)} × ${(Number(geometry.substrate_length_m)*1e3).toFixed(2)} mm</td></tr>
    <tr><th>Full-wave sweep</th><td>${formatFrequency(geometry.sweep_low_hz)} – ${formatFrequency(geometry.sweep_high_hz)} · ${geometry.sweep_points} points</td></tr>
  </table><ul>${warnings.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`;
  renderRFConstruction();
  renderRFDashboard();
}

async function storeRFAsset() {
  const file = $('#rfUpload').files[0];
  if (!file) return toast('Choose an RF/Touchstone/waveform file', true);
  const form = new FormData();
  form.append('file', file);
  try {
    const asset = await api('/api/assets', { method: 'POST', body: form });
    await loadAssets();
    if (/\.s\d+p$/i.test(file.name)) $('#rfTouchstoneAsset').value = String(asset.id);
    else $('#rfWaveformAsset').value = String(asset.id);
    toast('RF asset stored locally');
  } catch (error) { toast(error.message, true); }
}

function parseRFLimitMask() {
  const raw = $('#rfLimitMask').value.trim();
  if (!raw) return [];
  const value = JSON.parse(raw);
  if (!Array.isArray(value)) throw new Error('Limit mask must be a JSON list');
  return value;
}

async function analyzeRFTouchstone() {
  const assetId = Number($('#rfTouchstoneAsset').value);
  if (!assetId) return toast('Select a Touchstone asset', true);
  const targetMHz = Number($('#rfTargetMHz').value);
  const payload = {
    asset_id: assetId,
    target_frequency_hz: Number.isFinite(targetMHz) && targetMHz > 0 ? targetMHz * 1e6 : null,
    return_loss_threshold_db: Number($('#rfReturnLoss').value) || 10,
    reference_impedance_ohms: Number($('#rfZ0').value) || 50,
  };
  try {
    state.rfTouchstone = await api('/api/rf/touchstone/analyze', { method: 'POST', body: JSON.stringify(payload) });
    state.rfS11Dirty = false;
    renderRFTouchstone(state.rfTouchstone);
  } catch (error) { toast(error.message, true); }
}

async function analyzeRFAssetNoise() {
  const assetId = Number($('#rfWaveformAsset').value);
  if (!assetId) return toast('Select a waveform CSV asset', true);
  try {
    const sampleRate = Number($('#rfSampleRate').value);
    const payload = {
      asset_id: assetId,
      sample_rate_hz: Number.isFinite(sampleRate) && sampleRate > 0 ? sampleRate : null,
      value_unit: $('#rfValueUnit').value.trim() || 'V',
      impedance_ohms: Number($('#rfImpedance').value) || 50,
      limit_mask: parseRFLimitMask(),
    };
    state.rfNoise = await api('/api/rf/noise/asset', { method: 'POST', body: JSON.stringify(payload) });
    state.rfNoiseDirty = false;
    renderRFNoise(state.rfNoise);
  } catch (error) { toast(error.message, true); }
}

async function analyzeRFSessionNoise() {
  const sessionId = $('#rfSession').value;
  const channel = $('#rfChannel').value.trim();
  if (!sessionId || !channel) return toast('Select a session and enter one telemetry channel', true);
  try {
    const payload = {
      session_id: sessionId,
      channel,
      value_unit: $('#rfValueUnit').value.trim() || 'V',
      impedance_ohms: Number($('#rfImpedance').value) || 50,
      limit_mask: parseRFLimitMask(),
    };
    state.rfNoise = await api('/api/rf/noise/session', { method: 'POST', body: JSON.stringify(payload) });
    state.rfNoiseDirty = false;
    renderRFNoise(state.rfNoise);
  } catch (error) { toast(error.message, true); }
}

function formatFrequency(value) {
  const hz = Number(value);
  if (!Number.isFinite(hz)) return '—';
  if (Math.abs(hz) >= 1e9) return `${(hz / 1e9).toFixed(4)} GHz`;
  if (Math.abs(hz) >= 1e6) return `${(hz / 1e6).toFixed(4)} MHz`;
  if (Math.abs(hz) >= 1e3) return `${(hz / 1e3).toFixed(3)} kHz`;
  return `${hz.toFixed(2)} Hz`;
}

function formatEngineering(value, unit = '') {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  const prefixes = [[1e9,'G'],[1e6,'M'],[1e3,'k'],[1,''],[1e-3,'m'],[1e-6,'µ'],[1e-9,'n'],[1e-12,'p']];
  const scale = prefixes.find(([limit]) => Math.abs(number) >= limit) || prefixes[prefixes.length - 1];
  return `${(number / scale[0]).toPrecision(4)} ${scale[1]}${unit}`;
}

function rfStatusClass(level) {
  return ['good', 'warning', 'danger'].includes(level) ? level : 'neutral';
}

function rfSetBadge(selector, label, level = 'neutral') {
  const element = $(selector);
  if (!element) return;
  element.textContent = label;
  element.className = `rf-status-badge ${rfStatusClass(level)}`;
}

function rfMatchAssessment(report = state.rfTouchstone) {
  if (state.rfS11Dirty && report) return { level: 'warning', label: 'S11 inputs changed', detail: 'Re-run S11 analysis to refresh target/matching metrics.' };
  const target = report?.target;
  if (!target || !Number.isFinite(Number(target.s11_db))) {
    return { level: 'neutral', label: 'Waiting for S11', detail: 'Import or simulate a Touchstone result.' };
  }
  const s11 = Number(target.s11_db);
  const vswr = Number(target.vswr);
  const goal = Math.abs(Number($('#rfReturnLoss')?.value) || 10);
  if (s11 <= -(goal + 5)) return { level: 'good', label: 'Excellent match', detail: `${s11.toFixed(1)} dB · VSWR ${Number.isFinite(vswr) ? vswr.toFixed(2) : '—'}` };
  if (s11 <= -goal) return { level: 'good', label: 'Target met', detail: `${s11.toFixed(1)} dB · VSWR ${Number.isFinite(vswr) ? vswr.toFixed(2) : '—'}` };
  if (s11 <= -(goal * 0.6)) return { level: 'warning', label: 'Marginal match', detail: `${s11.toFixed(1)} dB · improve feed/matching` };
  return { level: 'danger', label: 'Poor match', detail: `${s11.toFixed(1)} dB · significant reflected power` };
}

function rfResonanceAssessment(report = state.rfTouchstone) {
  if (state.rfS11Dirty && report) return { level: 'warning', label: 'Target changed', detail: 'Re-run S11 analysis before using resonance correction.' };
  const best = report?.best_match;
  const targetHz = Number($('#rfTargetMHz')?.value) * 1e6;
  if (!best || !Number.isFinite(Number(best.frequency_hz)) || !Number.isFinite(targetHz) || targetHz <= 0) {
    return { level: 'neutral', label: 'Not evaluated', detail: 'Target and measured resonance will be compared.' };
  }
  const delta = (Number(best.frequency_hz) - targetHz) / targetHz * 100;
  const abs = Math.abs(delta);
  const direction = delta > 0 ? 'high' : delta < 0 ? 'low' : 'on target';
  if (abs <= 0.5) return { level: 'good', label: 'Resonance on target', detail: `${delta >= 0 ? '+' : ''}${delta.toFixed(2)}% · ${formatFrequency(best.frequency_hz)}` };
  if (abs <= 3) return { level: 'warning', label: `Resonance ${direction}`, detail: `${delta >= 0 ? '+' : ''}${delta.toFixed(2)}% · tune resonant length` };
  return { level: 'danger', label: `Resonance ${direction}`, detail: `${delta >= 0 ? '+' : ''}${delta.toFixed(2)}% · geometry correction needed` };
}

function rfNoiseAssessment(report = state.rfNoise) {
  if (state.rfNoiseDirty && report) return { level: 'warning', label: 'Noise inputs changed', detail: 'Re-run FFT to recalculate peaks and mask margin.' };
  if (!report) return { level: 'neutral', label: 'Waiting for FFT', detail: 'Add a waveform and optional engineering mask.' };
  const checked = report.limit_exceedances || [];
  const exceeded = checked.filter(item => item.exceeds);
  if (exceeded.length) {
    const worst = Math.min(...exceeded.map(item => Number(item.margin_db)).filter(Number.isFinite));
    return { level: 'danger', label: `${exceeded.length} mask exceedance${exceeded.length === 1 ? '' : 's'}`, detail: Number.isFinite(worst) ? `Worst margin ${worst.toFixed(1)} dB` : 'Engineering mask exceeded' };
  }
  if (checked.length) {
    const margin = Math.min(...checked.map(item => Number(item.margin_db)).filter(Number.isFinite));
    return { level: margin < 3 ? 'warning' : 'good', label: margin < 3 ? 'Low EMI headroom' : 'Mask clear', detail: Number.isFinite(margin) ? `Minimum peak margin +${margin.toFixed(1)} dB` : 'No peak exceeds the mask' };
  }
  return { level: 'neutral', label: 'Spectrum mapped', detail: `${(report.peaks || []).length} dominant peaks · add a mask for margin` };
}

function renderRFDashboard() {
  const match = rfMatchAssessment();
  const resonance = rfResonanceAssessment();
  const noise = rfNoiseAssessment();
  const openemsReady = Boolean(state.rfCapabilities?.openems?.available);
  const construction = state.rfPatch
    ? (state.rfPatchDirty
      ? { level: 'warning', label: 'Geometry edited', detail: 'Recalculate/export the model before treating it as the current full-wave seed.' }
      : { level: openemsReady ? 'good' : 'warning', label: openemsReady ? 'Full-wave ready' : 'Geometry ready', detail: openemsReady ? 'openEMS solver is available for the next iteration.' : 'Install/sync openEMS for full-wave verification.' })
    : { level: 'neutral', label: 'Seed model', detail: 'Use actual stack-up values before fabrication.' };
  const cards = [
    ['◎', 'Target match', match],
    ['↔', 'Resonance placement', resonance],
    ['⌁', 'EMI headroom', noise],
    ['◇', 'Construction confidence', construction],
  ];
  $('#rfOverviewStats').innerHTML = cards.map(([icon, title, assessment]) => `
    <article class="rf-kpi-card ${rfStatusClass(assessment.level)}"><span class="rf-kpi-icon">${icon}</span><div><small>${escapeHtml(title)}</small><strong>${escapeHtml(assessment.label)}</strong><p>${escapeHtml(assessment.detail)}</p></div></article>`).join('');

  rfSetBadge('#rfMatchBadge', match.label, match.level);
  rfSetBadge('#rfNoiseBadge', noise.label, noise.level);
  const levels = [match.level, resonance.level, noise.level, construction.level];
  const overall = levels.includes('danger') ? 'danger' : levels.includes('warning') ? 'warning' : (state.rfPatch && state.rfTouchstone && state.rfNoise ? 'good' : 'neutral');
  rfSetBadge('#rfOverallBadge', overall === 'good' ? 'coherent' : overall === 'danger' ? 'action needed' : overall === 'warning' ? 'review' : 'waiting', overall);

  const geometryText = state.rfPatch
    ? `Patch seed is ${(Number(state.rfPatch.patch_width_m) * 1e3).toFixed(2)} × ${(Number(state.rfPatch.patch_length_m) * 1e3).toFixed(2)} mm. ${openemsReady ? 'Full-wave solver is ready.' : 'Full-wave solver is still optional/missing.'}`
    : 'Enter the real dielectric constant and thickness, then calculate a patch seed.';
  const matchText = state.rfTouchstone
    ? `${match.detail}. ${resonance.detail}.`
    : 'Import S1P/S2P from openEMS or a VNA to place resonance and inspect impedance.';
  const noiseText = state.rfNoise
    ? `${noise.detail}. Fundamental ${formatFrequency(state.rfNoise.fundamental_hz)}; Nyquist ${formatFrequency(state.rfNoise.nyquist_hz)}.`
    : 'FFT a fast switching node, supply-current proxy or simulation telemetry channel.';
  const sourceInfo = rfSystemRiskSummary();
  $('#rfVisualGuidance').innerHTML = [
    ['1', state.rfPatch ? 'good' : 'neutral', state.rfPatch ? 'Physical seed defined' : 'Define the physical seed', geometryText],
    ['2', match.level, match.label, matchText],
    ['3', noise.level, noise.label, noiseText],
    ['4', sourceInfo.level, sourceInfo.title, sourceInfo.detail],
  ].map(([number, level, title, detail]) => `<div class="rf-guidance-item ${rfStatusClass(level)}"><span>${number}</span><div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(detail)}</p></div></div>`).join('');

  const setFlow = (selector, level) => { const el = $(selector); if (el) el.className = `rf-workflow-step ${rfStatusClass(level)}`; };
  setFlow('#rfFlowConstruction', state.rfPatch ? construction.level : 'neutral');
  setFlow('#rfFlowMatch', state.rfTouchstone ? (match.level === 'danger' ? 'danger' : resonance.level) : 'neutral');
  setFlow('#rfFlowNoise', state.rfNoise ? noise.level : 'neutral');
  setFlow('#rfFlowDecision', state.rfPatch && state.rfTouchstone && state.rfNoise ? overall : 'neutral');
}

function rfSystemRisk(node) {
  const haystack = `${node.label || ''} ${node.kind || ''} ${node.bus || ''} ${node.componentId || ''}`.toLowerCase();
  const high = ['pwm', 'clock', 'oscillator', 'buck', 'boost', 'switch', 'smps', 'motor', 'dc-dc', 'ddr', 'ethernet', 'usb', 'spi', 'can'];
  const medium = ['uart', 'i2c', 'display', 'led', 'gpio', 'radio', 'ble', 'wifi', 'rf'];
  if (high.some(term => haystack.includes(term))) return { score: 3, level: 'high', label: 'high edge-rate risk' };
  if (medium.some(term => haystack.includes(term))) return { score: 2, level: 'medium', label: 'moderate coupling risk' };
  return { score: 1, level: 'low', label: 'lower heuristic risk' };
}

function rfSystemRiskSummary() {
  const ranked = (state.graph?.nodes || []).map(node => ({ node, risk: rfSystemRisk(node) })).sort((a,b) => b.risk.score - a.risk.score);
  if (!ranked.length) return { level: 'neutral', title: 'Map system noise sources', detail: 'Load or build a project graph to highlight clocks, PWM, switch-mode power and fast digital buses.' };
  const high = ranked.filter(item => item.risk.score === 3);
  if (high.length) return { level: 'warning', title: 'Review high edge-rate sources', detail: `${high.length} node${high.length === 1 ? '' : 's'} may deserve spectral checks: ${high.slice(0,3).map(item => item.node.label).join(', ')}.` };
  return { level: 'good', title: 'No obvious high-risk source', detail: `${ranked.length} project nodes scanned heuristically; still verify real switching waveforms and return paths.` };
}

function renderRFSystemSources() {
  const container = $('#rfSystemSources');
  if (!container) return;
  const ranked = (state.graph?.nodes || []).map(node => ({ node, risk: rfSystemRisk(node) })).sort((a,b) => b.risk.score - a.risk.score).slice(0, 7);
  if (!ranked.length) {
    container.innerHTML = '<div class="empty-state">Load a system in Designer to correlate likely clocks, PWM, power switching and fast buses with the RF view.</div>';
    return;
  }
  container.innerHTML = ranked.map(({node, risk}) => `<div class="rf-source-item ${risk.level}"><i></i><div><strong>${escapeHtml(node.label || node.componentId || 'component')}</strong><small>${escapeHtml(`${node.kind || 'component'} · ${node.bus || 'no bus'}`)}</small></div><em>${escapeHtml(risk.label)}</em></div>`).join('');
}

function renderRFConstruction() {
  const svg = $('#rfConstructionSvg');
  if (!svg) return;
  const patch = state.rfPatch || {};
  const widthMm = Number($('#rfPatchWidth')?.value) || Number(patch.patch_width_m) * 1e3;
  const lengthMm = Number($('#rfPatchLength')?.value) || Number(patch.patch_length_m) * 1e3;
  const feedMm = Number($('#rfPatchFeed')?.value);
  const er = Number($('#rfPatchEr')?.value);
  const hMm = Number($('#rfPatchH')?.value);
  const loss = Number($('#rfPatchLoss')?.value);
  const targetMHz = Number($('#rfTargetMHz')?.value);
  const substrateW = Number(patch.substrate_width_m) * 1e3;
  const substrateL = Number(patch.substrate_length_m) * 1e3;
  const hasGeometry = Number.isFinite(widthMm) && widthMm > 0 && Number.isFinite(lengthMm) && lengthMm > 0;

  if (!hasGeometry) {
    svg.innerHTML = `<rect x="38" y="42" width="470" height="270" rx="18" fill="#123529" stroke="#2c765f" stroke-width="2"/><rect x="155" y="105" width="236" height="145" rx="3" fill="none" stroke="#e6a352" stroke-width="2" stroke-dasharray="8 7"/><text x="273" y="172" text-anchor="middle" fill="#a9bed1" font-size="16" font-weight="700">PATCH GEOMETRY</text><text x="273" y="198" text-anchor="middle" fill="#718ba2" font-size="12">Calculate seed to scale construction</text><path d="M509 177 H650" stroke="#45657f" stroke-width="2" stroke-dasharray="6 6"/><text x="578" y="162" text-anchor="middle" fill="#718ba2" font-size="11">FEED / MATCH</text><circle cx="650" cy="177" r="9" fill="#0d1720" stroke="#66e0ff" stroke-width="2"/>`;
  } else {
    const boardRatio = Number.isFinite(substrateL) && Number.isFinite(substrateW) && substrateW > 0 ? substrateL / substrateW : lengthMm / widthMm;
    let boardW = 430, boardH = Math.max(170, Math.min(260, boardW / Math.max(boardRatio, .65)));
    if (boardH > 250) { boardH = 250; boardW = Math.max(280, boardH * boardRatio); }
    const bx = 42, by = 42;
    const physicalBoardL = Number.isFinite(substrateL) && substrateL > lengthMm ? substrateL : lengthMm * 1.45;
    const physicalBoardW = Number.isFinite(substrateW) && substrateW > widthMm ? substrateW : widthMm * 1.45;
    const patchWpx = boardW * Math.min(.82, lengthMm / physicalBoardL);
    const patchHpx = boardH * Math.min(.82, widthMm / physicalBoardW);
    const px = bx + (boardW - patchWpx)/2, py = by + (boardH - patchHpx)/2;
    const feedPosition = Number.isFinite(feedMm) ? Math.max(-lengthMm/2, Math.min(lengthMm/2, feedMm)) : -0.18 * lengthMm;
    const fx = px + patchWpx/2 + (feedPosition / lengthMm) * patchWpx;
    const fy = py + patchHpx/2;
    const sideY = 332;
    svg.innerHTML = `
      <defs><marker id="rfArrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#6f8ca4"/></marker></defs>
      <text x="42" y="24" fill="#718ba2" font-size="10" font-weight="700" letter-spacing="1.4">TOP VIEW · PHYSICAL SCALE PROPORTION</text>
      <rect x="${bx}" y="${by}" width="${boardW.toFixed(1)}" height="${boardH.toFixed(1)}" rx="15" fill="#123f32" stroke="#2d8068" stroke-width="2"/>
      <rect x="${(bx+14).toFixed(1)}" y="${(by+14).toFixed(1)}" width="${(boardW-28).toFixed(1)}" height="${(boardH-28).toFixed(1)}" rx="8" fill="none" stroke="#5c8294" stroke-width="1" stroke-dasharray="6 5" opacity=".75"/>
      <rect x="${px.toFixed(1)}" y="${py.toFixed(1)}" width="${patchWpx.toFixed(1)}" height="${patchHpx.toFixed(1)}" rx="2" fill="#c98335" stroke="#ffc06c" stroke-width="2"/>
      <line x1="${fx.toFixed(1)}" y1="${(by+boardH).toFixed(1)}" x2="${fx.toFixed(1)}" y2="${fy.toFixed(1)}" stroke="#ffd07a" stroke-width="5"/>
      <circle cx="${fx.toFixed(1)}" cy="${fy.toFixed(1)}" r="6" fill="#071019" stroke="#66e0ff" stroke-width="2"/>
      <line x1="${px.toFixed(1)}" y1="${(py-17).toFixed(1)}" x2="${(px+patchWpx).toFixed(1)}" y2="${(py-17).toFixed(1)}" stroke="#7896ae" marker-start="url(#rfArrow)" marker-end="url(#rfArrow)"/>
      <text x="${(px+patchWpx/2).toFixed(1)}" y="${(py-23).toFixed(1)}" text-anchor="middle" fill="#aabed0" font-size="11">L ${lengthMm.toFixed(2)} mm</text>
      <line x1="${(px-17).toFixed(1)}" y1="${py.toFixed(1)}" x2="${(px-17).toFixed(1)}" y2="${(py+patchHpx).toFixed(1)}" stroke="#7896ae" marker-start="url(#rfArrow)" marker-end="url(#rfArrow)"/>
      <text x="${(px-25).toFixed(1)}" y="${(py+patchHpx/2).toFixed(1)}" text-anchor="middle" fill="#aabed0" font-size="11" transform="rotate(-90 ${(px-25).toFixed(1)} ${(py+patchHpx/2).toFixed(1)})">W ${widthMm.toFixed(2)} mm</text>
      <path d="M${(fx+7).toFixed(1)} ${(fy-4).toFixed(1)} L${(fx+67).toFixed(1)} ${(fy-33).toFixed(1)}" stroke="#66e0ff" stroke-width="1"/>
      <text x="${(fx+72).toFixed(1)}" y="${(fy-36).toFixed(1)}" fill="#92b6cd" font-size="10">feed ${Number.isFinite(feedMm) ? feedMm.toFixed(2) : 'auto'} mm</text>
      <g transform="translate(535 54)">
        <text x="0" y="0" fill="#718ba2" font-size="10" font-weight="700" letter-spacing="1.2">STACK-UP</text>
        <rect x="0" y="28" width="175" height="7" rx="2" fill="#e6a352"/><text x="185" y="35" fill="#aabed0" font-size="10">patch copper</text>
        <rect x="0" y="35" width="175" height="54" rx="2" fill="#1d6b55"/><text x="185" y="64" fill="#aabed0" font-size="10">εr ${Number.isFinite(er) ? er.toFixed(2) : '—'}</text>
        <rect x="0" y="89" width="175" height="8" rx="2" fill="#71849a"/><text x="185" y="97" fill="#aabed0" font-size="10">ground plane</text>
        <line x1="-12" y1="35" x2="-12" y2="89" stroke="#7896ae" marker-start="url(#rfArrow)" marker-end="url(#rfArrow)"/><text x="-22" y="66" text-anchor="middle" fill="#aabed0" font-size="10" transform="rotate(-90 -22 66)">h ${Number.isFinite(hMm) ? hMm.toFixed(2) : '—'} mm</text>
        <text x="0" y="126" fill="#718ba2" font-size="10">tanδ ${Number.isFinite(loss) ? loss.toFixed(4) : '—'}</text>
        <text x="0" y="145" fill="#66e0ff" font-size="12" font-weight="700">${Number.isFinite(targetMHz) ? targetMHz.toFixed(2) : '—'} MHz target</text>
      </g>
      <text x="42" y="${sideY}" fill="#718ba2" font-size="10" font-weight="700" letter-spacing="1.2">CURRENT / COUPLING INTUITION</text>
      <path d="M70 ${sideY+29} C140 ${sideY-8}, 220 ${sideY+64}, 302 ${sideY+29} S445 ${sideY-7}, 500 ${sideY+29}" fill="none" stroke="#66e0ff" stroke-width="2" opacity=".8"/>
      <text x="70" y="${sideY+52}" fill="#91a8bb" font-size="10">feed</text><text x="260" y="${sideY+52}" fill="#91a8bb" font-size="10">dominant resonant path</text><text x="462" y="${sideY+52}" fill="#91a8bb" font-size="10">fringing field</text>
    `;
  }

  const facts = [
    ['Target', Number.isFinite(targetMHz) && targetMHz > 0 ? `${targetMHz.toFixed(2)} MHz` : '—'],
    ['Patch', hasGeometry ? `${lengthMm.toFixed(2)} × ${widthMm.toFixed(2)} mm` : 'not calculated'],
    ['Dielectric', Number.isFinite(er) ? `εr ${er.toFixed(3)}` : '—'],
    ['Thickness', Number.isFinite(hMm) ? `${hMm.toFixed(3)} mm` : '—'],
    ['Feed offset', Number.isFinite(feedMm) ? `${feedMm.toFixed(3)} mm` : 'auto'],
    ['Sweep', patch.sweep_low_hz ? `${formatFrequency(patch.sweep_low_hz)} → ${formatFrequency(patch.sweep_high_hz)}` : 'not generated'],
  ];
  $('#rfConstructionFacts').innerHTML = facts.map(([label,value]) => `<div class="rf-fact"><small>${escapeHtml(label)}</small><strong>${escapeHtml(value)}</strong></div>`).join('');
  const badge = $('#rfConstructionBadge');
  badge.textContent = state.rfPatch ? (state.rfPatchDirty ? 'edited · regenerate' : (state.rfCapabilities?.openems?.available ? 'full-wave ready' : 'geometry ready')) : 'analytical seed';
  badge.className = `pill ${state.rfPatch ? (state.rfPatchDirty ? 'warning' : (state.rfCapabilities?.openems?.available ? 'ok' : 'warning')) : ''}`;
  renderRFSystemSources();
}

function renderRFTouchstone(report) {
  const best = report.best_match || {};
  const target = report.target || {};
  const tuning = report.tuning || {};
  const bandwidth = report.bandwidth;
  const resonanceDelta = Number(best.frequency_hz) && Number($('#rfTargetMHz').value) ? (Number(best.frequency_hz) / (Number($('#rfTargetMHz').value)*1e6) - 1) * 100 : null;
  $('#rfAntennaStats').innerHTML = [
    ['Best S11', Number(best.s11_db).toFixed(2) + ' dB', 'deepest resonance in sweep'],
    ['Resonance', formatFrequency(best.frequency_hz), Number.isFinite(resonanceDelta) ? `${resonanceDelta >= 0 ? '+' : ''}${resonanceDelta.toFixed(2)}% from target` : 'best-match point'],
    ['Target S11', target.s11_db === undefined ? '—' : Number(target.s11_db).toFixed(2) + ' dB', 'value nearest target frequency'],
    ['Target VSWR', target.vswr === null || target.vswr === undefined ? '—' : Number(target.vswr).toFixed(3), '1.0 is ideal'],
    ['Accepted power', target.accepted_power_percent === undefined ? '—' : Number(target.accepted_power_percent).toFixed(2) + '%', 'from |Γ|², not radiation efficiency'],
    ['−RL bandwidth', bandwidth ? formatFrequency(bandwidth.width_hz) : 'not reached', bandwidth ? `${formatFrequency(bandwidth.low_hz)} → ${formatFrequency(bandwidth.high_hz)}` : 'return-loss threshold not met'],
  ].map(([label,value,note]) => `<div class="stat"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(note)}</small></div>`).join('');
  const z = target.impedance_ohms;
  const match = tuning.series_reactance_cancellation || {};
  const component = match.type === 'series_inductor' ? formatEngineering(match.inductance_h, 'H') :
    match.type === 'series_capacitor' ? formatEngineering(match.capacitance_f, 'F') : 'none';
  $('#rfTuningReport').classList.remove('empty-state');
  $('#rfTuningReport').innerHTML = `<table>
    <tr class="key-row"><th>Target impedance</th><td>${z ? `${Number(z.real).toFixed(2)} ${Number(z.imag) >= 0 ? '+' : '−'} j${Math.abs(Number(z.imag)).toFixed(2)} Ω` : '—'}</td></tr>
    <tr><th>Resonant path change</th><td>${tuning.geometry_change_percent === undefined ? '—' : `${Number(tuning.geometry_change_percent).toFixed(2)}% · ${escapeHtml(tuning.geometry_direction)}`}</td></tr>
    <tr><th>First-order series compensation</th><td>${escapeHtml(match.type || '—')} · ${escapeHtml(component)}</td></tr>
    <tr><th>¼ wavelength at target</th><td>${tuning.quarter_wavelength_m ? formatEngineering(tuning.quarter_wavelength_m, 'm') : '—'}</td></tr>
  </table><p class="warning-text">${escapeHtml(tuning.warning || '')}</p>`;
  drawRFS11Chart(report);
  drawRFSmithChart(report);
  renderRFDashboard();
  renderRFConstruction();
}

function renderRFPeakLadder(report) {
  const container = $('#rfPeakLadder');
  if (!container) return;
  const peaks = (report.peaks || []).slice(0, 10);
  if (!peaks.length) { container.className = 'rf-peak-ladder empty-state'; container.textContent = 'No dominant spectral peaks were detected.'; return; }
  container.className = 'rf-peak-ladder';
  const max = Math.max(...peaks.map(item => Number(item.dbuv_rms)).filter(Number.isFinite));
  const min = Math.min(...peaks.map(item => Number(item.dbuv_rms)).filter(Number.isFinite));
  const exceededFreqs = new Set((report.limit_exceedances || []).filter(item => item.exceeds).map(item => Number(item.frequency_hz).toPrecision(12)));
  container.innerHTML = peaks.map(item => {
    const dbuv = Number(item.dbuv_rms);
    const strength = Number.isFinite(dbuv) ? Math.max(1, Math.min(5, 1 + 4 * (dbuv - min) / Math.max(max - min, 1e-6))) : 1;
    const exceeded = exceededFreqs.has(Number(item.frequency_hz).toPrecision(12));
    return `<div class="rf-peak-chip ${exceeded ? 'exceeds' : ''}" style="--peak-height:${strength.toFixed(1)}px"><strong>${item.harmonic ? `H${item.harmonic} · ` : ''}${escapeHtml(formatFrequency(item.frequency_hz))}</strong><small>${Number(item.dbuv_rms).toFixed(1)} dBµV · ${Number(item.dbm).toFixed(1)} dBm${exceeded ? ' · OVER MASK' : ''}</small></div>`;
  }).join('');
}

function renderRFNoise(report) {
  $('#rfNoiseStats').innerHTML = [
    ['Sample rate', formatFrequency(report.sample_rate_hz), 'waveform sampling'],
    ['Nyquist', formatFrequency(report.nyquist_hz), 'upper inferable frequency'],
    ['FFT bins', report.samples_fft, `${report.samples_input} input samples`],
    ['Bin width', formatFrequency(report.bin_width_hz), 'frequency resolution'],
    ['Fundamental', formatFrequency(report.fundamental_hz), 'lowest meaningful peak'],
    ['Timing jitter', Number(report.sample_interval_jitter_percent || 0).toFixed(3) + '%', Number(report.sample_interval_jitter_percent || 0) > 1 ? 'resampling recommended' : 'sampling grid quality'],
  ].map(([label,value,note]) => `<div class="stat"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(note)}</small></div>`).join('');
  const peaks = report.peaks || [];
  const exceeded = (report.limit_exceedances || []).filter(item => item.exceeds);
  $('#rfNoiseReport').classList.remove('empty-state');
  $('#rfNoiseReport').innerHTML = `<h3>Spectral peaks</h3>${tableFromObjects(peaks.slice(0, 30).map(item => ({
      frequency: formatFrequency(item.frequency_hz), dBuV: Number(item.dbuv_rms).toFixed(2), dBm: Number(item.dbm).toFixed(2), harmonic: item.harmonic || '—'
    })), ['frequency','dBuV','dBm','harmonic'])}
    ${exceeded.length ? `<h3 class="danger-text">Custom-mask exceedances</h3>${tableFromObjects(exceeded, ['frequency_hz','level','limit','margin_db','unit'])}` : ''}
    <h3>Interpretation limits</h3><ul>${(report.warnings || []).map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
    <p class="warning-text">${escapeHtml(report.compliance?.reason || '')}</p>`;
  renderRFPeakLadder(report);
  drawRFNoiseSpectrum(report);
  renderRFDashboard();
}

function rfPrepareCanvas(selector) {
  const canvas = $(selector);
  if (!canvas) return null;
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * ratio));
  canvas.height = Math.max(1, Math.floor(rect.height * ratio));
  const ctx = canvas.getContext('2d');
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, rect.width, rect.height);
  return { canvas, ctx, width: rect.width, height: rect.height };
}

function rfNoData(canvasInfo, message) {
  const {ctx} = canvasInfo;
  ctx.fillStyle = '#90a2b7'; ctx.font = '13px sans-serif'; ctx.fillText(message, 18, 28);
}

function rfDrawAxes(ctx, width, height, box, xLabels, yLabels) {
  const {left,right,top,bottom} = box;
  ctx.strokeStyle = 'rgba(90,120,150,.18)'; ctx.lineWidth = 1;
  for (let i=0;i<xLabels.length;i++) {
    const x = left + i * (width-left-right) / Math.max(xLabels.length-1,1);
    ctx.beginPath(); ctx.moveTo(x,top); ctx.lineTo(x,height-bottom); ctx.stroke();
  }
  for (let i=0;i<yLabels.length;i++) {
    const y = top + i * (height-top-bottom) / Math.max(yLabels.length-1,1);
    ctx.beginPath(); ctx.moveTo(left,y); ctx.lineTo(width-right,y); ctx.stroke();
  }
  ctx.fillStyle='#7f97ad'; ctx.font='10px sans-serif';
  xLabels.forEach((label,i) => {
    const x = left + i * (width-left-right) / Math.max(xLabels.length-1,1);
    const measured = ctx.measureText(label).width;
    ctx.fillText(label, Math.min(width-right-measured, Math.max(left, x-measured/2)), height-10);
  });
  yLabels.forEach((label,i) => {
    const y = top + i * (height-top-bottom) / Math.max(yLabels.length-1,1);
    ctx.fillText(label, 7, y+3);
  });
}

function rfNearestByFrequency(points, frequency) {
  if (!points.length) return null;
  let low = 0, high = points.length - 1;
  while (low < high) {
    const mid = Math.floor((low + high) / 2);
    if (Number(points[mid].frequency_hz) < frequency) low = mid + 1; else high = mid;
  }
  const a = points[Math.max(0, low-1)], b = points[low];
  return !a || Math.abs(Number(b.frequency_hz)-frequency) < Math.abs(Number(a.frequency_hz)-frequency) ? b : a;
}

function rfInstallFrequencyCursor(canvas, {left,right,top,bottom,minX,maxX,logX,points,formatter}) {
  canvas.onpointermove = event => {
    const rect = canvas.getBoundingClientRect();
    const x = Math.max(left, Math.min(rect.width-right, event.clientX-rect.left));
    const ratio = (x-left) / Math.max(rect.width-left-right, 1);
    const frequency = logX ? 10 ** (Math.log10(minX) + ratio * (Math.log10(maxX)-Math.log10(minX))) : minX + ratio * (maxX-minX);
    const point = rfNearestByFrequency(points, frequency);
    if (point) $('#rfCursorReadout').textContent = formatter(point);
  };
  canvas.onpointerleave = () => { $('#rfCursorReadout').textContent = 'Move over an RF plot to inspect the nearest point.'; };
}

function drawRFS11Chart(report) {
  const info = rfPrepareCanvas('#rfS11Canvas'); if (!info) return;
  const {canvas,ctx,width,height} = info;
  const points = (report.trace || []).filter(row => Number.isFinite(Number(row.frequency_hz)) && Number.isFinite(Number(row.s11_db)));
  if (points.length < 2) return rfNoData(info, 'No S11 trace data');
  const box={left:58,right:16,top:14,bottom:34};
  const minX=Number(points[0].frequency_hz), maxX=Number(points[points.length-1].frequency_hz);
  const rawMin=Math.min(...points.map(p=>Number(p.s11_db)));
  const threshold=-Math.abs(Number($('#rfReturnLoss').value)||10);
  const minY=Math.min(-20, Math.floor((rawMin-3)/5)*5), maxY=0;
  const xPx=f=>box.left+(f-minX)/Math.max(maxX-minX,1e-15)*(width-box.left-box.right);
  const yPx=v=>box.top+(maxY-v)/(maxY-minY)*(height-box.top-box.bottom);
  const thresholdY=yPx(threshold), marginalY=yPx(threshold/2);
  ctx.fillStyle='rgba(85,214,169,.055)'; ctx.fillRect(box.left,thresholdY,width-box.left-box.right,height-box.bottom-thresholdY);
  ctx.fillStyle='rgba(255,202,105,.045)'; ctx.fillRect(box.left,marginalY,width-box.left-box.right,thresholdY-marginalY);
  const xLabels=Array.from({length:5},(_,i)=>formatFrequency(minX+i*(maxX-minX)/4));
  const yLabels=Array.from({length:5},(_,i)=>(maxY-i*(maxY-minY)/4).toFixed(0)+' dB');
  rfDrawAxes(ctx,width,height,box,xLabels,yLabels);
  ctx.strokeStyle='#55d6be'; ctx.lineWidth=1.8; ctx.beginPath();
  points.forEach((point,index)=>{const x=xPx(Number(point.frequency_hz)),y=yPx(Number(point.s11_db)); if(index===0)ctx.moveTo(x,y); else ctx.lineTo(x,y);}); ctx.stroke();
  ctx.setLineDash([5,4]); ctx.strokeStyle='rgba(85,214,169,.7)'; ctx.beginPath();ctx.moveTo(box.left,thresholdY);ctx.lineTo(width-box.right,thresholdY);ctx.stroke();ctx.setLineDash([]);
  const targetHz=Number($('#rfTargetMHz').value)*1e6;
  if(Number.isFinite(targetHz)&&targetHz>=minX&&targetHz<=maxX){const tx=xPx(targetHz);ctx.strokeStyle='rgba(102,224,255,.65)';ctx.setLineDash([3,4]);ctx.beginPath();ctx.moveTo(tx,box.top);ctx.lineTo(tx,height-box.bottom);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#66e0ff';ctx.font='10px sans-serif';ctx.fillText('TARGET',Math.min(tx+5,width-58),box.top+11);}
  const markers=[['best_match','#ffca69','BEST'],['target','#66e0ff','TARGET']];
  markers.forEach(([key,color,label])=>{const p=report[key];if(!p||!Number.isFinite(Number(p.frequency_hz)))return;const x=xPx(Number(p.frequency_hz)),y=yPx(Number(p.s11_db));ctx.fillStyle=color;ctx.beginPath();ctx.arc(x,y,4.2,0,Math.PI*2);ctx.fill();ctx.fillStyle=color;ctx.font='9px sans-serif';ctx.fillText(label,x+6,Math.max(box.top+9,y-5));});
  rfInstallFrequencyCursor(canvas,{...box,minX,maxX,logX:false,points,formatter:p=>`${formatFrequency(p.frequency_hz)} · S11 ${Number(p.s11_db).toFixed(2)} dB · VSWR ${p.vswr==null?'∞':Number(p.vswr).toFixed(2)} · Z ${Number(p.impedance_ohms?.real).toFixed(1)} ${Number(p.impedance_ohms?.imag)>=0?'+':'−'} j${Math.abs(Number(p.impedance_ohms?.imag)).toFixed(1)} Ω`});
}

function drawRFSmithChart(report) {
  const info=rfPrepareCanvas('#rfSmithCanvas'); if(!info)return;
  const {canvas,ctx,width,height}=info;
  const points=(report.trace||[]).filter(row=>Number.isFinite(Number(row.gamma?.real))&&Number.isFinite(Number(row.gamma?.imag)));
  if(points.length<2)return rfNoData(info,'No reflection-coefficient data');
  const radius=Math.max(30,Math.min(width-32,height-28)/2), cx=width/2, cy=height/2+2;
  ctx.save();ctx.beginPath();ctx.arc(cx,cy,radius,0,Math.PI*2);ctx.clip();
  ctx.fillStyle='#081119';ctx.fillRect(cx-radius,cy-radius,2*radius,2*radius);
  ctx.strokeStyle='rgba(102,132,158,.23)';ctx.lineWidth=1;
  [0,.2,.5,1,2,5].forEach(r=>{const c=r/(1+r),rad=1/(1+r);ctx.beginPath();ctx.arc(cx+c*radius,cy,rad*radius,0,Math.PI*2);ctx.stroke();});
  [.2,.5,1,2,5].forEach(x=>{[1,-1].forEach(sign=>{const v=x*sign;ctx.beginPath();ctx.arc(cx+radius,cy-(1/v)*radius,Math.abs(1/v)*radius,0,Math.PI*2);ctx.stroke();});});
  ctx.strokeStyle='rgba(115,145,170,.34)';ctx.beginPath();ctx.moveTo(cx-radius,cy);ctx.lineTo(cx+radius,cy);ctx.stroke();
  ctx.strokeStyle='#66e0ff';ctx.lineWidth=1.7;ctx.beginPath();points.forEach((p,i)=>{const x=cx+Number(p.gamma.real)*radius,y=cy-Number(p.gamma.imag)*radius;if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);});ctx.stroke();
  ctx.restore();ctx.strokeStyle='#5e7990';ctx.lineWidth=1.2;ctx.beginPath();ctx.arc(cx,cy,radius,0,Math.PI*2);ctx.stroke();
  ctx.fillStyle='#7f97ad';ctx.font='9px sans-serif';ctx.fillText('0 Ω',cx-radius+5,cy-5);ctx.fillText('50 Ω',cx+4,cy-5);ctx.fillText('∞',cx+radius-10,cy-5);
  const markers=[['best_match','#ffca69'],['target','#55d6be']];markers.forEach(([key,color])=>{const p=report[key];if(!p?.gamma)return;const x=cx+Number(p.gamma.real)*radius,y=cy-Number(p.gamma.imag)*radius;ctx.fillStyle=color;ctx.beginPath();ctx.arc(x,y,4.5,0,Math.PI*2);ctx.fill();});
  canvas.onpointermove=event=>{const rect=canvas.getBoundingClientRect();const mx=event.clientX-rect.left,my=event.clientY-rect.top;let best=null,bestD=Infinity;points.forEach(p=>{const x=cx+Number(p.gamma.real)*radius,y=cy-Number(p.gamma.imag)*radius,d=(x-mx)**2+(y-my)**2;if(d<bestD){bestD=d;best=p;}});if(best)$('#rfCursorReadout').textContent=`${formatFrequency(best.frequency_hz)} · Γ ${Number(best.gamma.magnitude).toFixed(3)} ∠ ${Number(best.gamma.phase_deg).toFixed(1)}° · Z ${Number(best.impedance_ohms.real).toFixed(1)} ${Number(best.impedance_ohms.imag)>=0?'+':'−'} j${Math.abs(Number(best.impedance_ohms.imag)).toFixed(1)} Ω`;};
  canvas.onpointerleave=()=>{$('#rfCursorReadout').textContent='Move over an RF plot to inspect the nearest point.';};
}

function rfLimitMaskAsDbuv() {
  try {
    const impedance=Number($('#rfImpedance').value)||50;
    return parseRFLimitMask().map(item=>{const unit=String(item.unit||'dBuV').toLowerCase();let value=Number(item.limit);if(unit==='dbv')value+=120;else if(unit==='dbm')value+=90+10*Math.log10(impedance);return {frequency_hz:Number(item.frequency_hz),limit_dbuv:value};}).filter(item=>Number.isFinite(item.frequency_hz)&&item.frequency_hz>0&&Number.isFinite(item.limit_dbuv)).sort((a,b)=>a.frequency_hz-b.frequency_hz);
  } catch (_) { return []; }
}

function drawRFNoiseSpectrum(report) {
  const info=rfPrepareCanvas('#rfNoiseCanvas');if(!info)return;
  const {canvas,ctx,width,height}=info;
  const points=(report.trace||[]).filter(row=>Number(row.frequency_hz)>0&&Number.isFinite(Number(row.dbuv_rms)));
  if(points.length<2)return rfNoData(info,'No RF spectrum data');
  const box={left:58,right:16,top:14,bottom:34};
  const minX=Math.max(Number(points[0].frequency_hz),1e-30),maxX=Number(points[points.length-1].frequency_hz);
  const mask=rfLimitMaskAsDbuv();
  const values=points.map(p=>Number(p.dbuv_rms)).concat(mask.map(p=>p.limit_dbuv));
  let minY=Math.floor((Math.min(...values)-6)/10)*10,maxY=Math.ceil((Math.max(...values)+6)/10)*10;if(minY===maxY){minY-=10;maxY+=10;}
  const lx0=Math.log10(minX),lx1=Math.log10(maxX),xPx=f=>box.left+(Math.log10(Math.max(f,minX))-lx0)/Math.max(lx1-lx0,1e-15)*(width-box.left-box.right),yPx=v=>box.top+(maxY-v)/(maxY-minY)*(height-box.top-box.bottom);
  const xLabels=Array.from({length:5},(_,i)=>formatFrequency(10**(lx0+i*(lx1-lx0)/4)));const yLabels=Array.from({length:5},(_,i)=>(maxY-i*(maxY-minY)/4).toFixed(0)+' dBµV');rfDrawAxes(ctx,width,height,box,xLabels,yLabels);
  ctx.strokeStyle='#66e0ff';ctx.lineWidth=1.25;ctx.beginPath();points.forEach((p,i)=>{const x=xPx(Number(p.frequency_hz)),y=yPx(Number(p.dbuv_rms));if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);});ctx.stroke();
  if(mask.length>=2){ctx.strokeStyle='#ff7184';ctx.lineWidth=1.6;ctx.setLineDash([6,4]);ctx.beginPath();mask.forEach((p,i)=>{const x=xPx(p.frequency_hz),y=yPx(p.limit_dbuv);if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);});ctx.stroke();ctx.setLineDash([]);}
  const peaks=(report.peaks||[]).slice(0,12);const exceeded=new Set((report.limit_exceedances||[]).filter(item=>item.exceeds).map(item=>Number(item.frequency_hz).toPrecision(12)));peaks.forEach((p,i)=>{const x=xPx(Number(p.frequency_hz)),y=yPx(Number(p.dbuv_rms));ctx.fillStyle=exceeded.has(Number(p.frequency_hz).toPrecision(12))?'#ff7184':(i<3?'#ffca69':'#66e0ff');ctx.beginPath();ctx.arc(x,y,i<3?3.8:2.6,0,Math.PI*2);ctx.fill();});
  rfInstallFrequencyCursor(canvas,{...box,minX,maxX,logX:true,points,formatter:p=>`${formatFrequency(p.frequency_hz)} · ${Number(p.dbuv_rms).toFixed(2)} dBµV · ${Number(p.dbm).toFixed(2)} dBm · ${formatEngineering(p.amplitude_rms, report.value_unit||'V')} RMS`});
}

function drawRFTrace(selector, rows, xKey, yKey, yLabel, logX) {
  // Backwards-compatible generic trace renderer used by older integrations.
  const info=rfPrepareCanvas(selector);if(!info)return;const {ctx,width,height}=info;
  const points=rows.map(row=>({x:Number(row[xKey]),y:Number(row[yKey])})).filter(point=>Number.isFinite(point.x)&&Number.isFinite(point.y)&&(!logX||point.x>0));
  if(points.length<2)return rfNoData(info,'No RF trace data');
  const box={left:58,right:12,top:12,bottom:36},tx=v=>logX?Math.log10(v):v,xs=points.map(p=>tx(p.x)),minX=Math.min(...xs),maxX=Math.max(...xs);let minY=Math.min(...points.map(p=>p.y)),maxY=Math.max(...points.map(p=>p.y));if(minY===maxY){minY-=1;maxY+=1;}const pad=Math.max((maxY-minY)*.08,.5);minY-=pad;maxY+=pad;rfDrawAxes(ctx,width,height,box,[formatFrequency(points[0].x),formatFrequency(points[points.length-1].x)],[`${maxY.toFixed(1)} ${yLabel}`,minY.toFixed(1)]);ctx.strokeStyle=colors[0];ctx.lineWidth=1.7;ctx.beginPath();points.forEach((p,i)=>{const x=box.left+(tx(p.x)-minX)/Math.max(maxX-minX,1e-15)*(width-box.left-box.right),y=box.top+(1-(p.y-minY)/(maxY-minY))*(height-box.top-box.bottom);if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);});ctx.stroke();
}

function installFirmwareEvents() {
  $('#uploadFirmware').addEventListener('click', uploadFirmware);
  $('#analyzeFirmware').addEventListener('click', analyzeFirmware);
  $$('.report-tabs button').forEach(button => button.addEventListener('click', () => {
    state.reportTab = button.dataset.report;
    $$('.report-tabs button').forEach(item => item.classList.toggle('active', item === button));
    renderFirmwareReport();
  }));
}

async function uploadFirmware() {
  const file = $('#firmwareUpload').files[0];
  if (!file) return toast('Choose a firmware file', true);
  const form = new FormData(); form.append('file', file);
  try {
    $('#firmwareProgress').textContent = 'Storing locally…';
    const asset = await api('/api/assets', { method: 'POST', body: form });
    await loadAssets(); $('#firmwareAsset').value = asset.id; $('#sessionFirmware').value = asset.id;
    $('#firmwareProgress').textContent = `Stored as ${asset.sha256.slice(0, 12)}…`;
    toast('Firmware stored locally');
  } catch (error) { toast(error.message, true); }
}

async function analyzeFirmware() {
  const assetId = Number($('#firmwareAsset').value);
  if (!assetId) return toast('Select a firmware asset', true);
  try {
    $('#firmwareProgress').textContent = 'Analyzing…';
    const response = await api('/api/firmware/analyze', { method: 'POST', body: JSON.stringify({ asset_id: assetId, architecture: $('#firmwareArch').value || null }) });
    state.firmwareReport = response.report; state.reportTab = 'summary';
    $$('.report-tabs button').forEach(button => button.classList.toggle('active', button.dataset.report === 'summary'));
    renderFirmwareReport(); $('#firmwareProgress').textContent = `Analysis ${response.id}`;
  } catch (error) { $('#firmwareProgress').textContent = ''; toast(error.message, true); }
}

function renderFirmwareReport() {
  const report = state.firmwareReport; const output = $('#firmwareReport');
  if (!report) return;
  const tab = state.reportTab;
  if (tab === 'summary') {
    output.innerHTML = `<div class="stats-grid">
      ${[['Format', report.format], ['Size', formatBytes(report.size)], ['Entropy', Number(report.entropy).toFixed(4)], ['SHA-256', report.sha256.slice(0, 16)+'…']].map(([label,value])=>`<div class="stat"><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`).join('')}
    </div><h3>Findings</h3>${report.findings.length ? `<table>${report.findings.map(item=>`<tr><td>${escapeHtml(item.severity)}</td><td>${escapeHtml(item.message)}</td><td>0x${Number(item.offset).toString(16)}</td></tr>`).join('')}</table>` : '<p class="muted">No heuristic findings.</p>'}
    <h3>Container metadata</h3><pre>${escapeHtml(JSON.stringify(report.elf || report.uf2 || report.intel_hex || report.raw, null, 2).slice(0, 40000))}</pre>`;
  } else if (tab === 'sections') output.innerHTML = tableFromObjects(report.elf?.sections || [], ['name','type','address','size','entropy']);
  else if (tab === 'symbols') output.innerHTML = tableFromObjects(report.elf?.symbols || [], ['name','address','size','bind','type']);
  else if (tab === 'strings') output.innerHTML = tableFromObjects(report.strings || [], ['offset','encoding','value']);
  else if (tab === 'disassembly') {
    const sections = report.elf?.executable_sections || [];
    const rows = sections.flatMap(section => (section.disassembly || []).map(item => ({ section: section.name, ...item })));
    output.innerHTML = tableFromObjects(rows, ['section','address','bytes','mnemonic','operands']);
  } else if (tab === 'hexdump') output.innerHTML = `<pre>${escapeHtml(report.hexdump_preview)}</pre>`;
}

function tableFromObjects(rows, columns) {
  if (!rows.length) return '<div class="empty-state">No data available. Install optional analysis dependencies when applicable.</div>';
  return `<table><thead><tr>${columns.map(column=>`<th>${escapeHtml(column)}</th>`).join('')}</tr></thead><tbody>${rows.slice(0,5000).map(row=>`<tr>${columns.map(column=>`<td>${escapeHtml(typeof row[column] === 'number' && column.includes('address') ? '0x'+row[column].toString(16) : row[column])}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

function installEmulationEvents() {
  $('#startSession').addEventListener('click', startSession);
}

async function loadSessions() {
  state.sessions = await api('/api/sessions?limit=500');
  const sessionOptions = '<option value="">Select…</option>' + state.sessions.map(session => `<option value="${escapeHtml(session.id)}">${escapeHtml(session.status)} · ${escapeHtml(session.target)} · ${escapeHtml(formatTime(session.started_at))}</option>`).join('');
  $('#monitorSession').innerHTML = sessionOptions;
  $('#rfSession').innerHTML = sessionOptions;
  $('#logSession').innerHTML = '<option value="">All</option>' + sessionOptions.replace('<option value="">Select…</option>', '');
  $('#sessionRows').innerHTML = state.sessions.map(session => `
    <tr><td><span class="pill ${session.status === 'running' ? 'ok' : ''}">${escapeHtml(session.status)}</span></td><td>${escapeHtml(session.target)}</td><td>${formatTime(session.started_at)}</td><td><code>${escapeHtml((session.command || []).join(' '))}</code></td><td>${session.status === 'running' || session.status === 'starting' ? `<button data-stop="${escapeHtml(session.id)}" class="danger">Stop</button>` : ''}</td></tr>`).join('');
  $$('[data-stop]').forEach(button => button.addEventListener('click', () => stopSession(button.dataset.stop)));
}

async function startSession() {
  const payload = {
    target: $('#sessionTarget').value,
    firmware_asset_id: Number($('#sessionFirmware').value) || null,
    platform_asset_id: Number($('#sessionPlatform').value) || null,
    script_asset_id: Number($('#sessionScript').value) || null,
    extra_args: shellSplit($('#sessionArgs').value),
  };
  try {
    const session = await api('/api/sessions', { method: 'POST', body: JSON.stringify(payload) });
    await loadSessions(); $('#monitorSession').value = session.id; toast(`Session ${session.id.slice(0, 8)} started`);
  } catch (error) { toast(error.message, true); }
}

async function stopSession(sessionId) {
  try { await api(`/api/sessions/${sessionId}/stop`, { method: 'POST' }); await loadSessions(); toast('Session stopped'); }
  catch (error) { toast(error.message, true); }
}

function shellSplit(value) {
  const result = []; let current = ''; let quote = null;
  for (let index=0; index<value.length; index++) {
    const character = value[index];
    if (quote) { if (character === quote) quote = null; else current += character; }
    else if (character === '"' || character === "'") quote = character;
    else if (/\s/.test(character)) { if (current) { result.push(current); current=''; } }
    else current += character;
  }
  if (current) result.push(current); return result;
}

function installLogEvents() {
  $('#refreshLogs').addEventListener('click', refreshLogs);
  $('#exportLogs').addEventListener('click', exportLogs);
}

async function refreshLogs() {
  const params = new URLSearchParams();
  if ($('#logSession').value) params.set('session_id', $('#logSession').value);
  if ($('#logLevel').value) params.set('level', $('#logLevel').value);
  if ($('#logSource').value) params.set('source', $('#logSource').value);
  if ($('#logSearch').value) params.set('search', $('#logSearch').value);
  params.set('limit', '20000');
  try { state.logs = await api(`/api/logs?${params}`); renderLogs(); }
  catch (error) { toast(error.message, true); }
}

function renderLogs() {
  $('#logOutput').innerHTML = state.logs.map(log => `<div class="log-line ${escapeHtml(log.level)}"><span>${formatTime(log.timestamp)}</span><span>${escapeHtml(log.level)}</span><span>${escapeHtml(log.source)}</span><span>${escapeHtml(log.message)}</span></div>`).join('') || '<div class="empty-state">No matching log records.</div>';
}

function exportLogs() {
  const rows = [['timestamp','level','source','session_id','message'], ...state.logs.map(log => [log.timestamp, log.level, log.source, log.session_id || '', log.message])];
  const csv = rows.map(row => row.map(value => `"${String(value).replaceAll('"','""')}"`).join(',')).join('\n');
  const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([csv], {type:'text/csv'})); link.download = 'embeddyn-logs.csv'; link.click(); URL.revokeObjectURL(link.href);
}

async function downloadBundledAsset(name) {
  try {
    const response = await fetch(`/api/bundled-assets/${encodeURIComponent(name)}`);
    if (!response.ok) throw new Error(await response.text());
    const link = document.createElement('a');
    link.href = URL.createObjectURL(await response.blob());
    link.download = name;
    link.click();
    URL.revokeObjectURL(link.href);
  } catch (error) { toast(error.message, true); }
}

function installSettingsEvents() {
  $('#apiToken').value = state.token;
  $('#downloadComponentModels').addEventListener('click', () => downloadBundledAsset('renode-external-components-overlay.zip'));
  $('#saveToken').addEventListener('click', () => {
    state.token = $('#apiToken').value.trim();
    if (state.token) localStorage.setItem(TOKEN_KEY, state.token); else localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(LEGACY_TOKEN_KEY);
    toast('Browser token updated');
    refreshStudioData().catch(error => toast(`Authentication failed: ${error.message}`, true));
  });
}

bootstrap();
