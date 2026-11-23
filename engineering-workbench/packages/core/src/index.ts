export type Id = string;
export type DefinitionId = Id;
export type InstanceId = Id;
export type PortId = Id;
export type InterfaceId = Id;
export type ConnectionId = Id;
export type DiagramId = Id;

export interface Point { x: number; y: number; }
export interface Size { width: number; height: number; }
export interface Rect extends Point, Size {}

export type PortDirection = 'input' | 'output' | 'inout' | 'passive' | 'monitor';
export type PortSide = 'left' | 'right' | 'top' | 'bottom';

export interface TypeDescriptor {
  kind: string;
  width?: number;
  protocol?: string;
  domain?: string;
  unit?: string;
}

export interface PortDefinition {
  id: PortId;
  name: string;
  direction: PortDirection;
  side?: PortSide;
  dataType?: TypeDescriptor;
  required?: boolean;
  cardinality?: 'single' | 'multiple';
  tags?: string[];
  description?: string;
}

export interface InterfaceMember {
  logicalName: string;
  portId: PortId;
}

export interface InterfaceDefinition {
  id: InterfaceId;
  name: string;
  interfaceType: string;
  role?: string;
  members: InterfaceMember[];
}

export interface ParameterDefinition {
  id: string;
  name: string;
  type: 'string' | 'number' | 'boolean';
  defaultValue: string | number | boolean;
  unit?: string;
}

export interface ComponentDefinition {
  id: DefinitionId;
  type: string;
  namespace?: string;
  name: string;
  version?: string;
  description?: string;
  category?: string;
  ports: PortDefinition[];
  interfaces?: InterfaceDefinition[];
  parameters?: ParameterDefinition[];
  visual?: {
    icon?: string;
    minWidth?: number;
    accent?: string;
  };
  metadata?: Record<string, unknown>;
}

export interface HierarchyPort {
  id: Id;
  name: string;
  childEndpoint: EndpointRef;
  direction?: PortDirection;
  dataType?: TypeDescriptor;
}

export interface Portal {
  id: Id;
  name: string;
  position: Point;
  scope?: string;
  metadata?: Record<string, unknown>;
}

export interface Region {
  id: Id;
  name: string;
  bounds: Rect;
  metadata?: Record<string, unknown>;
}

export interface ComponentInstance {
  id: InstanceId;
  definitionId: DefinitionId;
  name: string;
  position: Point;
  size?: Size;
  parameterValues: Record<string, string | number | boolean>;
  locked?: boolean;
  childDiagramId?: DiagramId;
  metadata?: Record<string, unknown>;
}

export interface EndpointRef {
  instanceId: InstanceId;
  portId: PortId;
}

export type ConnectionType = 'signal' | 'bus' | 'clock' | 'reset' | 'logical' | 'hierarchy' | 'portal' | string;

export interface Waypoint extends Point { locked?: boolean; }

export interface ConnectionRoute {
  mode: 'automatic' | 'semiAutomatic' | 'manual';
  router: 'orthogonal' | 'polyline' | string;
  waypoints: Waypoint[];
}

export interface Connection {
  id: ConnectionId;
  type: ConnectionType;
  source: EndpointRef;
  targets: EndpointRef[];
  label?: string;
  route: ConnectionRoute;
  metadata?: Record<string, unknown>;
}

export interface Annotation {
  id: Id;
  text: string;
  position: Point;
}

export interface Diagram {
  id: DiagramId;
  name: string;
  instances: ComponentInstance[];
  connections: Connection[];
  hierarchyPorts?: HierarchyPort[];
  portals?: Portal[];
  regions?: Region[];
  annotations?: Annotation[];
}

export interface Project {
  schemaVersion: number;
  id: Id;
  name: string;
  definitions: ComponentDefinition[];
  diagrams: Diagram[];
  pluginData?: Record<string, unknown>;
}

export type IssueSeverity = 'info' | 'warning' | 'error';

export interface ObjectRef {
  kind: 'instance' | 'connection' | 'port' | 'diagram';
  id: string;
  parentId?: string;
}

export interface ValidationIssue {
  id: string;
  severity: IssueSeverity;
  code: string;
  message: string;
  objectRef?: ObjectRef;
  relatedObjects?: ObjectRef[];
}

let sequence = 0;
export function createId(prefix: string): string {
  sequence += 1;
  const time = Date.now().toString(36);
  return `${prefix}-${time}-${sequence.toString(36)}`;
}

export function cloneProject(project: Project): Project {
  return structuredClone(project);
}

export function getDiagram(project: Project, diagramId: DiagramId): Diagram {
  const diagram = project.diagrams.find((item) => item.id === diagramId);
  if (!diagram) throw new Error(`Diagram not found: ${diagramId}`);
  return diagram;
}

export function getDefinition(project: Project, id: DefinitionId): ComponentDefinition | undefined {
  return project.definitions.find((definition) => definition.id === id);
}

export function getInstance(project: Project, diagramId: DiagramId, id: InstanceId): ComponentInstance | undefined {
  return getDiagram(project, diagramId).instances.find((instance) => instance.id === id);
}

export function getPort(project: Project, diagramId: DiagramId, endpoint: EndpointRef): PortDefinition | undefined {
  const instance = getInstance(project, diagramId, endpoint.instanceId);
  if (!instance) return undefined;
  return getDefinition(project, instance.definitionId)?.ports.find((port) => port.id === endpoint.portId);
}
