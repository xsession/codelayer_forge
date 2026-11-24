import { useCallback, useMemo, useRef, useState } from 'react';
import {
  createId,
  getDiagram,
  type ComponentDefinition,
  type ComponentInstance,
  type Connection,
  type EndpointRef,
  type Point,
  type Project
} from '@ew/core';
import {
  AddConnectionCommand,
  AddInstanceCommand,
  CommandHistory,
  DeleteConnectionCommand,
  MoveInstanceCommand,
  RenameInstanceCommand,
  type ProjectCommand
} from '@ew/commands';
import { createConnection, evaluateCompatibility } from '@ew/graph';
import type { PluginRegistry } from '@ew/plugin-api';

export type Selection =
  | { kind: 'instance'; id: string }
  | { kind: 'connection'; id: string }
  | { kind: 'port'; instanceId: string; portId: string }
  | undefined;

export interface WorkbenchModel {
  project: Project;
  diagramId: string;
  registry: PluginRegistry;
  selection: Selection;
  setSelection(selection: Selection): void;
  execute(command: ProjectCommand): void;
  undo(): void;
  redo(): void;
  canUndo: boolean;
  canRedo: boolean;
  addDefinitionInstance(definition: ComponentDefinition, position: Point): void;
  moveInstance(instanceId: string, from: Point, to: Point): void;
  renameInstance(instanceId: string, before: string, after: string): void;
  connect(source: EndpointRef, target: EndpointRef): { ok: boolean; message?: string; connection?: Connection };
  deleteConnection(connection: Connection): void;
}

export function useWorkbenchModel(initialProject: Project, diagramId: string, registry: PluginRegistry): WorkbenchModel {
  const [project, setProject] = useState(initialProject);
  const [selection, setSelection] = useState<Selection>();
  const history = useRef(new CommandHistory());

  const execute = useCallback((command: ProjectCommand) => {
    setProject((current) => command.apply(current));
    history.current.push(command);
  }, []);

  const undo = useCallback(() => setProject((current) => history.current.undo(current)), []);
  const redo = useCallback(() => setProject((current) => history.current.redo(current)), []);

  const addDefinitionInstance = useCallback((definition: ComponentDefinition, position: Point) => {
    const diagram = getDiagram(project, diagramId);
    const base = definition.name.replace(/[^A-Za-z0-9]+/g, '_').toLowerCase();
    const nextIndex = diagram.instances.filter((instance) => instance.definitionId === definition.id).length;
    const instance: ComponentInstance = {
      id: createId('inst'), definitionId: definition.id,
      name: `${base}${nextIndex}`,
      position,
      parameterValues: Object.fromEntries((definition.parameters ?? []).map((parameter) => [parameter.id, parameter.defaultValue]))
    };
    execute(new AddInstanceCommand(diagramId, instance));
    setSelection({ kind: 'instance', id: instance.id });
  }, [diagramId, execute, project]);

  const moveInstance = useCallback((instanceId: string, from: Point, to: Point) => {
    if (from.x === to.x && from.y === to.y) return;
    execute(new MoveInstanceCommand(diagramId, instanceId, from, to));
  }, [diagramId, execute]);

  const renameInstance = useCallback((instanceId: string, before: string, after: string) => {
    if (before === after || !after.trim()) return;
    execute(new RenameInstanceCommand(diagramId, instanceId, before, after.trim()));
  }, [diagramId, execute]);

  const connect = useCallback((source: EndpointRef, target: EndpointRef) => {
    const result = evaluateCompatibility(project, diagramId, source, target, registry.compatibilityProviders);
    if (result.status === 'incompatible') return { ok: false, message: result.message };
    const connection = createConnection(source, target, result);
    execute(new AddConnectionCommand(diagramId, connection));
    setSelection({ kind: 'connection', id: connection.id });
    return { ok: true, message: result.message, connection };
  }, [diagramId, execute, project, registry.compatibilityProviders]);

  const deleteConnection = useCallback((connection: Connection) => {
    execute(new DeleteConnectionCommand(diagramId, connection));
    setSelection(undefined);
  }, [diagramId, execute]);

  return useMemo(() => ({
    project, diagramId, registry, selection, setSelection, execute,
    undo, redo,
    canUndo: history.current.canUndo,
    canRedo: history.current.canRedo,
    addDefinitionInstance, moveInstance, renameInstance, connect, deleteConnection
  }), [project, diagramId, registry, selection, execute, undo, redo, addDefinitionInstance, moveInstance, renameInstance, connect, deleteConnection]);
}
