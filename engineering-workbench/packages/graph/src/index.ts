import {
  createId,
  getDefinition,
  getDiagram,
  getInstance,
  getPort,
  type Connection,
  type DiagramId,
  type EndpointRef,
  type Project
} from '@ew/core';
import type {
  CompatibilityProvider,
  CompatibilityResult,
  EndpointDescriptor
} from '@ew/plugin-api';

function descriptor(project: Project, diagramId: DiagramId, ref: EndpointRef): EndpointDescriptor | undefined {
  const instance = getInstance(project, diagramId, ref.instanceId);
  if (!instance) return undefined;
  const definition = getDefinition(project, instance.definitionId);
  const port = getPort(project, diagramId, ref);
  if (!definition || !port) return undefined;
  return { ref, port, definition, instanceName: instance.name };
}

export function endpointKey(ref: EndpointRef): string {
  return `${ref.instanceId}:${ref.portId}`;
}

export function equivalentEndpoints(a: EndpointRef, b: EndpointRef): boolean {
  return a.instanceId === b.instanceId && a.portId === b.portId;
}

export function connectionExists(
  project: Project,
  diagramId: DiagramId,
  source: EndpointRef,
  target: EndpointRef
): Connection | undefined {
  const diagram = getDiagram(project, diagramId);
  return diagram.connections.find((connection) => {
    const direct = equivalentEndpoints(connection.source, source) &&
      connection.targets.some((item) => equivalentEndpoints(item, target));
    const reversed = equivalentEndpoints(connection.source, target) &&
      connection.targets.some((item) => equivalentEndpoints(item, source));
    return direct || reversed;
  });
}

export function evaluateCompatibility(
  project: Project,
  diagramId: DiagramId,
  sourceRef: EndpointRef,
  targetRef: EndpointRef,
  providers: CompatibilityProvider[]
): CompatibilityResult {
  if (equivalentEndpoints(sourceRef, targetRef)) {
    return { status: 'incompatible', message: 'A port cannot connect to itself.' };
  }
  if (sourceRef.instanceId === targetRef.instanceId) {
    return { status: 'incompatible', message: 'Loopback connections require an explicit domain rule.' };
  }
  if (connectionExists(project, diagramId, sourceRef, targetRef)) {
    return { status: 'incompatible', message: 'An equivalent connection already exists.' };
  }

  const source = descriptor(project, diagramId, sourceRef);
  const target = descriptor(project, diagramId, targetRef);
  if (!source || !target) {
    return { status: 'incompatible', message: 'One or both endpoints are unresolved.' };
  }

  for (const provider of providers) {
    const result = provider.evaluate(source, target, { project, diagramId });
    if (result) return result;
  }

  return { status: 'incompatible', message: 'No compatibility provider accepted these endpoints.' };
}

export function createConnection(
  source: EndpointRef,
  target: EndpointRef,
  result: CompatibilityResult
): Connection {
  return {
    id: createId('conn'),
    type: result.connectionType ?? 'signal',
    source,
    targets: [target],
    route: { mode: 'automatic', router: 'orthogonal', waypoints: [] }
  };
}

export function connectionsForEndpoint(project: Project, diagramId: DiagramId, endpoint: EndpointRef): Connection[] {
  return getDiagram(project, diagramId).connections.filter((connection) =>
    equivalentEndpoints(connection.source, endpoint) ||
    connection.targets.some((target) => equivalentEndpoints(target, endpoint))
  );
}
