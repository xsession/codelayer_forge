import { routeOrthogonal } from './router.js';
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const clone = (v) => structuredClone(v);

let seq = 0;
const id = (prefix) => `${prefix}-${Date.now().toString(36)}-${(++seq).toString(36)}`;

const port = (id, name, direction, kind, width = 1, required = false, protocol) => ({
  id, name, direction, required,
  cardinality: direction === 'output' && (kind === 'clock' || kind === 'reset') ? 'multiple' : 'single',
  dataType: { kind, width, protocol }
});

const definitions = [
  { id:'def.clock', type:'clock-source', namespace:'demo', name:'Clock Generator', version:'1.0', category:'Infrastructure', description:'Configurable system clock source.', ports:[port('clk_out','clk_out','output','clock',1,true)], parameters:[{id:'frequency',name:'Frequency',defaultValue:100,unit:'MHz'}] },
  { id:'def.reset', type:'reset-source', namespace:'demo', name:'Reset Controller', version:'1.0', category:'Infrastructure', description:'System reset distribution.', ports:[port('rst_out','reset_n','output','reset',1,true)] },
  { id:'def.cpu', type:'processor', namespace:'demo', name:'RV32 CPU', version:'1.2', category:'Processing', description:'Example 32-bit processor with a generic memory master.', ports:[port('clk','clk','input','clock',1,true),port('rst','reset_n','input','reset',1,true),port('mem','MEM_M','output','bus',32,true,'demo-mem'),port('irq','irq','input','signal')], parameters:[{id:'freq',name:'Clock frequency',defaultValue:100,unit:'MHz'},{id:'debug',name:'Debug enabled',defaultValue:true}] },
  { id:'def.bus', type:'interconnect', namespace:'demo', name:'Memory Interconnect', version:'1.0', category:'Interconnect', description:'One-master, multi-target address/data interconnect.', ports:[port('clk','clk','input','clock',1,true),port('rst','reset_n','input','reset',1,true),port('s0','S0','input','bus',32,true,'demo-mem'),port('m0','M0','output','bus',32,true,'demo-mem'),port('m1','M1','output','bus',32,false,'demo-mem'),port('m2','M2','output','bus',32,false,'demo-mem')] },
  { id:'def.ram', type:'memory', namespace:'demo', name:'On-Chip RAM', version:'1.0', category:'Memory', description:'Generic memory target.', ports:[port('clk','clk','input','clock',1,true),port('mem','MEM_S','input','bus',32,true,'demo-mem')], parameters:[{id:'size',name:'Size',defaultValue:128,unit:'KiB'}] },
  { id:'def.uart', type:'peripheral', namespace:'demo', name:'UART', version:'2.0', category:'Peripherals', description:'Memory-mapped UART peripheral.', ports:[port('clk','clk','input','clock',1,true),port('rst','reset_n','input','reset',1,true),port('bus','BUS_S','input','bus',32,true,'demo-mem'),port('tx','tx','output','signal'),port('rx','rx','input','signal'),port('irq','irq','output','signal')] },
  { id:'def.spi', type:'peripheral', namespace:'demo', name:'SPI Controller', version:'1.0', category:'Peripherals', description:'Memory-mapped SPI controller.', ports:[port('clk','clk','input','clock',1,true),port('rst','reset_n','input','reset',1,true),port('bus','BUS_S','input','bus',32,true,'demo-mem'),port('sck','sck','output','signal'),port('mosi','mosi','output','signal'),port('miso','miso','input','signal')] },
  { id:'def.gpio', type:'peripheral', namespace:'demo', name:'GPIO Bank', version:'1.0', category:'Peripherals', description:'Memory-mapped general purpose I/O.', ports:[port('clk','clk','input','clock',1,true),port('rst','reset_n','input','reset',1,true),port('bus','BUS_S','input','bus',32,true,'demo-mem'),port('gpio','gpio[15:0]','inout','signal',16)] }
];

const conn = (id, type, si, sp, ti, tp) => ({ id, type, source:{instanceId:si,portId:sp}, targets:[{instanceId:ti,portId:tp}], route:{mode:'automatic',router:'orthogonal',waypoints:[]} });

