import { type Connection, type Project } from '@ew/core';
import { electronicsDefinitions } from '@plugins/example-electronics';

const conn = (id: string, type: string, sourceInstance: string, sourcePort: string, targetInstance: string, targetPort: string): Connection => ({
  id, type,
  source: { instanceId: sourceInstance, portId: sourcePort },
  targets: [{ instanceId: targetInstance, portId: targetPort }],
  route: { mode: 'automatic', router: 'orthogonal', waypoints: [] }
});

export const demoProject: Project = {
  schemaVersion: 1,
  id: 'project-demo',
  name: 'SoC Platform Demo',
  definitions: electronicsDefinitions,
  diagrams: [{
    id: 'diagram-top',
    name: 'soc_top',
    instances: [
      { id: 'clock0', definitionId: 'def.clock', name: 'sys_clk', position: { x: 70, y: 110 }, parameterValues: { frequency: 100 } },
      { id: 'reset0', definitionId: 'def.reset', name: 'sys_reset', position: { x: 70, y: 300 }, parameterValues: {} },
      { id: 'cpu0', definitionId: 'def.cpu', name: 'cpu0', position: { x: 430, y: 120 }, parameterValues: { freq: 100, debug: true } },
      { id: 'bus0', definitionId: 'def.bus', name: 'sys_bus', position: { x: 810, y: 250 }, parameterValues: {} },
      { id: 'ram0', definitionId: 'def.ram', name: 'sram0', position: { x: 1230, y: 100 }, parameterValues: { size: 128 } },
      { id: 'uart0', definitionId: 'def.uart', name: 'uart0', position: { x: 1230, y: 310 }, parameterValues: {} },
      { id: 'spi0', definitionId: 'def.spi', name: 'spi0', position: { x: 1230, y: 545 }, parameterValues: {} },
      { id: 'gpio0', definitionId: 'def.gpio', name: 'gpio0', position: { x: 810, y: 610 }, parameterValues: {} }
    ],
    connections: [
      conn('conn-clk-cpu', 'clock', 'clock0', 'clk_out', 'cpu0', 'clk'),
      conn('conn-clk-bus', 'clock', 'clock0', 'clk_out', 'bus0', 'clk'),
      conn('conn-clk-ram', 'clock', 'clock0', 'clk_out', 'ram0', 'clk'),
      conn('conn-clk-uart', 'clock', 'clock0', 'clk_out', 'uart0', 'clk'),
      conn('conn-clk-spi', 'clock', 'clock0', 'clk_out', 'spi0', 'clk'),
      conn('conn-clk-gpio', 'clock', 'clock0', 'clk_out', 'gpio0', 'clk'),
      conn('conn-reset-cpu', 'reset', 'reset0', 'rst_out', 'cpu0', 'rst'),
      conn('conn-reset-bus', 'reset', 'reset0', 'rst_out', 'bus0', 'rst'),
      conn('conn-reset-uart', 'reset', 'reset0', 'rst_out', 'uart0', 'rst'),
      conn('conn-reset-spi', 'reset', 'reset0', 'rst_out', 'spi0', 'rst'),
      conn('conn-reset-gpio', 'reset', 'reset0', 'rst_out', 'gpio0', 'rst'),
      conn('conn-cpu-bus', 'bus', 'cpu0', 'mem', 'bus0', 's0'),
      conn('conn-bus-ram', 'bus', 'bus0', 'm0', 'ram0', 'mem'),
      conn('conn-bus-uart', 'bus', 'bus0', 'm1', 'uart0', 'bus'),
      conn('conn-bus-spi', 'bus', 'bus0', 'm2', 'spi0', 'bus')
    ]
  }]
};
