import { useMemo, useState } from 'react';
import {
  getDefinition,
  getDiagram,
  getInstance,
  type ComponentDefinition,
  type Project,
  type ValidationIssue
} from '@ew/core';
import { createPluginRegistry, type EngineeringPlugin } from '@ew/plugin-api';
import { validateDiagram } from '@ew/validation';
import { EngineeringCanvas } from './EngineeringCanvas';
import { useWorkbenchModel } from './model';
import {
  Box, ChevronDown, CircuitBoard, Command, FilePlus2, FolderOpen, Grid3X3,
  Redo2, Save, Search, Undo2, ZoomIn, ZoomOut, AlertTriangle, CircleX,
  CircleCheck, Cable, Layers3, Settings2, PanelBottom
} from 'lucide-react';

interface WorkbenchProps {
  initialProject: Project;
  plugins: EngineeringPlugin[];
  initialDiagramId: string;
}

export function Workbench({ initialProject, plugins, initialDiagramId }: WorkbenchProps) {
  const registry = useMemo(() => createPluginRegistry(plugins), [plugins]);
  const model = useWorkbenchModel(initialProject, initialDiagramId, registry);
  const [leftTab, setLeftTab] = useState<'library' | 'project' | 'hierarchy'>('library');
  const [bottomTab, setBottomTab] = useState<'problems' | 'connections' | 'console'>('problems');
  const [filter, setFilter] = useState('');
  const issues = useMemo(() => validateDiagram(model.project, model.diagramId, registry), [model.project, model.diagramId, registry]);
  const diagram = getDiagram(model.project, model.diagramId);

  const selectedInstance = model.selection?.kind === 'instance' ? getInstance(model.project, model.diagramId, model.selection.id) : undefined;
  const selectedDefinition = selectedInstance ? getDefinition(model.project, selectedInstance.definitionId) : undefined;
  const selectedConnectionId = model.selection?.kind === 'connection' ? model.selection.id : undefined;
  const selectedConnection = selectedConnectionId ? diagram.connections.find((item) => item.id === selectedConnectionId) : undefined;

  return (
    <div className="ew-app-shell">
      <header className="ew-menu-bar">
        <div className="ew-brand"><CircuitBoard size={16} /> Engineering Workbench <span className="ew-badge">CLEAN ROOM</span></div>
        <nav>{['File', 'Edit', 'View', 'Diagram', 'Component', 'Connection', 'Tools', 'Generate', 'Debug', 'Help'].map((item) => <button key={item}>{item}</button>)}</nav>
      </header>
      <div className="ew-toolbar">
        <ToolbarButton icon={<FilePlus2 size={15}/>} label="New" />
        <ToolbarButton icon={<FolderOpen size={15}/>} label="Open" />
        <ToolbarButton icon={<Save size={15}/>} label="Save" />
        <span className="ew-separator" />
        <ToolbarButton icon={<Undo2 size={15}/>} label="Undo" disabled={!model.canUndo} onClick={model.undo} />
        <ToolbarButton icon={<Redo2 size={15}/>} label="Redo" disabled={!model.canRedo} onClick={model.redo} />
        <span className="ew-separator" />
        <ToolbarButton icon={<Cable size={15}/>} label="Connect" active />
        <ToolbarButton icon={<Grid3X3 size={15}/>} label="Grid" active />
        <span className="ew-separator" />
        <ToolbarButton icon={<ZoomIn size={15}/>} label="Zoom +" />
        <ToolbarButton icon={<ZoomOut size={15}/>} label="Zoom −" />
        <div className="ew-toolbar-spacer" />
        <ToolbarButton icon={<Command size={15}/>} label="Commands" />
        <ToolbarButton icon={<AlertTriangle size={15}/>} label={`Issues ${issues.length}`} />
      </div>

      <div className="ew-main-grid">
        <aside className="ew-left-dock">
          <DockTabs
            tabs={[['library', 'Library'], ['project', 'Project'], ['hierarchy', 'Hierarchy']]}
            active={leftTab}
            onChange={(tab) => setLeftTab(tab as typeof leftTab)}
          />
          {leftTab === 'library' && <LibraryPanel definitions={model.project.definitions} filter={filter} setFilter={setFilter} />}
          {leftTab === 'project' && <ProjectPanel project={model.project} />}
          {leftTab === 'hierarchy' && <HierarchyPanel project={model.project} diagramId={model.diagramId} />}
        </aside>

        <main className="ew-document-area">
          <div className="ew-document-tabs">
            <button className="is-active"><Box size={13} /> {diagram.name}<span className="ew-dirty">●</span></button>
            <button><Layers3 size={13} /> memory_map</button>
            <button className="ew-tab-plus">+</button>
          </div>
          <EngineeringCanvas model={model} />
        </main>

        <aside className="ew-right-dock">
          <div className="ew-dock-title"><Settings2 size={14}/> Inspector</div>
          {selectedInstance && selectedDefinition ? (
            <InstanceInspector instance={selectedInstance} definition={selectedDefinition} onRename={(name) => model.renameInstance(selectedInstance.id, selectedInstance.name, name)} />
          ) : selectedConnection ? (
            <ConnectionInspector connection={selectedConnection} project={model.project} diagramId={model.diagramId} onDelete={() => model.deleteConnection(selectedConnection)} />
          ) : (
            <EmptyInspector />
          )}
        </aside>

        <section className="ew-bottom-dock">
          <div className="ew-bottom-tabs">
            <button className={bottomTab === 'problems' ? 'is-active' : ''} onClick={() => setBottomTab('problems')}><AlertTriangle size={13}/> Problems <span>{issues.length}</span></button>
            <button className={bottomTab === 'connections' ? 'is-active' : ''} onClick={() => setBottomTab('connections')}><Cable size={13}/> Connections <span>{diagram.connections.length}</span></button>
            <button className={bottomTab === 'console' ? 'is-active' : ''} onClick={() => setBottomTab('console')}><PanelBottom size={13}/> Console</button>
          </div>
          <div className="ew-bottom-content">
            {bottomTab === 'problems' && <ProblemsTable issues={issues} onSelect={(issue) => {
              if (issue.objectRef?.kind === 'instance') model.setSelection({ kind: 'instance', id: issue.objectRef.id });
              if (issue.objectRef?.kind === 'connection') model.setSelection({ kind: 'connection', id: issue.objectRef.id });
              if (issue.objectRef?.kind === 'port' && issue.objectRef.parentId) model.setSelection({ kind: 'port', instanceId: issue.objectRef.parentId, portId: issue.objectRef.id });
            }} />}
            {bottomTab === 'connections' && <ConnectionsTable project={model.project} diagramId={model.diagramId} onSelect={(id) => model.setSelection({ kind: 'connection', id })} />}
            {bottomTab === 'console' && <div className="ew-console"><span>workbench:</span> model loaded; {registry.plugins.length} plugin(s) active; {diagram.instances.length} instances; {diagram.connections.length} connections.</div>}
          </div>
        </section>
      </div>
      <footer className="ew-statusbar">
        <span><CircleCheck size={12}/> Model ready</span>
        <span>{diagram.instances.length} components</span>
        <span>{diagram.connections.length} connections</span>
        <span className={issues.some((issue) => issue.severity === 'error') ? 'has-error' : ''}>{issues.filter((issue) => issue.severity === 'error').length} errors</span>
        <span>{issues.filter((issue) => issue.severity === 'warning').length} warnings</span>
        <span className="ew-status-spacer" />
        <span>Example Electronics 0.1.0</span>
      </footer>
    </div>
  );
}

