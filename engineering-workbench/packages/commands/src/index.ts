import {
  cloneProject,
  getDiagram,
  type ComponentInstance,
  type Connection,
  type DiagramId,
  type InstanceId,
  type Point,
  type Project
} from '@ew/core';

export interface ProjectCommand {
  readonly label: string;
  apply(project: Project): Project;
  revert(project: Project): Project;
}

export class CommandHistory {
  private undoStack: ProjectCommand[] = [];
  private redoStack: ProjectCommand[] = [];

  push(command: ProjectCommand): void {
    this.undoStack.push(command);
    this.redoStack.length = 0;
  }

  undo(project: Project): Project {
    const command = this.undoStack.pop();
    if (!command) return project;
    const result = command.revert(project);
    this.redoStack.push(command);
    return result;
  }

  redo(project: Project): Project {
    const command = this.redoStack.pop();
    if (!command) return project;
    const result = command.apply(project);
    this.undoStack.push(command);
    return result;
  }

  get canUndo(): boolean { return this.undoStack.length > 0; }
  get canRedo(): boolean { return this.redoStack.length > 0; }
  get nextUndoLabel(): string | undefined { return this.undoStack.at(-1)?.label; }
}

function mutateDiagram(project: Project, diagramId: DiagramId, fn: (diagram: ReturnType<typeof getDiagram>) => void): Project {
  const copy = cloneProject(project);
  fn(getDiagram(copy, diagramId));
  return copy;
}

export class AddInstanceCommand implements ProjectCommand {
  readonly label = 'Add component';
  constructor(private diagramId: DiagramId, private instance: ComponentInstance) {}
  apply(project: Project): Project {
    return mutateDiagram(project, this.diagramId, (diagram) => diagram.instances.push(structuredClone(this.instance)));
  }
  revert(project: Project): Project {
    return mutateDiagram(project, this.diagramId, (diagram) => {
      diagram.instances = diagram.instances.filter((item) => item.id !== this.instance.id);
      diagram.connections = diagram.connections.filter((connection) =>
        connection.source.instanceId !== this.instance.id &&
        connection.targets.every((target) => target.instanceId !== this.instance.id)
      );
    });
  }
}

export class MoveInstanceCommand implements ProjectCommand {
  readonly label = 'Move component';
  constructor(
    private diagramId: DiagramId,
    private instanceId: InstanceId,
    private from: Point,
    private to: Point
  ) {}
  private set(project: Project, position: Point): Project {
    return mutateDiagram(project, this.diagramId, (diagram) => {
      const instance = diagram.instances.find((item) => item.id === this.instanceId);
      if (instance) instance.position = { ...position };
    });
  }
  apply(project: Project): Project { return this.set(project, this.to); }
  revert(project: Project): Project { return this.set(project, this.from); }
}

export class RenameInstanceCommand implements ProjectCommand {
  readonly label = 'Rename component';
  constructor(
    private diagramId: DiagramId,
    private instanceId: InstanceId,
    private before: string,
    private after: string
  ) {}
  private set(project: Project, name: string): Project {
    return mutateDiagram(project, this.diagramId, (diagram) => {
      const instance = diagram.instances.find((item) => item.id === this.instanceId);
      if (instance) instance.name = name;
    });
  }
  apply(project: Project): Project { return this.set(project, this.after); }
  revert(project: Project): Project { return this.set(project, this.before); }
}

export class AddConnectionCommand implements ProjectCommand {
  readonly label = 'Create connection';
  constructor(private diagramId: DiagramId, private connection: Connection) {}
  apply(project: Project): Project {
    return mutateDiagram(project, this.diagramId, (diagram) => diagram.connections.push(structuredClone(this.connection)));
  }
  revert(project: Project): Project {
    return mutateDiagram(project, this.diagramId, (diagram) => {
      diagram.connections = diagram.connections.filter((item) => item.id !== this.connection.id);
    });
  }
}

export class DeleteConnectionCommand implements ProjectCommand {
  readonly label = 'Delete connection';
  constructor(private diagramId: DiagramId, private connection: Connection) {}
  apply(project: Project): Project {
    return mutateDiagram(project, this.diagramId, (diagram) => {
      diagram.connections = diagram.connections.filter((item) => item.id !== this.connection.id);
    });
  }
  revert(project: Project): Project {
    return mutateDiagram(project, this.diagramId, (diagram) => diagram.connections.push(structuredClone(this.connection)));
  }
}
