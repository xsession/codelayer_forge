import type {
  ComponentDefinition,
  EndpointRef,
  Project,
  DiagramId,
  PortDefinition,
  ValidationIssue
} from '@ew/core';

export interface EndpointDescriptor {
  ref: EndpointRef;
  port: PortDefinition;
  definition: ComponentDefinition;
  instanceName: string;
}

export type CompatibilityStatus =
  | 'compatible'
  | 'compatible-warning'
  | 'requires-adapter'
  | 'incompatible';

export interface CompatibilityResult {
  status: CompatibilityStatus;
  message?: string;
  connectionType?: string;
}

export interface ConnectionContext {
  project: Project;
  diagramId: DiagramId;
}

export interface CompatibilityProvider {
  id: string;
  priority?: number;
  evaluate(
    source: EndpointDescriptor,
    target: EndpointDescriptor,
    context: ConnectionContext
  ): CompatibilityResult | undefined;
}

export interface Validator {
  id: string;
  validate(project: Project, diagramId: DiagramId): ValidationIssue[];
}

export interface EngineeringPlugin {
  id: string;
  name: string;
  version: string;
  definitions?: ComponentDefinition[];
  compatibilityProviders?: CompatibilityProvider[];
  validators?: Validator[];
}

export interface PluginRegistry {
  plugins: EngineeringPlugin[];
  definitions: ComponentDefinition[];
  compatibilityProviders: CompatibilityProvider[];
  validators: Validator[];
}

export function createPluginRegistry(plugins: EngineeringPlugin[]): PluginRegistry {
  return {
    plugins,
    definitions: plugins.flatMap((plugin) => plugin.definitions ?? []),
    compatibilityProviders: plugins
      .flatMap((plugin) => plugin.compatibilityProviders ?? [])
      .sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0)),
    validators: plugins.flatMap((plugin) => plugin.validators ?? [])
  };
}

export interface ImportSource {
  name?: string;
  text: string;
  mediaType?: string;
}

export interface ImportResult {
  project?: Project;
  definitions?: ComponentDefinition[];
  diagnostics?: string[];
}

export interface Importer {
  id: string;
  label: string;
  canImport(source: ImportSource): boolean | Promise<boolean>;
  import(source: ImportSource): ImportResult | Promise<ImportResult>;
}

export interface ExportResult {
  fileName: string;
  mediaType: string;
  text: string;
}

export interface Exporter {
  id: string;
  label: string;
  export(project: Project, diagramId?: DiagramId): ExportResult | Promise<ExportResult>;
}

export interface Generator {
  id: string;
  label: string;
  generate(project: Project, diagramId: DiagramId): ExportResult | Promise<ExportResult>;
}
