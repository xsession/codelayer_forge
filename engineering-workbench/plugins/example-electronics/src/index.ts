import type { ComponentDefinition, Project, ValidationIssue } from '@ew/core';
import type {
  CompatibilityProvider,
  EngineeringPlugin,
  EndpointDescriptor,
  Validator
} from '@ew/plugin-api';

const port = (
  id: string,
  name: string,
  direction: 'input' | 'output' | 'inout',
  kind: string,
  width = 1,
  required = false,
  protocol?: string
) => ({
  id,
  name,
  direction,
  required,
  cardinality: direction === 'output' && (kind === 'clock' || kind === 'reset') ? 'multiple' as const : 'single' as const,
  dataType: { kind, width, protocol }
});

export const electronicsDefinitions: ComponentDefinition[] = [
  {
    id: 'def.clock', type: 'clock-source', namespace: 'demo', name: 'Clock Generator', version: '1.0',
    category: 'Infrastructure', description: 'Configurable system clock source.', visual: { icon: 'clock', minWidth: 220 },
    ports: [port('clk_out', 'clk_out', 'output', 'clock', 1, true)],
    parameters: [{ id: 'frequency', name: 'Frequency', type: 'number', defaultValue: 100, unit: 'MHz' }]
  },
  {
    id: 'def.reset', type: 'reset-source', namespace: 'demo', name: 'Reset Controller', version: '1.0',
    category: 'Infrastructure', description: 'System reset distribution.', visual: { icon: 'rotate-ccw', minWidth: 220 },
    ports: [port('rst_out', 'reset_n', 'output', 'reset', 1, true)]
  },
  {
    id: 'def.cpu', type: 'processor', namespace: 'demo', name: 'RV32 CPU', version: '1.2',
    category: 'Processing', description: 'Example 32-bit processor with a generic memory master.', visual: { icon: 'cpu', minWidth: 245 },
    ports: [
      port('clk', 'clk', 'input', 'clock', 1, true),
      port('rst', 'reset_n', 'input', 'reset', 1, true),
      port('mem', 'MEM_M', 'output', 'bus', 32, true, 'demo-mem'),
      port('irq', 'irq', 'input', 'signal', 1, false)
    ],
    parameters: [
      { id: 'freq', name: 'Clock frequency', type: 'number', defaultValue: 100, unit: 'MHz' },
      { id: 'debug', name: 'Debug enabled', type: 'boolean', defaultValue: true }
    ]
  },
  {
    id: 'def.bus', type: 'interconnect', namespace: 'demo', name: 'Memory Interconnect', version: '1.0',
    category: 'Interconnect', description: 'One-master, multi-target address/data interconnect.', visual: { icon: 'git-branch', minWidth: 250 },
    ports: [
      port('clk', 'clk', 'input', 'clock', 1, true),
      port('rst', 'reset_n', 'input', 'reset', 1, true),
      port('s0', 'S0', 'input', 'bus', 32, true, 'demo-mem'),
      port('m0', 'M0', 'output', 'bus', 32, true, 'demo-mem'),
      port('m1', 'M1', 'output', 'bus', 32, false, 'demo-mem'),
      port('m2', 'M2', 'output', 'bus', 32, false, 'demo-mem')
    ]
  },
  {
    id: 'def.ram', type: 'memory', namespace: 'demo', name: 'On-Chip RAM', version: '1.0',
    category: 'Memory', description: 'Generic memory target.', visual: { icon: 'memory-stick', minWidth: 230 },
    ports: [
      port('clk', 'clk', 'input', 'clock', 1, true),
      port('mem', 'MEM_S', 'input', 'bus', 32, true, 'demo-mem')
    ],
    parameters: [{ id: 'size', name: 'Size', type: 'number', defaultValue: 128, unit: 'KiB' }]
  },
  {
    id: 'def.uart', type: 'peripheral', namespace: 'demo', name: 'UART', version: '2.0',
    category: 'Peripherals', description: 'Memory-mapped UART peripheral.', visual: { icon: 'terminal', minWidth: 230 },
    ports: [
      port('clk', 'clk', 'input', 'clock', 1, true),
      port('rst', 'reset_n', 'input', 'reset', 1, true),
      port('bus', 'BUS_S', 'input', 'bus', 32, true, 'demo-mem'),
      port('tx', 'tx', 'output', 'signal'),
      port('rx', 'rx', 'input', 'signal'),
      port('irq', 'irq', 'output', 'signal')
    ]
  },
  {
    id: 'def.spi', type: 'peripheral', namespace: 'demo', name: 'SPI Controller', version: '1.0',
    category: 'Peripherals', description: 'Memory-mapped SPI controller.', visual: { icon: 'radio', minWidth: 230 },
    ports: [
      port('clk', 'clk', 'input', 'clock', 1, true),
      port('rst', 'reset_n', 'input', 'reset', 1, true),
      port('bus', 'BUS_S', 'input', 'bus', 32, true, 'demo-mem'),
      port('sck', 'sck', 'output', 'signal'),
      port('mosi', 'mosi', 'output', 'signal'),
      port('miso', 'miso', 'input', 'signal')
    ]
  },
  {
    id: 'def.gpio', type: 'peripheral', namespace: 'demo', name: 'GPIO Bank', version: '1.0',
    category: 'Peripherals', description: 'Memory-mapped general purpose I/O.', visual: { icon: 'grid-3x3', minWidth: 230 },
    ports: [
      port('clk', 'clk', 'input', 'clock', 1, true),
      port('rst', 'reset_n', 'input', 'reset', 1, true),
      port('bus', 'BUS_S', 'input', 'bus', 32, true, 'demo-mem'),
      port('gpio', 'gpio[15:0]', 'inout', 'signal', 16)
    ]
  }
];