let project = {
  schemaVersion:1, id:'project-demo', name:'SoC Platform Demo', definitions,
  diagrams:[{ id:'diagram-top', name:'soc_top', instances:[
    {id:'clock0',definitionId:'def.clock',name:'sys_clk',position:{x:70,y:110},parameterValues:{frequency:100}},
    {id:'reset0',definitionId:'def.reset',name:'sys_reset',position:{x:70,y:300},parameterValues:{}},
    {id:'cpu0',definitionId:'def.cpu',name:'cpu0',position:{x:430,y:120},parameterValues:{freq:100,debug:true}},
    {id:'bus0',definitionId:'def.bus',name:'sys_bus',position:{x:810,y:250},parameterValues:{}},
    {id:'ram0',definitionId:'def.ram',name:'sram0',position:{x:1230,y:100},parameterValues:{size:128}},
    {id:'uart0',definitionId:'def.uart',name:'uart0',position:{x:1230,y:310},parameterValues:{}},
    {id:'spi0',definitionId:'def.spi',name:'spi0',position:{x:1230,y:545},parameterValues:{}},
    {id:'gpio0',definitionId:'def.gpio',name:'gpio0',position:{x:810,y:610},parameterValues:{}}
  ], connections:[
    conn('conn-clk-cpu','clock','clock0','clk_out','cpu0','clk'), conn('conn-clk-bus','clock','clock0','clk_out','bus0','clk'), conn('conn-clk-ram','clock','clock0','clk_out','ram0','clk'), conn('conn-clk-uart','clock','clock0','clk_out','uart0','clk'), conn('conn-clk-spi','clock','clock0','clk_out','spi0','clk'), conn('conn-clk-gpio','clock','clock0','clk_out','gpio0','clk'),
    conn('conn-reset-cpu','reset','reset0','rst_out','cpu0','rst'), conn('conn-reset-bus','reset','reset0','rst_out','bus0','rst'), conn('conn-reset-uart','reset','reset0','rst_out','uart0','rst'), conn('conn-reset-spi','reset','reset0','rst_out','spi0','rst'), conn('conn-reset-gpio','reset','reset0','rst_out','gpio0','rst'),
    conn('conn-cpu-bus','bus','cpu0','mem','bus0','s0'), conn('conn-bus-ram','bus','bus0','m0','ram0','mem'), conn('conn-bus-uart','bus','bus0','m1','uart0','bus'), conn('conn-bus-spi','bus','bus0','m2','spi0','bus')
  ]}]
};

const diagramId = 'diagram-top';
const diagram = () => project.diagrams.find(d => d.id === diagramId);
const def = (id) => project.definitions.find(d => d.id === id);
const inst = (iid) => diagram().instances.find(i => i.id === iid);
const endpointPort = (e) => { const i=inst(e.instanceId); return i ? def(i.definitionId)?.ports.find(p=>p.id===e.portId) : undefined; };
const endpointName = (e) => { const i=inst(e.instanceId); const p=endpointPort(e); return `${i?.name ?? '?'} . ${p?.name ?? '?'}`; };
const sameEndpoint = (a,b) => a.instanceId===b.instanceId && a.portId===b.portId;

const history = { undo:[], redo:[] };
function execute(label, mutator){ const before=clone(project); mutator(project); const after=clone(project); history.undo.push({label,before,after}); history.redo=[]; render(); }
function undo(){ const e=history.undo.pop(); if(!e)return; history.redo.push(e); project=clone(e.before); selection=undefined; render(); }
function redo(){ const e=history.redo.pop(); if(!e)return; history.undo.push(e); project=clone(e.after); selection=undefined; render(); }

function connectionExists(a,b){ return diagram().connections.find(c => (sameEndpoint(c.source,a)&&c.targets.some(t=>sameEndpoint(t,b))) || (sameEndpoint(c.source,b)&&c.targets.some(t=>sameEndpoint(t,a)))); }
function connectionsFor(e){ return diagram().connections.filter(c=>sameEndpoint(c.source,e)||c.targets.some(t=>sameEndpoint(t,e))); }
function normalizeEndpoints(a,b){
  const ap=endpointPort(a), bp=endpointPort(b); if(!ap||!bp) return {source:a,target:b};
  const aOut=ap.direction==='output', bOut=bp.direction==='output';
  const aIn=ap.direction==='input', bIn=bp.direction==='input';
  if(aIn&&bOut) return {source:b,target:a};
  return {source:a,target:b};
}
function compatibility(a,b,{ignoreDuplicate=false}={}){
  if(sameEndpoint(a,b)) return {status:'incompatible',message:'A port cannot connect to itself.'};
  if(a.instanceId===b.instanceId) return {status:'incompatible',message:'Loopback requires an explicit domain rule.'};
  if(!ignoreDuplicate && connectionExists(a,b)) return {status:'incompatible',message:'An equivalent connection already exists.'};
  const {source,target}=normalizeEndpoints(a,b); const s=endpointPort(source), t=endpointPort(target);
  if(!s||!t) return {status:'incompatible',message:'One or both endpoints are unresolved.'};
  const sourceLike=s.direction==='output'||s.direction==='inout'; const targetLike=t.direction==='input'||t.direction==='inout';
  if(!sourceLike||!targetLike) return {status:'incompatible',message:`${s.direction} cannot drive ${t.direction}.`};
  if(s.dataType?.kind!==t.dataType?.kind) return {status:'incompatible',message:`${s.dataType?.kind??'unknown'} cannot connect to ${t.dataType?.kind??'unknown'}.`};
  if(s.dataType?.protocol&&t.dataType?.protocol&&s.dataType.protocol!==t.dataType.protocol) return {status:'incompatible',message:`Protocol mismatch: ${s.dataType.protocol} vs ${t.dataType.protocol}.`};
  const sourceUsed=connectionsFor(source).filter(c=>sameEndpoint(c.source,source)).length;
  const targetUsed=connectionsFor(target).length;
  if(s.cardinality==='single'&&sourceUsed>0&&!ignoreDuplicate) return {status:'incompatible',message:`${s.name} only permits one outgoing connection.`};
  if(t.cardinality==='single'&&targetUsed>0&&!ignoreDuplicate) return {status:'incompatible',message:`${t.name} already has a driver.`};
  if(s.dataType?.width!==t.dataType?.width) return {status:'warning',message:`Width mismatch ${s.dataType?.width??'?'} -> ${t.dataType?.width??'?'}.`,type:s.dataType?.kind??'signal',source,target};
  return {status:'compatible',type:s.dataType?.kind==='bus'?'bus':s.dataType?.kind??'signal',source,target};
}

