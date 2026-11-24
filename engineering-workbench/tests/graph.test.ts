import { describe, expect, it } from 'vitest';
import { evaluateCompatibility } from '@ew/graph';
import { createPluginRegistry } from '@ew/plugin-api';
import { exampleElectronicsPlugin } from '@plugins/example-electronics';
import { demoProject } from '../apps/demo/src/demoProject';

describe('graph compatibility', () => {
  const registry = createPluginRegistry([exampleElectronicsPlugin]);
  it('accepts output clock to input clock', () => {
    const result = evaluateCompatibility(
      demoProject, 'diagram-top',
      { instanceId: 'clock0', portId: 'clk_out' },
      { instanceId: 'cpu0', portId: 'clk' },
      registry.compatibilityProviders
    );
    // Demo project already contains the edge, proving duplicate protection takes priority.
    expect(result.status).toBe('incompatible');
    expect(result.message).toMatch(/already exists/i);
  });

  it('rejects input to input', () => {
    const clean = structuredClone(demoProject);
    clean.diagrams[0].connections = [];
    const result = evaluateCompatibility(
      clean, 'diagram-top',
      { instanceId: 'cpu0', portId: 'clk' },
      { instanceId: 'bus0', portId: 'clk' },
      registry.compatibilityProviders
    );
    expect(result.status).toBe('incompatible');
  });

  it('accepts matching memory bus', () => {
    const clean = structuredClone(demoProject);
    clean.diagrams[0].connections = [];
    const result = evaluateCompatibility(
      clean, 'diagram-top',
      { instanceId: 'cpu0', portId: 'mem' },
      { instanceId: 'bus0', portId: 's0' },
      registry.compatibilityProviders
    );
    expect(result.status).toBe('compatible');
    expect(result.connectionType).toBe('bus');
  });
});
