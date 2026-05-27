import { spawn } from 'node:child_process';
import { unlinkSync, writeFileSync } from 'node:fs';
import type { IncomingMessage } from 'node:http';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

import type { Plugin } from 'vite';

/** Accumulates request body chunks into a raw string. */
function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', (chunk: Buffer) => (body += chunk.toString()));
    req.on('end', () => resolve(body));
    req.on('error', reject);
  });
}

interface SpawnResult {
  stdout: string;
  stderr: string;
  code: number | null;
}

/**
 * Writes `payload` to a temp JSON file, spawns `python3` with
 * `[...headArgs, '--json-input', <tempPath>, ...tailArgs]`,
 * captures stdout/stderr, cleans up the temp file, and resolves with
 * the result.
 */
function spawnCli(
  headArgs: string[],
  payload: string,
  tailArgs: string[] = [],
): Promise<SpawnResult> {
  return new Promise((resolve) => {
    const tmp = join(tmpdir(), `sqlfy-input-${Date.now()}.json`);
    writeFileSync(tmp, payload);

    const proc = spawn('python3', [...headArgs, '--json-input', tmp, ...tailArgs]);

    let stdout = '';
    let stderr = '';
    proc.stdout.on('data', (d: Buffer) => (stdout += d.toString()));
    proc.stderr.on('data', (d: Buffer) => (stderr += d.toString()));
    proc.on('close', (code) => {
      try {
        unlinkSync(tmp);
      } catch {
        /* best-effort */
      }
      resolve({ stdout, stderr, code });
    });
  });
}

/**
 * Dev-only Vite plugin that exposes two CLI proxy endpoints:
 * - `POST /api/sqlfy/parse` — full schema parse, returns `{ graph, chunks }`
 * - `POST /api/sqlfy/run`   — generic subcommand, returns `{ output: string }`
 *
 * Both routes write the request payload to a temp file, spawn the Python
 * CLI, and stream the response back. This lets `npm run dev` use the real
 * Python parser without needing Tauri.
 */
function sqlifyCliPlugin(): Plugin {
  return {
    name: 'sqlfy-cli',
    configureServer(server) {
      server.middlewares.use('/api/sqlfy/parse', async (req, res, next) => {
        if (req.method !== 'POST') return next();

        const body = await readBody(req);
        const { stdout, stderr, code } = await spawnCli(
          ['-m', 'sqlfy.main'],
          body,
          ['--all', '--json'],
        );

        if (code === 0) {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(stdout);
        } else {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: stderr || 'CLI process failed', code }));
        }
      });

      // Generic CLI command proxy: POST /api/sqlfy/run
      // Body: { subcommand, args, files }
      // Returns: { output: string }
      server.middlewares.use('/api/sqlfy/run', async (req, res, next) => {
        if (req.method !== 'POST') return next();

        const raw = await readBody(req);
        const { subcommand, args, files } = JSON.parse(raw) as {
          subcommand: string;
          args: string[];
          files: unknown[];
        };

        const { stdout, stderr, code } = await spawnCli(
          ['-m', 'sqlfy.main', subcommand],
          JSON.stringify(files),
          args,
        );

        if (code === 0) {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ output: stdout }));
        } else {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: stderr || 'CLI process failed', code }));
        }
      });
    },
  };
}

export default defineConfig({
  resolve: {
    tsconfigPaths: true,
  },
  plugins: [react(), sqlifyCliPlugin()],
  server: {
    fs: {
      // Allow the dev server to serve files from the repo root (parent of app/).
      // Required so import.meta.glob can resolve ../../../samples/*.sql at runtime.
      allow: ['..'],
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/config/tests/setup.ts'],
    include: ['src/**/*.unit.test.{ts,tsx}'],
  },
});