function validate(){
  const issues=[];
  for(const c of diagram().connections){ for(const t of c.targets){ const r=compatibility(c.source,t,{ignoreDuplicate:true}); if(!endpointPort(c.source)||!endpointPort(t)) issues.push({id:`u:${c.id}`,severity:'error',code:'E001',message:'Connection has an unresolved endpoint.',kind:'connection',objectId:c.id}); else if(r.status==='incompatible') issues.push({id:`i:${c.id}`,severity:'error',code:'E120',message:r.message,kind:'connection',objectId:c.id}); else if(r.status==='warning') issues.push({id:`w:${c.id}`,severity:'warning',code:'W080',message:r.message,kind:'connection',objectId:c.id}); } }
  for(const i of diagram().instances){ const d=def(i.definitionId); if(!d){issues.push({id:`d:${i.id}`,severity:'error',code:'E010',message:`Missing component definition for ${i.name}.`,kind:'instance',objectId:i.id});continue;} for(const p of d.ports.filter(p=>p.required)){ if(connectionsFor({instanceId:i.id,portId:p.id}).length===0) issues.push({id:`r:${i.id}:${p.id}`,severity:'warning',code:'W044',message:`${i.name}.${p.name} is required but unconnected.`,kind:'port',objectId:i.id,portId:p.id}); } }
  const seen=new Map(); for(const i of diagram().instances){if(seen.has(i.name)) issues.push({id:`n:${i.id}`,severity:'error',code:'E200',message:`Duplicate instance name: ${i.name}.`,kind:'instance',objectId:i.id}); else seen.set(i.name,i.id);}
  return issues;
}

const NODE_W=244, HEAD=38, ROW=24, BOTTOM=10;
function sideOf(p){ return p.side ?? (p.direction==='input'?'left':'right'); }
function rectOf(i, override){ const d=def(i.definitionId); const left=d?.ports.filter(p=>sideOf(p)==='left').length??0, right=d?.ports.filter(p=>sideOf(p)==='right').length??0; return {x:override?.x??i.position.x,y:override?.y??i.position.y,width:i.size?.width??NODE_W,height:i.size?.height??HEAD+Math.max(left,right,1)*ROW+BOTTOM}; }
function portLayout(i,override){ const d=def(i.definitionId); if(!d)return[]; const r=rectOf(i,override); const left=d.ports.filter(p=>sideOf(p)==='left'), right=d.ports.filter(p=>sideOf(p)==='right'); return [...left.map((p,n)=>({port:p,side:'left',point:{x:r.x,y:r.y+HEAD+ROW*(n+.5)}})),...right.map((p,n)=>({port:p,side:'right',point:{x:r.x+r.width,y:r.y+HEAD+ROW*(n+.5)}}))]; }
function anchor(e){ const i=inst(e.instanceId); if(!i)return; return portLayout(i).find(x=>x.port.id===e.portId)?.point; }

function path(points){return points.length?`M ${points.map(p=>`${p.x} ${p.y}`).join(' L ')}`:''}

let selection;
let viewport={x:22,y:18,zoom:.76};
let draft;
let dragging;
let panning;
let statusMessage='Ready';
let leftTab='library', bottomTab='problems';

