import { describe, it, expect, vi } from 'vitest';

import { dumpWithOptions, dump, dumpYaml, dumpSummary } from './cli';

import type { MigrationFile } from '@/core/types';

// Mock the Tauri plugins
vi.mock('@tauri-apps/plugin-shell', () => ({
  Command: {
    create: vi.fn(),
    sidecar: vi.fn(),
  },
}));

vi.mock('@tauri-apps/plugin-fs', () => ({
  writeTextFile: vi.fn(),
  remove: vi.fn(),
}));

vi.mock('@tauri-apps/api/path', () => ({
  tempDir: vi.fn(() => Promise.resolve('/tmp')),
  join: vi.fn((...args: string[]) => Promise.resolve(args.join('/'))),
}));

const mockFiles: MigrationFile[] = [
  { filename: 'V1__create_users.sql', sql: 'CREATE TABLE users (id NUMBER PRIMARY KEY);' },
  { filename: 'V2__add_email.sql', sql: 'ALTER TABLE users ADD email VARCHAR2(255);' },
];

describe('CLI Bridge', () => {
  describe('dumpWithOptions', () => {
    it('should call runCliCommand with format argument', async () => {
      // Mock fetch for dev server path
      globalThis.fetch = vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ output: '{}' }),
        } as Response),
      );

      const result = await dumpWithOptions(mockFiles, { format: 'json' });
      expect(result).toBeDefined();
    });

    it('should include --at version when specified', async () => {
      // Mock fetch for dev server path
      globalThis.fetch = vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ output: '{}' }),
        } as Response),
      );

      const result = await dumpWithOptions(mockFiles, { format: 'json', atVersion: 5 });
      expect(result).toBeDefined();
    });

    it('should support yaml format', async () => {
      globalThis.fetch = vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ output: 'version: "1"' }),
        } as Response),
      );

      const result = await dumpWithOptions(mockFiles, { format: 'yaml' });
      expect(result).toBeDefined();
    });

    it('should support summary format', async () => {
      globalThis.fetch = vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ output: 'Schema Summary' }),
        } as Response),
      );

      const result = await dumpWithOptions(mockFiles, { format: 'summary' });
      expect(result).toBeDefined();
    });
  });

  describe('dump (legacy shortcut)', () => {
    it('should default to JSON format', async () => {
      globalThis.fetch = vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ output: '{"version":"1"}' }),
        } as Response),
      );

      const result = await dump(mockFiles);
      expect(result).toBeDefined();
      expect(result).toContain('{');
    });
  });

  describe('dumpYaml', () => {
    it('should request YAML format', async () => {
      globalThis.fetch = vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ output: 'version: "1"' }),
        } as Response),
      );

      const result = await dumpYaml(mockFiles);
      expect(result).toBeDefined();
    });
  });

  describe('dumpSummary', () => {
    it('should request summary format', async () => {
      globalThis.fetch = vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ output: 'Schema Summary' }),
        } as Response),
      );

      const result = await dumpSummary(mockFiles);
      expect(result).toBeDefined();
    });
  });

  describe('error handling', () => {
    it('should throw error when CLI fails', async () => {
      globalThis.fetch = vi.fn(() =>
        Promise.resolve({
          ok: false,
          json: () => Promise.resolve({ error: 'CLI error' }),
        } as Response),
      );

      await expect(dumpWithOptions(mockFiles, { format: 'json' })).rejects.toThrow();
    });

    it('should throw error when dev server is unreachable', async () => {
      globalThis.fetch = vi.fn(() => Promise.reject(new Error('Network error')));

      await expect(dumpWithOptions(mockFiles, { format: 'json' })).rejects.toThrow();
    });
  });
});