function ToolbarButton({ icon, label, onClick, disabled, active }: { icon: React.ReactNode; label: string; onClick?: () => void; disabled?: boolean; active?: boolean }) {
  return <button className={`ew-tool ${active ? 'is-active' : ''}`} title={label} onClick={onClick} disabled={disabled}>{icon}<span>{label}</span></button>;
}

function DockTabs({ tabs, active, onChange }: { tabs: Array<[string,string]>; active: string; onChange(id: string): void }) {
  return <div className="ew-dock-tabs">{tabs.map(([id, label]) => <button key={id} className={active === id ? 'is-active' : ''} onClick={() => onChange(id)}>{label}</button>)}</div>;
}

function LibraryPanel({ definitions, filter, setFilter }: { definitions: ComponentDefinition[]; filter: string; setFilter(value: string): void }) {
  const groups = definitions
    .filter((definition) => `${definition.name} ${definition.type} ${definition.category}`.toLowerCase().includes(filter.toLowerCase()))
    .reduce<Record<string, ComponentDefinition[]>>((acc, definition) => {
      const key = definition.category ?? 'Other';
      (acc[key] ??= []).push(definition);
      return acc;
    }, {});
  return <div className="ew-panel-fill">
    <div className="ew-search"><Search size={13}/><input placeholder="Filter components..." value={filter} onChange={(event) => setFilter(event.target.value)} /></div>
    <div className="ew-library-list">
      {Object.entries(groups).map(([group, items]) => <div className="ew-tree-group" key={group}>
        <div className="ew-tree-heading"><ChevronDown size={12}/>{group}<span>{items.length}</span></div>
        {items.map((definition) => <div
          key={definition.id}
          draggable
          onDragStart={(event) => event.dataTransfer.setData('application/x-ew-definition', definition.id)}
          className="ew-library-item"
          title={definition.description}
        ><CircuitBoard size={14}/><span><strong>{definition.name}</strong><small>{definition.namespace}:{definition.type} · v{definition.version}</small></span></div>)}
      </div>)}
    </div>
  </div>;
}