function iconText(type){return ({'clock-source':'CLK','reset-source':'RST',processor:'CPU',interconnect:'BUS',memory:'MEM',peripheral:'IO'})[type]??'IP';}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

function shellHtml(){
  const issues=validate();
  return `<div class="shell">
    <header class="menu"><div class="brand"><span class="logo">EW</span> Engineering Workbench <span class="badge">CLEAN ROOM</span></div><nav>${['File','Edit','View','Diagram','Component','Connection','Tools','Generate','Debug','Help'].map(x=>`<button>${x}</button>`).join('')}</nav></header>
    <div class="toolbar">
      <button class="tool">＋ <span>New</span></button><button class="tool">▣ <span>Open</span></button><button class="tool">▤ <span>Save</span></button><i class="sep"></i>
      <button id="undo" class="tool" ${history.undo.length?'':'disabled'}>↶ <span>Undo</span></button><button id="redo" class="tool" ${history.redo.length?'':'disabled'}>↷ <span>Redo</span></button><i class="sep"></i>
      <button class="tool active">⌁ <span>Connect</span></button><button class="tool active"># <span>Grid</span></button><i class="sep"></i><button class="tool">＋ <span>Zoom +</span></button><button class="tool">− <span>Zoom −</span></button><div class="spacer"></div><button class="tool">⌘ <span>Commands</span></button><button class="tool">⚠ <span>Issues ${issues.length}</span></button>
    </div>
    <div class="main">
      <aside class="left"><div class="tabs"><button data-left="library" class="${leftTab==='library'?'on':''}">Library</button><button data-left="project" class="${leftTab==='project'?'on':''}">Project</button><button data-left="hierarchy" class="${leftTab==='hierarchy'?'on':''}">Hierarchy</button></div><div id="leftContent"></div></aside>
      <main class="doc"><div class="doctabs"><button class="on">▦ ${diagram().name}<span class="dirty">●</span></button><button>▤ memory_map</button><button>＋</button></div><div id="canvas" class="canvas"><div id="world" class="world"><svg id="edges" class="connections" width="4000" height="2600" viewBox="0 0 4000 2600"></svg><div id="nodes"></div></div><div class="hud"><span id="zoomLabel">${Math.round(viewport.zoom*100)}%</span><span>Shift+drag / middle-drag to pan</span><span id="canvasMsg">${esc(statusMessage)}</span></div></div></main>
      <aside class="right"><div class="docktitle">⚙ Inspector</div><div id="inspector" class="inspector"></div></aside>
      <section class="bottom"><div class="bottomtabs"><button data-bottom="problems" class="${bottomTab==='problems'?'on':''}">⚠ Problems <span>${issues.length}</span></button><button data-bottom="connections" class="${bottomTab==='connections'?'on':''}">⌁ Connections <span>${diagram().connections.length}</span></button><button data-bottom="console" class="${bottomTab==='console'?'on':''}">▤ Console</button></div><div id="bottomContent" class="bottomcontent"></div></section>
    </div>
    <footer class="status"><span>✓ Model ready</span><span>${diagram().instances.length} components</span><span>${diagram().connections.length} connections</span><span class="${issues.some(i=>i.severity==='error')?'err':''}">${issues.filter(i=>i.severity==='error').length} errors</span><span>${issues.filter(i=>i.severity==='warning').length} warnings</span><span class="grow"></span><span>Example Electronics 0.1.0</span></footer>
  </div>`;
}

function render(){
  $('#app').innerHTML=shellHtml(); bindShell(); renderLeft(); renderCanvas(); renderInspector(); renderBottom();
}

function bindShell(){
  $('#undo').onclick=undo; $('#redo').onclick=redo;
  $$('[data-left]').forEach(b=>b.onclick=()=>{leftTab=b.dataset.left;render();});
  $$('[data-bottom]').forEach(b=>b.onclick=()=>{bottomTab=b.dataset.bottom;render();});
  const c=$('#canvas'); c.addEventListener('wheel',onWheel,{passive:false}); c.addEventListener('pointerdown',onCanvasDown); c.addEventListener('pointermove',onCanvasMove); c.addEventListener('pointerup',onCanvasUp); c.addEventListener('pointercancel',onCanvasUp); c.addEventListener('dragover',e=>e.preventDefault()); c.addEventListener('drop',onDrop);
}

