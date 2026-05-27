import { spawn } from 'node:child_process';
import { unlinkSync, writeFileSync } from 'node:fs';
import type { IncomingMessage } from 'node:http';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

export function readBody(req: IncomingMessage): Promise<string> {
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

export function spawnCli(
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