function ProjectPanel({ project }: { project: Project }) {
  return <div className="ew-tree"><div className="ew-tree-heading"><ChevronDown size={12}/>{project.name}</div><div className="ew-tree-indent">Definitions <span>{project.definitions.length}</span></div>{project.diagrams.map((diagram) => <div className="ew-tree-indent" key={diagram.id}>Diagram: {diagram.name}</div>)}</div>;
}

function HierarchyPanel({ project, diagramId }: { project: Project; diagramId: string }) {
  const diagram = getDiagram(project, diagramId);
  return <div className="ew-tree"><div className="ew-tree-heading"><ChevronDown size={12}/>{diagram.name}</div>{diagram.instances.map((instance) => <div className="ew-tree-indent" key={instance.id}>{instance.name}</div>)}</div>;
}

function EmptyInspector() {
  return <div className="ew-empty-inspector"><CircuitBoard size={28}/><strong>No object selected</strong><span>Select a component, port, or connection on the diagram.</span></div>;
}

function PropertyRow({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="ew-property-row"><label>{label}</label><div>{children}</div></div>;
}

function InstanceInspector({ instance, definition, onRename }: { instance: any; definition: ComponentDefinition; onRename(name: string): void }) {
  const [name, setName] = useState(instance.name);
  if (name !== instance.name && document.activeElement?.getAttribute('data-inspector-name') !== 'true') setName(instance.name);
  return <div className="ew-inspector-scroll">
    <InspectorSection title="Identity">
      <PropertyRow label="Name"><input data-inspector-name="true" value={name} onChange={(event) => setName(event.target.value)} onBlur={() => onRename(name)} onKeyDown={(event) => { if (event.key === 'Enter') (event.currentTarget as HTMLInputElement).blur(); }} /></PropertyRow>
      <PropertyRow label="Definition"><span className="ew-value-readonly">{definition.name}</span></PropertyRow>
      <PropertyRow label="Type"><span className="ew-value-readonly">{definition.type}</span></PropertyRow>
      <PropertyRow label="Version"><span className="ew-value-readonly">{definition.version}</span></PropertyRow>
    </InspectorSection>
    <InspectorSection title="Placement">
      <PropertyRow label="X"><span className="ew-value-readonly">{instance.position.x}</span></PropertyRow>
      <PropertyRow label="Y"><span className="ew-value-readonly">{instance.position.y}</span></PropertyRow>
    </InspectorSection>
    {(definition.parameters ?? []).length > 0 && <InspectorSection title="Configuration">
      {(definition.parameters ?? []).map((parameter) => <PropertyRow key={parameter.id} label={parameter.name}><span className="ew-value-readonly">{String(instance.parameterValues[parameter.id] ?? parameter.defaultValue)} {parameter.unit ?? ''}</span></PropertyRow>)}
    </InspectorSection>}
    <InspectorSection title={`Ports (${definition.ports.length})`}>
      <div className="ew-mini-table">{definition.ports.map((port) => <div key={port.id}><span>{port.name}</span><span>{port.direction}</span><span>{port.dataType?.kind}{(port.dataType?.width ?? 1) > 1 ? `[${port.dataType?.width}]` : ''}</span></div>)}</div>
    </InspectorSection>
  </div>;
}

function ConnectionInspector({ connection, project, diagramId, onDelete }: { connection: any; project: Project; diagramId: string; onDelete(): void }) {
  const endpointName = (ref: any) => {
    const instance = getInstance(project, diagramId, ref.instanceId);
    const definition = instance ? getDefinition(project, instance.definitionId) : undefined;
    const port = definition?.ports.find((item) => item.id === ref.portId);
    return `${instance?.name ?? '?'} . ${port?.name ?? '?'}`;
  };
  return <div className="ew-inspector-scroll">
    <InspectorSection title="Connection">
      <PropertyRow label="ID"><span className="ew-value-readonly ew-mono">{connection.id}</span></PropertyRow>
      <PropertyRow label="Type"><span className="ew-value-readonly">{connection.type}</span></PropertyRow>
      <PropertyRow label="Routing"><span className="ew-value-readonly">{connection.route.mode} / {connection.route.router}</span></PropertyRow>
    </InspectorSection>
    <InspectorSection title="Endpoints">
      <PropertyRow label="Source"><span className="ew-value-readonly">{endpointName(connection.source)}</span></PropertyRow>
      {connection.targets.map((target: any, index: number) => <PropertyRow key={`${target.instanceId}:${target.portId}`} label={`Target ${index + 1}`}><span className="ew-value-readonly">{endpointName(target)}</span></PropertyRow>)}
    </InspectorSection>
    <div className="ew-inspector-actions"><button className="danger" onClick={onDelete}><CircleX size={14}/> Delete connection</button></div>
  </div>;
}

function InspectorSection({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="ew-inspector-section"><h3><ChevronDown size={12}/>{title}</h3><div>{children}</div></section>;
}

function ProblemsTable({ issues, onSelect }: { issues: ValidationIssue[]; onSelect(issue: ValidationIssue): void }) {
  return <table className="ew-data-table"><thead><tr><th>Severity</th><th>Code</th><th>Description</th><th>Object</th></tr></thead><tbody>{issues.length === 0 ? <tr><td colSpan={4}>No problems.</td></tr> : issues.map((issue) => <tr key={issue.id} onClick={() => onSelect(issue)}><td><span className={`ew-severity ew-severity--${issue.severity}`}>{issue.severity === 'error' ? <CircleX size={13}/> : issue.severity === 'warning' ? <AlertTriangle size={13}/> : <CircleCheck size={13}/>} {issue.severity}</span></td><td className="ew-mono">{issue.code}</td><td>{issue.message}</td><td>{issue.objectRef?.kind ?? ''}</td></tr>)}</tbody></table>;
}

function ConnectionsTable({ project, diagramId, onSelect }: { project: Project; diagramId: string; onSelect(id: string): void }) {
  const diagram = getDiagram(project, diagramId);
  const endpoint = (ref: any) => {
    const instance = getInstance(project, diagramId, ref.instanceId);
    const def = instance ? getDefinition(project, instance.definitionId) : undefined;
    return `${instance?.name ?? '?'} . ${def?.ports.find((p) => p.id === ref.portId)?.name ?? '?'}`;
  };
  return <table className="ew-data-table"><thead><tr><th>Type</th><th>Source</th><th>Target</th><th>Routing</th><th>ID</th></tr></thead><tbody>{diagram.connections.map((connection) => connection.targets.map((target) => <tr key={`${connection.id}:${target.instanceId}:${target.portId}`} onClick={() => onSelect(connection.id)}><td>{connection.type}</td><td>{endpoint(connection.source)}</td><td>{endpoint(target)}</td><td>{connection.route.mode}</td><td className="ew-mono">{connection.id}</td></tr>))}</tbody></table>;
}
