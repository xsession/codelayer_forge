import { getDefinition, getDiagram, type EndpointRef, type Point, type Project, type Rect } from '@ew/core';

export const NODE_WIDTH = 244;
export const NODE_HEADER = 38;
export const PORT_ROW = 24;
export const NODE_PADDING_BOTTOM = 10;

export interface PortLayout {
  endpoint: EndpointRef;
  point: Point;
  side: 'left' | 'right';
  row: number;
}

export function instanceRect(project: Project, diagramId: string, instanceId: string): Rect | undefined {
  const diagram = getDiagram(project, diagramId);
  const instance = diagram.instances.find((item) => item.id === instanceId);
  if (!instance) return undefined;
  const definition = getDefinition(project, instance.definitionId);
  if (!definition) return undefined;
  const left = definition.ports.filter((p) => (p.side ?? (p.direction === 'input' ? 'left' : 'right')) === 'left');
  const right = definition.ports.filter((p) => (p.side ?? (p.direction === 'input' ? 'left' : 'right')) === 'right');
  const rows = Math.max(left.length, right.length, 1);
  return {
    x: instance.position.x,
    y: instance.position.y,
    width: instance.size?.width ?? Math.max(NODE_WIDTH, definition.visual?.minWidth ?? NODE_WIDTH),
    height: instance.size?.height ?? NODE_HEADER + rows * PORT_ROW + NODE_PADDING_BOTTOM
  };
}

export function portLayouts(project: Project, diagramId: string, instanceId: string): PortLayout[] {
  const diagram = getDiagram(project, diagramId);
  const instance = diagram.instances.find((item) => item.id === instanceId);
  if (!instance) return [];
  const definition = getDefinition(project, instance.definitionId);
  const rect = instanceRect(project, diagramId, instanceId);
  if (!definition || !rect) return [];
  const left = definition.ports.filter((p) => (p.side ?? (p.direction === 'input' ? 'left' : 'right')) === 'left');
  const right = definition.ports.filter((p) => (p.side ?? (p.direction === 'input' ? 'left' : 'right')) === 'right');
  return [
    ...left.map((port, index) => ({
      endpoint: { instanceId, portId: port.id },
      point: { x: rect.x, y: rect.y + NODE_HEADER + PORT_ROW * (index + 0.5) },
      side: 'left' as const,
      row: index
    })),
    ...right.map((port, index) => ({
      endpoint: { instanceId, portId: port.id },
      point: { x: rect.x + rect.width, y: rect.y + NODE_HEADER + PORT_ROW * (index + 0.5) },
      side: 'right' as const,
      row: index
    }))
  ];
}

export function portPoint(project: Project, diagramId: string, endpoint: EndpointRef): Point | undefined {
  return portLayouts(project, diagramId, endpoint.instanceId).find((item) => item.endpoint.portId === endpoint.portId)?.point;
}