function renderLeft(){
  const host=$('#leftContent');
  if(leftTab==='library'){
    host.innerHTML=`<div class="search">⌕ <input id="filter" placeholder="Filter components..."></div><div id="library" class="library"></div>`; renderLibrary(''); $('#filter').oninput=e=>renderLibrary(e.target.value);
  } else if(leftTab==='project'){
    host.innerHTML=`<div class="heading">⌄ ${esc(project.name)}</div><div style="padding:8px 12px;color:var(--muted);line-height:25px">Definitions <span style="float:right;color:var(--dim)">${project.definitions.length}</span><br>${project.diagrams.map(d=>`Diagram: ${esc(d.name)}`).join('<br>')}</div>`;
  } else {
    host.innerHTML=`<div class="heading">⌄ ${esc(diagram().name)}</div>${diagram().instances.map(i=>`<div style="height:25px;padding:5px 10px 5px 23px;border-bottom:1px solid #1d2530;color:var(--muted)">${esc(i.name)}</div>`).join('')}`;
  }
}
function renderLibrary(filter){
  const text=filter.toLowerCase(); const grouped={}; for(const d of project.definitions.filter(d=>`${d.name} ${d.type} ${d.category}`.toLowerCase().includes(text))){(grouped[d.category??'Other']??=[]).push(d)}
  $('#library').innerHTML=Object.entries(grouped).map(([g,items])=>`<div class="group"><div class="heading">⌄ ${esc(g)}<span class="count">${items.length}</span></div>${items.map(d=>`<div class="item" draggable="true" data-def="${d.id}" title="${esc(d.description)}"><span class="itemIcon">${iconText(d.type)}</span><span><strong>${esc(d.name)}</strong><small>${esc(d.namespace)}:${esc(d.type)} · v${esc(d.version)}</small></span></div>`).join('')}</div>`).join('');
  $$('.item',$('#library')).forEach(el=>el.addEventListener('dragstart',e=>e.dataTransfer.setData('application/x-ew-definition',el.dataset.def)));
}

function renderCanvas(){
  $('#world').style.transform=`translate(${viewport.x}px,${viewport.y}px) scale(${viewport.zoom})`;
  renderEdges();
  $('#nodes').innerHTML=diagram().instances.map(nodeHtml).join('');
  $$('.node').forEach(node=>{
    node.addEventListener('pointerdown',e=>{ if(e.target.closest('.pmark'))return; selection={kind:'instance',id:node.dataset.instance}; renderInspector(); renderNodesSelection(); });
    $('.nodehead',node).addEventListener('pointerdown',e=>startNodeDrag(e,node.dataset.instance));
  });
  $$('.pmark').forEach(mark=>{ mark.addEventListener('pointerdown',e=>startConnection(e,{instanceId:mark.dataset.instance,portId:mark.dataset.port})); mark.addEventListener('pointerup',e=>finishConnection(e,{instanceId:mark.dataset.instance,portId:mark.dataset.port})); });
}
function nodeHtml(i){
  const d=def(i.definitionId), r=rectOf(i), left=portLayout(i).filter(x=>x.side==='left'), right=portLayout(i).filter(x=>x.side==='right'), map=new Map(d.ports.map(p=>[p.id,p]));
  const rows=(items,side)=>items.map(x=>{const p=map.get(x.port.id);return `<div class="portrow ${side}" data-endpoint="${i.id}:${p.id}">${side==='left'?`<button class="pmark" data-instance="${i.id}" data-port="${p.id}" title="${esc(p.name)} · ${p.direction} · ${p.dataType.kind}"></button>`:''}<span class="pname">${esc(p.name)}</span><span class="pkind">${esc(p.dataType.kind)}${p.dataType.width>1?`:${p.dataType.width}`:''}</span>${side==='right'?`<button class="pmark" data-instance="${i.id}" data-port="${p.id}" title="${esc(p.name)} · ${p.direction} · ${p.dataType.kind}"></button>`:''}</div>`}).join('');
  return `<div class="node ${selection?.kind==='instance'&&selection.id===i.id?'selected':''}" data-instance="${i.id}" style="left:${r.x}px;top:${r.y}px;width:${r.width}px;height:${r.height}px"><div class="nodehead"><span class="nodetype">${esc(d.type)}</span><strong>${esc(i.name)}</strong><span class="version">v${esc(d.version)}</span></div><div class="nodebody"><div class="portcol">${rows(left,'left')}</div><div class="portcol">${rows(right,'right')}</div></div></div>`;
}
function renderNodesSelection(){ $$('.node').forEach(n=>n.classList.toggle('selected',selection?.kind==='instance'&&selection.id===n.dataset.instance)); }

