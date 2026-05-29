// AUTO-GENERATED — do not edit. Re-run: node schema/codegen.mjs
// schema/codegen.mjs
// Generates app/src/core/types.ts from schema/types.json using json-schema-to-typescript.

import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';

// Resolve json-schema-to-typescript from app/node_modules so the script works
// when invoked from any cwd (e.g. repo root via `make codegen-ts`).
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const appDir = resolve(__dirname, '..', 'app');
const require = createRequire(resolve(appDir, 'package.json'));
const { compile } = require('json-schema-to-typescript');

const schemaPath = resolve(__dirname, 'types.json');
const outPath = resolve(appDir, 'src', 'core', 'types.ts');

const schema = JSON.parse(readFileSync(schemaPath, 'utf8'));

const opts = {
  additionalProperties: false,
  unreachableDefinitions: true,
  unknownAny: false,
  format: false,
  bannerComment: '',
};

const raw = await compile(schema, 'SQLfyTypes', opts);

const banner = [
  '// AUTO-GENERATED — do not edit by hand.',
  '// Source of truth: schema/types.json',
  '// Regenerate with: cd app && npm run codegen',
  '',
].join('\n');

// Drop the useless root SQLfyTypes interface (empty catch-all) that the generator emits.
const cleaned = raw.replace(/\/\*[\s\S]*?\*\/\nexport interface SQLfyTypes \{[\s\S]*?\}\n?/, '');

// Append re-export of app-internal types so all existing @/core/types imports keep working.
const footer = '\n// App-internal types (not CLI JSON output) — hand-written in local-types.ts\nexport * from \'./local-types\';\n';

writeFileSync(outPath, banner + cleaned + footer, 'utf8');
console.log(`✓  Generated TypeScript types → ${outPath}`);
