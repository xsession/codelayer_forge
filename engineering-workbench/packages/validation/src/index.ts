import {
  getDefinition,
  getDiagram,
  getPort,
  type DiagramId,
  type Project,
  type ValidationIssue
} from '@ew/core';
import { connectionsForEndpoint, evaluateCompatibility } from '@ew/graph';
import type { PluginRegistry } from '@ew/plugin-api';

export function validateDiagram(project: Project, diagramId: DiagramId, registry: PluginRegistry): ValidationIssue[] {
  const diagram = getDiagram(project, diagramId);
  const issues: ValidationIssue[] = [];

  for (const connection of diagram.connections) {
    for (const target of connection.targets) {
      const sourcePort = getPort(project, diagramId, connection.source);
      const targetPort = getPort(project, diagramId, target);
      if (!sourcePort || !targetPort) {
        issues.push({
          id: `unresolved:${connection.id}:${target.instanceId}:${target.portId}`,
          severity: 'error',
          code: 'E001',
          message: 'Connection has an unresolved endpoint.',
          objectRef: { kind: 'connection', id: connection.id }
        });
        continue;
      }
      const result = evaluateCompatibilityIgnoringDuplicate(project, diagramId, connection.source, target, registry);
      if (result.status === 'incompatible') {
        issues.push({
          id: `invalid:${connection.id}:${target.instanceId}:${target.portId}`,
          severity: 'error',
          code: 'E120',
          message: result.message ?? 'Incompatible connection.',
          objectRef: { kind: 'connection', id: connection.id }
        });
      } else if (result.status === 'compatible-warning' || result.status === 'requires-adapter') {
        issues.push({
          id: `warn:${connection.id}:${target.instanceId}:${target.portId}`,
          severity: 'warning',
          code: 'W080',
          message: result.message ?? 'Connection requires review.',
          objectRef: { kind: 'connection', id: connection.id }
        });
      }
    }
  }

  for (const instance of diagram.instances) {
    const definition = getDefinition(project, instance.definitionId);
    if (!definition) {
      issues.push({
        id: `missingdef:${instance.id}`,
        severity: 'error',
        code: 'E010',
        message: `Missing component definition for ${instance.name}.`,
        objectRef: { kind: 'instance', id: instance.id }
      });
      continue;
    }
    for (const port of definition.ports.filter((item) => item.required)) {
      const count = connectionsForEndpoint(project, diagramId, { instanceId: instance.id, portId: port.id }).length;
      if (count === 0) {
        issues.push({
          id: `required:${instance.id}:${port.id}`,
          severity: 'warning',
          code: 'W044',
          message: `${instance.name}.${port.name} is required but unconnected.`,
          objectRef: { kind: 'port', id: port.id, parentId: instance.id }
        });
      }
    }
  }

  for (const validator of registry.validators) {
    issues.push(...validator.validate(project, diagramId));
  }

  return issues;
}

function evaluateCompatibilityIgnoringDuplicate(
  project: Project,
  diagramId: DiagramId,
  source: { instanceId: string; portId: string },
  target: { instanceId: string; portId: string },
  registry: PluginRegistry
) {
  // Existing connections would normally trigger duplicate detection. Validate a temporary
  // project without the same edge so semantic compatibility can be checked independently.
  const clone = structuredClone(project);
  const diagram = getDiagram(clone, diagramId);
  diagram.connections = diagram.connections.filter((connection) => !(
    connection.source.instanceId === source.instanceId &&
    connection.source.portId === source.portId &&
    connection.targets.some((item) => item.instanceId === target.instanceId && item.portId === target.portId)
  ));
  return evaluateCompatibility(clone, diagramId, source, target, registry.compatibilityProviders);
}