function renderEdges(){
  const svg=$('#edges'); if(!svg)return; let html='';
  for(const c of diagram().connections){ for(const t of c.targets){ const s=anchor(c.source),d=anchor(t); if(!s||!d)continue; const obstacles=diagram().instances.filter(i=>i.id!==c.source.instanceId&&i.id!==t.instanceId).map(i=>rectOf(i)); const pts=routeOrthogonal(s,d,obstacles,{clearance:10,margin:220}); const mid=pts[Math.floor(pts.length/2)]; const selected=selection?.kind==='connection'&&selection.id===c.id; html+=`<g data-conn-group="${c.id}"><path class="edgehit" data-conn="${c.id}" d="${path(pts)}"></path><path class="edge ${c.type} ${selected?'selected':''}" d="${path(pts)}"></path><circle class="dirDot" cx="${mid.x}" cy="${mid.y}" r="3"></circle></g>`; } }
  if(draft){ const s=anchor(draft.source); if(s)html+=`<path id="draftPath" class="edge draft" d="${path(routeOrthogonal(s,draft.pointer,[],{clearance:0,margin:80}))}"></path>`; }
  svg.innerHTML=html;
  $$('.edgehit',svg).forEach(p=>{p.addEventListener('pointerdown',e=>{e.stopPropagation();selection={kind:'connection',id:p.dataset.conn};renderEdges();renderInspector();});p.addEventListener('mouseenter',()=>{const vis=p.nextElementSibling;vis?.classList.add('selected')});p.addEventListener('mouseleave',()=>{if(!(selection?.kind==='connection'&&selection.id===p.dataset.conn))p.nextElementSibling?.classList.remove('selected')});});
}

function renderInspector(){
  const host=$('#inspector'); if(!host)return;
  if(selection?.kind==='instance'){
    const i=inst(selection.id), d=i&&def(i.definitionId); if(!i||!d){host.innerHTML='<div class="empty">Selection unresolved</div>';return;}
    host.innerHTML=`<section class="section"><h3>⌄ Identity</h3><div class="prop"><label>Name</label><div><input id="iname" value="${esc(i.name)}"></div></div><div class="prop"><label>Definition</label><div><span class="readonly">${esc(d.name)}</span></div></div><div class="prop"><label>Type</label><div><span class="readonly">${esc(d.type)}</span></div></div><div class="prop"><label>Version</label><div><span class="readonly">${esc(d.version)}</span></div></div></section><section class="section"><h3>⌄ Placement</h3><div class="prop"><label>X</label><div><span class="readonly">${i.position.x}</span></div></div><div class="prop"><label>Y</label><div><span class="readonly">${i.position.y}</span></div></div></section>${d.parameters?.length?`<section class="section"><h3>⌄ Configuration</h3>${d.parameters.map(p=>`<div class="prop"><label>${esc(p.name)}</label><div><span class="readonly">${esc(i.parameterValues[p.id]??p.defaultValue)} ${esc(p.unit??'')}</span></div></div>`).join('')}</section>`:''}<section class="section"><h3>⌄ Ports (${d.ports.length})</h3><div class="mini">${d.ports.map(p=>`<div><span>${esc(p.name)}</span><span>${esc(p.direction)}</span><span>${esc(p.dataType.kind)}${p.dataType.width>1?`[${p.dataType.width}]`:''}</span></div>`).join('')}</div></section>`;
    $('#iname').addEventListener('keydown',e=>{if(e.key==='Enter')e.currentTarget.blur()}); $('#iname').addEventListener('blur',e=>{const name=e.target.value.trim();if(name&&name!==i.name)execute('Rename component',p=>{p.diagrams[0].instances.find(x=>x.id===i.id).name=name})});
  } else if(selection?.kind==='connection'){
    const c=diagram().connections.find(c=>c.id===selection.id); if(!c){host.innerHTML='<div class="empty">Connection not found</div>';return;}
    host.innerHTML=`<section class="section"><h3>⌄ Connection</h3><div class="prop"><label>ID</label><div><span class="readonly">${esc(c.id)}</span></div></div><div class="prop"><label>Type</label><div><span class="readonly">${esc(c.type)}</span></div></div><div class="prop"><label>Routing</label><div><span class="readonly">${esc(c.route.mode)} / ${esc(c.route.router)}</span></div></div></section><section class="section"><h3>⌄ Endpoints</h3><div class="prop"><label>Source</label><div><span class="readonly">${esc(endpointName(c.source))}</span></div></div>${c.targets.map((t,n)=>`<div class="prop"><label>Target ${n+1}</label><div><span class="readonly">${esc(endpointName(t))}</span></div></div>`).join('')}</section><div class="actions"><button id="deleteConn">Delete connection</button></div>`;
    $('#deleteConn').onclick=()=>execute('Delete connection',p=>{p.diagrams[0].connections=p.diagrams[0].connections.filter(x=>x.id!==c.id);selection=undefined});
  } else if(selection?.kind==='port'){
    const i=inst(selection.instanceId), p=endpointPort({instanceId:selection.instanceId,portId:selection.portId}); host.innerHTML=i&&p?`<section class="section"><h3>⌄ Port</h3><div class="prop"><label>Component</label><div><span class="readonly">${esc(i.name)}</span></div></div><div class="prop"><label>Name</label><div><span class="readonly">${esc(p.name)}</span></div></div><div class="prop"><label>Direction</label><div><span class="readonly">${esc(p.direction)}</span></div></div><div class="prop"><label>Type</label><div><span class="readonly">${esc(p.dataType.kind)} / ${p.dataType.width} bit</span></div></div><div class="prop"><label>Connections</label><div><span class="readonly">${connectionsFor({instanceId:i.id,portId:p.id}).length}</span></div></div></section>`:'<div class="empty">Port unresolved</div>';
  } else host.innerHTML='<div class="empty"><b style="font-size:28px">▦</b><strong>No object selected</strong><span>Select a component, port, or connection on the diagram.</span></div>';
}

