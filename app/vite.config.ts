import { spawn } from 'node:child_process';
import { unlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

import type { Plugin } from 'vite';

/**
 * Dev-only Vite plugin that exposes `POST /api/sqlfy/parse`.
 *
 * Accepts a `MigrationFile[]` JSON body, writes it to a temp file,
 * spawns the Python CLI (`cli/src/sqlfy/main.py`), and streams the
 * `{ graph, chunks }` JSON response back to the browser. This lets
 * `npm run dev` use the real Python parser without needing Tauri.
 */
function sqlifyCliPlugin(): Plugin {
  return {
    name: 'sqlfy-cli',
    configureServer(server) {
      server.middlewares.use('/api/sqlfy/parse', (req, res, next) => {
        if (req.method !== 'POST') return next();

        let body = '';
        req.on('data', (chunk: Buffer) => (body += chunk.toString()));
        req.on('end', () => {
          const tmp = join(tmpdir(), `sqlfy-input-${Date.now()}.json`);
          writeFileSync(tmp, body);

          const proc = spawn('python3', [
            '-m',
            'sqlfy.main',
            '--json-input',
            tmp,
            '--all',
            '--json',
          ]);

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
            if (code === 0) {
              res.writeHead(200, { 'Content-Type': 'application/json' });
              res.end(stdout);
            } else {
              res.writeHead(500, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: stderr || 'CLI process failed', code }));
            }
          });
        });
      });

      // Generic CLI command proxy: POST /api/sqlfy/run
      // Body: { subcommand, args, files }
      // Returns: { output: string }
      server.middlewares.use('/api/sqlfy/run', (req, res, next) => {
        if (req.method !== 'POST') return next();

        let body = '';
        req.on('data', (chunk: Buffer) => (body += chunk.toString()));
        req.on('end', () => {
          const { subcommand, args, files } = JSON.parse(body) as {
            subcommand: string;
            args: string[];
            files: unknown[];
          };

          const tmp = join(tmpdir(), `sqlfy-input-${Date.now()}.json`);
          writeFileSync(tmp, JSON.stringify(files));

          const proc = spawn('python3', [
            '-m',
            'sqlfy.main',
            subcommand,
            '--json-input',
            tmp,
            ...args,
          ]);

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
            if (code === 0) {
              res.writeHead(200, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ output: stdout }));
            } else {
              res.writeHead(500, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: stderr || 'CLI process failed', code }));
            }
          });
        });
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