const genericCompatibility: CompatibilityProvider = {
  id: 'demo.generic-compatibility',
  priority: 100,
  evaluate(source: EndpointDescriptor, target: EndpointDescriptor) {
    const s = source.port;
    const t = target.port;
    const sourceLike = s.direction === 'output' || s.direction === 'inout';
    const targetLike = t.direction === 'input' || t.direction === 'inout';
    if (!sourceLike || !targetLike) {
      return { status: 'incompatible', message: `${s.direction} cannot drive ${t.direction}.` };
    }
    if (s.dataType?.kind !== t.dataType?.kind) {
      return { status: 'incompatible', message: `${s.dataType?.kind ?? 'unknown'} cannot connect to ${t.dataType?.kind ?? 'unknown'}.` };
    }
    if (s.dataType?.protocol && t.dataType?.protocol && s.dataType.protocol !== t.dataType.protocol) {
      return { status: 'incompatible', message: `Protocol mismatch: ${s.dataType.protocol} vs ${t.dataType.protocol}.` };
    }
    if (s.dataType?.width !== t.dataType?.width) {
      return {
        status: 'compatible-warning',
        message: `Width mismatch ${s.dataType?.width ?? '?'} → ${t.dataType?.width ?? '?'}.`,
        connectionType: s.dataType?.kind ?? 'signal'
      };
    }
    return {
      status: 'compatible',
      connectionType: s.dataType?.kind === 'bus' ? 'bus' : s.dataType?.kind ?? 'signal'
    };
  }
};

const uniqueNameValidator: Validator = {
  id: 'demo.unique-instance-name',
  validate(project: Project, diagramId: string): ValidationIssue[] {
    const diagram = project.diagrams.find((item) => item.id === diagramId);
    if (!diagram) return [];
    const seen = new Map<string, string>();
    const issues: ValidationIssue[] = [];
    for (const instance of diagram.instances) {
      const prior = seen.get(instance.name);
      if (prior) {
        issues.push({
          id: `duplicate-name:${instance.id}`,
          severity: 'error', code: 'E200',
          message: `Duplicate instance name: ${instance.name}.`,
          objectRef: { kind: 'instance', id: instance.id },
          relatedObjects: [{ kind: 'instance', id: prior }]
        });
      } else seen.set(instance.name, instance.id);
    }
    return issues;
  }
};

export const exampleElectronicsPlugin: EngineeringPlugin = {
  id: 'example.electronics',
  name: 'Example Electronics',
  version: '0.1.0',
  definitions: electronicsDefinitions,
  compatibilityProviders: [genericCompatibility],
  validators: [uniqueNameValidator]
};