function renderBottom(){
  const host=$('#bottomContent'); if(!host)return;
  if(bottomTab==='problems'){
    const issues=validate(); host.innerHTML=`<table class="table"><thead><tr><th style="width:95px">Severity</th><th style="width:70px">Code</th><th>Description</th><th style="width:110px">Object</th></tr></thead><tbody>${issues.length?issues.map(i=>`<tr data-issue="${i.id}"><td class="sev ${i.severity}">${i.severity==='error'?'✕':'⚠'} ${i.severity}</td><td>${i.code}</td><td>${esc(i.message)}</td><td>${i.kind}</td></tr>`).join(''):'<tr><td colspan="4">No problems.</td></tr>'}</tbody></table>`; $$('#bottomContent tr[data-issue]').forEach(r=>r.onclick=()=>{const x=issues.find(i=>i.id===r.dataset.issue);selection=x.kind==='connection'?{kind:'connection',id:x.objectId}:x.kind==='port'?{kind:'port',instanceId:x.objectId,portId:x.portId}:{kind:'instance',id:x.objectId};renderCanvas();renderInspector();});
  } else if(bottomTab==='connections'){
    host.innerHTML=`<table class="table"><thead><tr><th style="width:85px">Type</th><th>Source</th><th>Target</th><th style="width:100px">Routing</th><th style="width:160px">ID</th></tr></thead><tbody>${diagram().connections.flatMap(c=>c.targets.map(t=>`<tr data-connrow="${c.id}"><td>${esc(c.type)}</td><td>${esc(endpointName(c.source))}</td><td>${esc(endpointName(t))}</td><td>${esc(c.route.mode)}</td><td>${esc(c.id)}</td></tr>`)).join('')}</tbody></table>`; $$('[data-connrow]',host).forEach(r=>r.onclick=()=>{selection={kind:'connection',id:r.dataset.connrow};renderEdges();renderInspector();});
  } else host.innerHTML=`<div class="console"><b>workbench:</b> model loaded; 1 plugin active; ${diagram().instances.length} instances; ${diagram().connections.length} connections.<br><b>router:</b> orthogonal A* obstacle avoidance enabled.<br><b>clean-room:</b> no Kactus2 source or assets included.</div>`;
}

