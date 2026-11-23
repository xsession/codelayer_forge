import { describe, expect, it } from 'vitest';
import { CommandHistory, MoveInstanceCommand } from '@ew/commands';
import { demoProject } from '../apps/demo/src/demoProject';

describe('command history', () => {
  it('undoes and redoes an instance move', () => {
    const history = new CommandHistory();
    const command = new MoveInstanceCommand('diagram-top', 'cpu0', { x: 430, y: 120 }, { x: 500, y: 200 });
    let project = command.apply(demoProject);
    history.push(command);
    expect(project.diagrams[0].instances.find((i) => i.id === 'cpu0')?.position).toEqual({ x: 500, y: 200 });
    project = history.undo(project);
    expect(project.diagrams[0].instances.find((i) => i.id === 'cpu0')?.position).toEqual({ x: 430, y: 120 });
    project = history.redo(project);
    expect(project.diagrams[0].instances.find((i) => i.id === 'cpu0')?.position).toEqual({ x: 500, y: 200 });
  });
});
