import type { Project } from '@ew/core';

export const CURRENT_SCHEMA_VERSION = 1;

export interface ProjectMigration {
  from: number;
  to: number;
  migrate(input: unknown): unknown;
}

export function serializeProject(project: Project): string {
  return JSON.stringify(project, null, 2);
}

export function deserializeProject(text: string, migrations: ProjectMigration[] = []): Project {
  let value: any = JSON.parse(text);
  if (!value || typeof value !== 'object') throw new Error('Project root must be an object.');
  if (!Number.isInteger(value.schemaVersion)) throw new Error('Project is missing schemaVersion.');
  while (value.schemaVersion < CURRENT_SCHEMA_VERSION) {
    const migration = migrations.find((item) => item.from === value.schemaVersion);
    if (!migration) throw new Error(`No migration registered from schema ${value.schemaVersion}.`);
    value = migration.migrate(value);
    value.schemaVersion = migration.to;
  }
  if (value.schemaVersion !== CURRENT_SCHEMA_VERSION) {
    throw new Error(`Unsupported schema version ${value.schemaVersion}; runtime supports ${CURRENT_SCHEMA_VERSION}.`);
  }
  if (!Array.isArray(value.definitions) || !Array.isArray(value.diagrams)) throw new Error('Project definitions/diagrams are invalid.');
  return value as Project;
}