function worldPoint(e){const r=$('#canvas').getBoundingClientRect();return{x:(e.clientX-r.left-viewport.x)/viewport.zoom,y:(e.clientY-r.top-viewport.y)/viewport.zoom};}
function applyViewport(){const w=$('#world');if(w)w.style.transform=`translate(${viewport.x}px,${viewport.y}px) scale(${viewport.zoom})`;const z=$('#zoomLabel');if(z)z.textContent=`${Math.round(viewport.zoom*100)}%`;}
function onWheel(e){e.preventDefault();const r=$('#canvas').getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top,oz=viewport.zoom,nz=Math.min(2.5,Math.max(.25,oz*(e.deltaY<0?1.1:.9))),wx=(mx-viewport.x)/oz,wy=(my-viewport.y)/oz;viewport={x:mx-wx*nz,y:my-wy*nz,zoom:nz};applyViewport();}
function onCanvasDown(e){
  if(e.button===1||(e.button===0&&e.shiftKey)){e.currentTarget.setPointerCapture(e.pointerId);panning={px:e.clientX,py:e.clientY,ox:viewport.x,oy:viewport.y};return;}
  if(e.button===0&&!e.target.closest('.node')&&!e.target.closest('.edgehit')){selection=undefined;renderNodesSelection();renderEdges();renderInspector();}
}
function onCanvasMove(e){
  if(panning){viewport.x=panning.ox+e.clientX-panning.px;viewport.y=panning.oy+e.clientY-panning.py;applyViewport();return;}
  if(dragging){const p=worldPoint(e),dx=p.x-dragging.start.x,dy=p.y-dragging.start.y;dragging.preview={x:Math.round((dragging.origin.x+dx)/10)*10,y:Math.round((dragging.origin.y+dy)/10)*10};const n=$(`.node[data-instance="${dragging.id}"]`);if(n){n.style.left=`${dragging.preview.x}px`;n.style.top=`${dragging.preview.y}px`;}return;}
  if(draft){draft.pointer=worldPoint(e);const s=anchor(draft.source),dp=$('#draftPath');if(s&&dp)dp.setAttribute('d',path(routeOrthogonal(s,draft.pointer,[],{clearance:0,margin:80})));}
}
function onCanvasUp(){
  if(panning){panning=undefined;return;}
  if(dragging){const d=dragging;dragging=undefined;if(d.origin.x!==d.preview.x||d.origin.y!==d.preview.y)execute('Move component',p=>{p.diagrams[0].instances.find(i=>i.id===d.id).position=d.preview});else renderCanvas();return;}
  if(draft){draft=undefined;clearCompatibility();statusMessage='Connection cancelled';renderEdges();const m=$('#canvasMsg');if(m)m.textContent=statusMessage;}
}
function startNodeDrag(e,instanceId){if(e.button!==0)return;e.stopPropagation();const i=inst(instanceId);if(!i)return;e.currentTarget.setPointerCapture(e.pointerId);selection={kind:'instance',id:instanceId};renderNodesSelection();renderInspector();dragging={id:instanceId,start:worldPoint(e),origin:{...i.position},preview:{...i.position}};}
function startConnection(e,source){e.preventDefault();e.stopPropagation();draft={source,pointer:worldPoint(e)};selection={kind:'port',instanceId:source.instanceId,portId:source.portId};statusMessage='Choose a compatible target';renderEdges();renderInspector();markCompatibility();const m=$('#canvasMsg');if(m)m.textContent=statusMessage;}
function finishConnection(e,target){if(!draft)return;e.preventDefault();e.stopPropagation();const result=compatibility(draft.source,target);const old=draft;draft=undefined;clearCompatibility();if(result.status==='incompatible'){statusMessage=result.message;renderEdges();$('#canvasMsg').textContent=statusMessage;return;}const source=result.source??normalizeEndpoints(old.source,target).source, normalizedTarget=result.target??normalizeEndpoints(old.source,target).target;execute('Create connection',p=>{p.diagrams[0].connections.push({id:id('conn'),type:result.type??'signal',source,targets:[normalizedTarget],route:{mode:'automatic',router:'orthogonal',waypoints:[]}})});statusMessage=result.status==='warning'?`Connected with warning: ${result.message}`:'Connection created';}
function markCompatibility(){ $$('.portrow').forEach(row=>{const [iid,pid]=row.dataset.endpoint.split(':'),r=compatibility(draft.source,{instanceId:iid,portId:pid});row.classList.remove('compatible','warning','incompatible');row.classList.add(r.status==='compatible'?'compatible':r.status==='warning'?'warning':'incompatible');}); }
function clearCompatibility(){ $$('.portrow').forEach(row=>row.classList.remove('compatible','warning','incompatible')); }
function onDrop(e){e.preventDefault();const did=e.dataTransfer.getData('application/x-ew-definition'),d=def(did);if(!d)return;const r=$('#canvas').getBoundingClientRect(),pos={x:Math.round(((e.clientX-r.left-viewport.x)/viewport.zoom)/10)*10,y:Math.round(((e.clientY-r.top-viewport.y)/viewport.zoom)/10)*10},n=diagram().instances.filter(i=>i.definitionId===d.id).length,base=d.name.replace(/[^A-Za-z0-9]+/g,'_').toLowerCase();const newId=id('inst');execute('Add component',p=>{p.diagrams[0].instances.push({id:newId,definitionId:d.id,name:`${base}${n}`,position:pos,parameterValues:Object.fromEntries((d.parameters??[]).map(x=>[x.id,x.defaultValue]))})});selection={kind:'instance',id:newId};statusMessage=`${d.name} added`;render();}

document.addEventListener('keydown',e=>{
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();e.shiftKey?redo():undo();}
  else if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='y'){e.preventDefault();redo();}
  else if(e.key==='Escape'&&draft){draft=undefined;clearCompatibility();statusMessage='Connection cancelled';renderEdges();$('#canvasMsg').textContent=statusMessage;}
  else if(e.key==='Delete'&&selection?.kind==='connection'){const cid=selection.id;execute('Delete connection',p=>{p.diagrams[0].connections=p.diagrams[0].connections.filter(c=>c.id!==cid)});selection=undefined;}
});

render();
