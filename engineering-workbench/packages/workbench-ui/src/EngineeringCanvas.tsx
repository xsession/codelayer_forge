import { useMemo, useRef, useState } from 'react';
import {
  getDefinition,
  getDiagram,
  getPort,
  type ComponentInstance,
  type EndpointRef,
  type Point
} from '@ew/core';
import { evaluateCompatibility } from '@ew/graph';
import { polylinePath, routeOrthogonal } from '@ew/router';
import type { WorkbenchModel } from './model';
import { instanceRect, portLayouts, portPoint } from './layout';

interface Props { model: WorkbenchModel; }
interface Viewport { x: number; y: number; zoom: number; }
interface Draft { source: EndpointRef; pointer: Point; }

function worldPoint(event: React.PointerEvent, container: HTMLDivElement, viewport: Viewport): Point {
  const rect = container.getBoundingClientRect();
  return {
    x: (event.clientX - rect.left - viewport.x) / viewport.zoom,
    y: (event.clientY - rect.top - viewport.y) / viewport.zoom
  };
}

export function EngineeringCanvas({ model }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [viewport, setViewport] = useState<Viewport>({ x: 42, y: 36, zoom: 0.86 });
  const [draft, setDraft] = useState<Draft>();
  const [message, setMessage] = useState('Ready');
  const [dragging, setDragging] = useState<{ instanceId: string; start: Point; origin: Point; preview: Point }>();
  const [panning, setPanning] = useState<{ pointer: Point; origin: Point }>();
  const diagram = getDiagram(model.project, model.diagramId);

  const routes = useMemo(() => {
    return diagram.connections.flatMap((connection) => {
      const source = portPoint(model.project, model.diagramId, connection.source);
      if (!source) return [];
      return connection.targets.flatMap((target) => {
        const targetPoint = portPoint(model.project, model.diagramId, target);
        if (!targetPoint) return [];
        const obstacleRects = diagram.instances
          .filter((instance) => instance.id !== connection.source.instanceId && instance.id !== target.instanceId)
          .map((instance) => instanceRect(model.project, model.diagramId, instance.id))
          .filter((rect): rect is NonNullable<typeof rect> => Boolean(rect));
        const points = routeOrthogonal(source, targetPoint, obstacleRects, { grid: 12, clearance: 10, margin: 220 });
        return [{ connection, target, points }];
      });
    });
  }, [diagram.connections, diagram.instances, model.project, model.diagramId]);

  const onWheel = (event: React.WheelEvent) => {
    event.preventDefault();
    const container = containerRef.current;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    const mx = event.clientX - rect.left;
    const my = event.clientY - rect.top;
    const oldZoom = viewport.zoom;
    const nextZoom = Math.min(2.5, Math.max(0.25, oldZoom * (event.deltaY < 0 ? 1.1 : 0.9)));
    const wx = (mx - viewport.x) / oldZoom;
    const wy = (my - viewport.y) / oldZoom;
    setViewport({ x: mx - wx * nextZoom, y: my - wy * nextZoom, zoom: nextZoom });
  };

  const startPan = (event: React.PointerEvent) => {
    if (event.button !== 1 && !(event.button === 0 && event.shiftKey)) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    setPanning({ pointer: { x: event.clientX, y: event.clientY }, origin: { x: viewport.x, y: viewport.y } });
  };

  const onCanvasPointerMove = (event: React.PointerEvent) => {
    const container = containerRef.current;
    if (!container) return;
    if (panning) {
      setViewport((current) => ({ ...current,
        x: panning.origin.x + event.clientX - panning.pointer.x,
        y: panning.origin.y + event.clientY - panning.pointer.y
      }));
      return;
    }
    const pointer = worldPoint(event, container, viewport);
    if (draft) setDraft({ ...draft, pointer });
    if (dragging) {
      const delta = { x: pointer.x - dragging.start.x, y: pointer.y - dragging.start.y };
      setDragging({ ...dragging, preview: {
        x: Math.round((dragging.origin.x + delta.x) / 10) * 10,
        y: Math.round((dragging.origin.y + delta.y) / 10) * 10
      }});
    }
  };

  const endCanvasPointer = () => {
    if (panning) setPanning(undefined);
    if (dragging) {
      model.moveInstance(dragging.instanceId, dragging.origin, dragging.preview);
      setDragging(undefined);
    }
    if (draft) {
      setDraft(undefined);
      setMessage('Connection cancelled');
    }
  };

  const startNodeDrag = (event: React.PointerEvent, instance: ComponentInstance) => {
    if (event.button !== 0) return;
    event.stopPropagation();
    const container = containerRef.current;
    if (!container) return;
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    model.setSelection({ kind: 'instance', id: instance.id });
    setDragging({ instanceId: instance.id, start: worldPoint(event, container, viewport), origin: instance.position, preview: instance.position });
  };

  const startConnection = (event: React.PointerEvent, source: EndpointRef) => {
    event.stopPropagation();
    const container = containerRef.current;
    if (!container) return;
    setDraft({ source, pointer: worldPoint(event, container, viewport) });
    model.setSelection({ kind: 'port', instanceId: source.instanceId, portId: source.portId });
    setMessage('Choose a compatible target');
  };

  const finishConnection = (event: React.PointerEvent, target: EndpointRef) => {
    event.stopPropagation();
    if (!draft) return;
    const result = model.connect(draft.source, target);
    setDraft(undefined);
    setMessage(result.ok ? (result.message ? `Connected with warning: ${result.message}` : 'Connection created') : (result.message ?? 'Incompatible connection'));
  };

  const dropDefinition = (event: React.DragEvent) => {
    event.preventDefault();
    const definitionId = event.dataTransfer.getData('application/x-ew-definition');
    const definition = model.project.definitions.find((item) => item.id === definitionId);
    const container = containerRef.current;
    if (!definition || !container) return;
    const rect = container.getBoundingClientRect();
    const position = {
      x: Math.round(((event.clientX - rect.left - viewport.x) / viewport.zoom) / 10) * 10,
      y: Math.round(((event.clientY - rect.top - viewport.y) / viewport.zoom) / 10) * 10
    };
    model.addDefinitionInstance(definition, position);
    setMessage(`${definition.name} added`);
  };

  const selectedConnectionId = model.selection?.kind === 'connection' ? model.selection.id : undefined;

  return (
    <div
      className="ew-canvas"
      ref={containerRef}
      onWheel={onWheel}
      onPointerDown={(event) => { startPan(event); if (event.button === 0 && !event.shiftKey) model.setSelection(undefined); }}
      onPointerMove={onCanvasPointerMove}
      onPointerUp={endCanvasPointer}
      onPointerCancel={endCanvasPointer}
      onDragOver={(event) => event.preventDefault()}
      onDrop={dropDefinition}
      data-testid="engineering-canvas"
    >
      <div className="ew-world" style={{ transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})` }}>
        <svg className="ew-connections" width="4000" height="2600" viewBox="0 0 4000 2600">
          {routes.map(({ connection, target, points }) => {
            const selected = connection.id === selectedConnectionId;
            return (
              <g key={`${connection.id}:${target.instanceId}:${target.portId}`}>
                <path
                  className="ew-edge-hit"
                  d={polylinePath(points)}
                  onPointerDown={(event) => { event.stopPropagation(); model.setSelection({ kind: 'connection', id: connection.id }); }}
                />
                <path className={`ew-edge ew-edge--${connection.type} ${selected ? 'is-selected' : ''}`} d={polylinePath(points)} />
                {points.length > 1 && <circle className="ew-direction-dot" cx={points[Math.floor(points.length / 2)].x} cy={points[Math.floor(points.length / 2)].y} r="3" />}
              </g>
            );
          })}
          {draft && (() => {
            const source = portPoint(model.project, model.diagramId, draft.source);
            if (!source) return null;
            const points = routeOrthogonal(source, draft.pointer, [], { grid: 10, clearance: 0, margin: 80 });
            return <path className="ew-edge ew-edge--draft" d={polylinePath(points)} />;
          })()}
        </svg>

        {diagram.instances.map((instance) => {
          const definition = getDefinition(model.project, instance.definitionId);
          if (!definition) return null;
          const rect = instanceRect(model.project, model.diagramId, instance.id)!;
          const previewPosition = dragging?.instanceId === instance.id ? dragging.preview : instance.position;
          const selected = model.selection?.kind === 'instance' && model.selection.id === instance.id;
          const layouts = portLayouts(model.project, model.diagramId, instance.id);
          const leftPorts = layouts.filter((p) => p.side === 'left');
          const rightPorts = layouts.filter((p) => p.side === 'right');
          const portById = new Map(definition.ports.map((p) => [p.id, p]));
          return (
            <div
              key={instance.id}
              className={`ew-node ${selected ? 'is-selected' : ''}`}
              style={{ left: previewPosition.x, top: previewPosition.y, width: rect.width, height: rect.height }}
              data-instance-id={instance.id}
            >
              <div className="ew-node-header" onPointerDown={(event) => startNodeDrag(event, instance)}>
                <span className="ew-node-type">{definition.type}</span>
                <strong>{instance.name}</strong>
                <span className="ew-node-version">{definition.version ?? ''}</span>
              </div>
              <div className="ew-node-body">
                <div className="ew-port-column ew-port-column--left">
                  {leftPorts.map((layout) => {
                    const port = portById.get(layout.endpoint.portId)!;
                    const compatibility = draft ? evaluateCompatibility(model.project, model.diagramId, draft.source, layout.endpoint, model.registry.compatibilityProviders) : undefined;
                    return <PortRow key={port.id} port={port} endpoint={layout.endpoint} side="left" compatibility={compatibility?.status} onStart={startConnection} onFinish={finishConnection} draft={Boolean(draft)} />;
                  })}
                </div>
                <div className="ew-port-column ew-port-column--right">
                  {rightPorts.map((layout) => {
                    const port = portById.get(layout.endpoint.portId)!;
                    const compatibility = draft ? evaluateCompatibility(model.project, model.diagramId, draft.source, layout.endpoint, model.registry.compatibilityProviders) : undefined;
                    return <PortRow key={port.id} port={port} endpoint={layout.endpoint} side="right" compatibility={compatibility?.status} onStart={startConnection} onFinish={finishConnection} draft={Boolean(draft)} />;
                  })}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <div className="ew-canvas-hud">
        <span>{Math.round(viewport.zoom * 100)}%</span>
        <span>Shift+drag / middle-drag to pan</span>
        <span>{message}</span>
      </div>
    </div>
  );
}

function PortRow({
  port, endpoint, side, compatibility, onStart, onFinish, draft
}: {
  port: NonNullable<ReturnType<typeof getPort>>;
  endpoint: EndpointRef;
  side: 'left' | 'right';
  compatibility?: string;
  onStart(event: React.PointerEvent, endpoint: EndpointRef): void;
  onFinish(event: React.PointerEvent, endpoint: EndpointRef): void;
  draft: boolean;
}) {
  const stateClass = draft && compatibility ? `compat-${compatibility}` : '';
  const marker = <button
    className={`ew-port-marker ${stateClass}`}
    title={`${port.name}: ${port.direction} ${port.dataType?.kind ?? ''}${port.dataType?.width ? ` [${port.dataType.width}]` : ''}`}
    onPointerDown={(event) => onStart(event, endpoint)}
    onPointerUp={(event) => draft ? onFinish(event, endpoint) : undefined}
    aria-label={`Port ${port.name}`}
  />;
  return (
    <div className={`ew-port-row ew-port-row--${side} ${stateClass}`}>
      {side === 'left' && marker}
      <span className="ew-port-name">{port.name}</span>
      <span className="ew-port-kind">{port.dataType?.kind}{(port.dataType?.width ?? 1) > 1 ? `:${port.dataType?.width}` : ''}</span>
      {side === 'right' && marker}
    </div>
  );
}
