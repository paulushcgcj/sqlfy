import type { MigrationFile } from '@/core/types';

// Load .sql files from the shared samples/ folder at the repo root.
// Vite resolves this glob statically at build time.
const rawModules = import.meta.glob('../../../samples/*.sql', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

export const SAMPLE_MIGRATIONS: MigrationFile[] = Object.entries(rawModules)
  .map(([filePath, sql]) => ({
    filename: filePath.split('/').at(-1) ?? filePath,
    sql,
  }))
  .sort((a, b) => a.filename.localeCompare(b.filename));
