# SQLfy — Project Context for Claude Code

## Workspace layout

```
sqlfy/
├── app/                        React 19 + Vite 8 + Tauri 2 desktop app
│   ├── src/
│   │   ├── main.tsx            Entry point. Imports ./index.scss → @use './styles/index'
│   │   ├── App.tsx             Root component
│   │   ├── bridge/             Tauri IPC + CLI bridge (folder.ts, cli.ts)
│   │   ├── components/
│   │   │   ├── core/           Reusable UI: ErdCanvas, ForceErd, TableDetail
│   │   │   └── schema/         Feature tabs: GraphTab, LlmTab, MigrationsTab, AskPanel
│   │   ├── core/               Pure business logic: core.ts, types.ts
│   │   ├── data/               Static sample data (samples.ts)
│   │   └── styles/             SCSS design system
│   │       ├── _tokens.scss    Single source of truth — SASS map theme switching
│   │       ├── index.scss      Barrel: @use each partial
│   │       └── _*.scss         Partials: _reset, _base, _layout, _topbar, _tabs,
│   │                                      _sidebar, _badges, _utilities
│   ├── vite.config.ts
│   ├── tsconfig.app.json       Defines @/ alias → src/
│   └── package.json
│
└── cli/                        Python CLI (sqlglot-based migration parser)
    ├── src/sqlfy/              src layout — package is `sqlfy`
    │   ├── main.py             Entry point: sqlfy = "sqlfy.main:main"
    │   ├── core.py             applyMigrations, buildChunks, computeLayout
    │   ├── schema_state.py     Schema state machine
    │   ├── reconstructor.py    SQL reconstructor
    │   ├── differ.py           Migration differ
    │   ├── grapher.py          Graph builder
    │   ├── insights.py         Schema insights
    │   ├── asker.py            LLM prompt builder
    │   ├── exporter.py         HTML schema exporter
    │   └── retriever.py        Vector chunk retriever
    └── pyproject.toml
```

---

## App — TypeScript import rules

**Rule: ALL imports inside `app/src/` use the `@/` alias. No relative `../` paths.**

```ts
// ✅ correct
import type { SchemaGraph } from '@/core/types';
import { buildChunks }      from '@/core/core';
import ForceErd             from '@/components/core/ForceErd';
import TableDetail          from '@/components/core/TableDetail';
import { writeFile }        from '@/bridge/folder';

// ❌ wrong — never use relative paths
import type { SchemaGraph } from '../../../core/types';
import ForceErd             from '../../core/ForceErd';
```

The alias `@/` resolves to `app/src/` and is configured in both `tsconfig.app.json` (paths) and `vite.config.ts` (tsconfigPaths: true), so it works in source and test files alike.

---

## App — Component conventions

Every component lives in its own folder with three co-located files:

```
components/core/ForceErd/
├── index.tsx       Component implementation
├── index.scss      Component styles (or a comment if none needed)
└── index.unit.test.tsx
```

Component template:

```tsx
import { type FC } from 'react';
import type { SchemaGraph } from '@/core/types';
import './index.scss';

export interface MyComponentProps {
  readonly graph: SchemaGraph;
  readonly onSelect: (key: string) => void;
}

const MyComponent: FC<MyComponentProps> = ({ graph, onSelect }) => {
  return <div />;
};

export default MyComponent;
```

Key rules:
- Props interface: `readonly` on all fields, named `<ComponentName>Props`
- Arrow function assigned to `const`, annotated `FC<Props>`
- `export default ComponentName;` — default export
- Never `window` directly — use `globalThis`
- `@/` for all imports, never relative

---

## App — Design system / SCSS

All design tokens live in `app/src/styles/_tokens.scss`.

Theme switching: dark by default (`:root`), light via `[data-theme="light"]` on `<html>`.

**CSS custom properties** (use `var(--xx)` in JSX inline styles and SCSS):

| Token       | CSS var         | Dark      | Light     |
|-------------|-----------------|-----------|-----------|
| Background  | `--bg`          | `#0f172a` | `#f8f7ff` |
| Card surface| `--bg-card`     | `#1e2235` | `#ffffff` |
| Header tint | `--bg-header`   | `#1a1040` | `#f3f0ff` |
| Primary text| `--text`        | `#f1f5f9` | `#111827` |
| Secondary   | `--text-2`      | `#94a3b8` | `#4b5563` |
| Tertiary    | `--text-3`      | `#64748b` | `#9ca3af` |
| Border      | `--border`      | rgba white 10% | rgba black 12% |
| Sub-border  | `--border-sub`  | rgba white 5%  | rgba black 6%  |
| Accent      | `--accent`      | `#7c3aed` (invariant) |
| Error       | `--error`       | `#dc2626` (invariant) |
| Warning     | `--warn`        | `#d97706` (invariant) |
| Success/UQ  | `--ok`          | `#059669` (invariant) |
| FK/cyan     | `--fk`          | `#0891b2` (invariant) |

SCSS partials use `@use 'tokens' as *` and reference SCSS variables (`$space-8`, `$radius-md`, `$fs-body`, etc.) for compile-time values. CSS custom properties are used for theme-variant values.

---

## CLI — Python import rules

**Rule: ALL imports between `sqlfy` modules MUST be relative.**

```python
# ✅ correct — relative imports
from .core         import apply_migrations, build_chunks
from .schema_state import SchemaState
from .differ       import diff_schemas
from .exporter     import Exporter

# ❌ wrong — absolute package imports break in src layout
from sqlfy.core    import apply_migrations
```

**After any change to the CLI source, reinstall:**

```bash
cd cli && pip3 install .
```

The CLI is installed as a regular package (NOT editable/`-e`). The `sqlfy` command in the Tauri app calls the installed binary. If you skip reinstall, the running binary will use stale code.

Entry point: `sqlfy = "sqlfy.main:main"` (defined in `pyproject.toml`).
