# SQLfy

**Schema Graph Engine** — Parse Flyway migrations into an AST, reconstruct your database schema state, and export LLM-ready vector context.

```
Flyway SQL files  →  sqlglot AST  →  Reconstructor  →  Schema Graph / SchemaState  →  LLM Chunks
```

---

## Overview

SQLfy reads a set of Flyway migration files in version order, parses each DDL statement into an abstract syntax tree, and reconstructs the **final state** of your database schema. From that state it produces:

- An interactive **ERD** showing tables and foreign-key relationships
- A structured **table explorer** with columns, types, constraints, indexes, and comments
- Pre-formatted **LLM context chunks** ready to be embedded into a RAG pipeline or pasted into a prompt

Primary target dialect is **OracleDB**. PostgreSQL support is planned.

---

## Repository Structure

```
sqlfy/
├── app/          React + Vite + Tauri desktop UI
├── cli/          Python CLI (pip-installable)
│   ├── src/sqlfy/
│   │   ├── core.py          Schema graph engine (data types, chunk builder, layout)
│   │   ├── reconstructor.py Stateful migration processor (incremental, point-in-time)
│   │   ├── schema_state.py  SchemaState dictionary — serialisable, LLM-ready snapshot
│   │   └── main.py          argparse CLI entry point
│   ├── tests/               pytest suite (140+ tests)
│   └── pyproject.toml
└── samples/      Shared Flyway .sql fixtures (Oracle DDL — used by app and test suite)
```

---

## Quick Start

### Desktop app

```bash
cd app
npm install
npm run dev          # Vite dev server (browser)
npx tauri dev        # Tauri desktop window
```

The app is pre-loaded with the sample Oracle schema from `samples/`. Replace the SQL with your own Flyway files, or add files with **+ Add Migration File**, then click **▶ Parse →**.

### CLI

```bash
cd cli
pip install .        # install
sqlfy ./samples      # human-readable schema summary
```

---

## CLI Reference

### Subcommand style (preferred)

| Subcommand | Description |
|---|---|
| `dump` | Output the Schema State Dictionary (JSON, YAML, or human-readable summary) |
| `chunks` | Output LLM vector chunks |
| `diff` | Compare two Schema State Dictionaries or migration directories |
| `graph` | Graph representation _(coming soon)_ |

#### `sqlfy dump`

```bash
sqlfy dump <migrations-dir> [--format json|yaml|summary] [--at VERSION] [--out FILE]
sqlfy dump --json-input FILE  [--format json|yaml|summary] [--out FILE]
```

| Flag | Default | Description |
|---|---|---|
| `migrations_dir` | — | Directory containing Flyway `V*__*.sql` files |
| `--json-input FILE` | — | JSON file `[{ filename, sql }]` (Tauri bridge) |
| `--format` | `json` | `json`, `yaml`, or `summary` (human-readable) |
| `--at VERSION` | — | Point-in-time snapshot at a specific Flyway version (e.g. `2`) |
| `--out FILE` | stdout | Write output to file |

#### `sqlfy chunks`

```bash
sqlfy chunks <migrations-dir> [--format json|text] [--at VERSION] [--out FILE]
```

#### `sqlfy diff`

```bash
sqlfy diff <state-a> <state-b> [--format json|text] [--out FILE]
```

Both arguments accept either a `.json` state file (from `sqlfy dump`) or a migrations directory reconstructed on the fly.

#### `sqlfy graph`

```bash
sqlfy graph <migrations-dir> [--format dot|mermaid|summary] [--title TEXT] [--at VERSION] [--out FILE]
```

| Format | Description |
|---|---|
| `dot` _(default)_ | Graphviz DOT — render with `dot -Tsvg schema.dot -o schema.svg` |
| `mermaid` | Mermaid ERD — paste into GitHub Markdown or https://mermaid.live |
| `summary` | Compact ASCII adjacency list — useful for LLM prompts |

### Legacy style (backward compatible)

```bash
sqlfy [migrations_dir] [--json-input FILE] [--json] [--chunks] [--all] [--at VERSION] [--out FILE]
```

| Flag | Output |
|---|---|
| _(default)_ | Human-readable schema summary |
| `--json` | JSON schema graph |
| `--chunks` | LLM vector chunks (human-readable) |
| `--chunks --json` | LLM vector chunks (JSON array) |
| `--all` | Combined `{ graph, chunks }` JSON — implies `--json` |

### Examples

```bash
# Schema State Dictionary (JSON)
sqlfy dump ./migrations

# YAML output
sqlfy dump ./migrations --format yaml

# Human-readable summary
sqlfy dump ./migrations --format summary

# Point-in-time snapshot at V2
sqlfy dump ./migrations --at 2

# Write to file
sqlfy dump ./migrations --out state.json

# LLM vector chunks
sqlfy chunks ./migrations
sqlfy chunks ./migrations --out chunks.json

# Diff two pre-built state files
sqlfy diff state_v2.json state_v5.json
sqlfy diff state_v2.json state_v5.json --format json

# Diff two migration directories on the fly
sqlfy diff ./migrations-v1 ./migrations-v2

# Graph output
sqlfy graph ./migrations
sqlfy graph ./migrations --format mermaid --out schema.md
sqlfy graph ./migrations --format dot --out schema.dot
sqlfy graph ./migrations --format summary

# Combined graph + chunks (Tauri bridge format — legacy)
sqlfy ./migrations --all

# From a JSON input file
sqlfy --json-input /tmp/sqlfy-input.json --all
```

---

## Development

### App

```bash
cd app
npm install
npm run dev          # Vite dev server (browser, no Tauri)
npm run build        # production Vite build
npm run lint         # ESLint
npx tauri dev        # Tauri desktop window (requires Rust + cargo)
npx tauri build      # Tauri production bundle (.app / .exe / .deb)
```

### CLI

```bash
cd cli
pip install -e ".[dev]"   # editable install + pytest
python -m pytest -v       # run all tests
python -m sqlfy ./samples # run directly without installing
```

Tests read real `.sql` files from `samples/` and validate the parser, Reconstructor, and SchemaState builder end-to-end.

### PyInstaller binary (for bundling with Tauri)

```bash
cd cli
pip install pyinstaller
pyinstaller --onefile src/sqlfy/main.py --name sqlfy
# Output: dist/sqlfy  — copy to app/src-tauri/binaries/sqlfy-<target-triple>
```

---

## How the App Uses the CLI

The desktop app (Tauri) and the browser dev mode use the CLI differently:

```
Browser dev mode:
  App (TypeScript) ──▶ app/src/core/core.ts  (in-process parser, no CLI)

Tauri desktop:
  App (TypeScript) ──▶ app/src/bridge/cli.ts
       │
       ├─ writes migrations to a temp JSON file: [{ filename, sql }]
       ├─ spawns CLI sidecar:  sqlfy --json-input <tmp> --all
       └─ parses response JSON: { graph: {...}, chunks: [...] }
```

**Detection** — `app/src/bridge/cli.ts` checks `'__TAURI_INTERNALS__' in window` to decide which path to use.

**CLI sidecar** — configured in `app/src-tauri/tauri.conf.json` under `externalBin`. The binary must be placed at `app/src-tauri/binaries/sqlfy-<target-triple>` before `npx tauri build`.

**Output contract** — the CLI's `--all` flag produces:

```json
{
  "graph":  { "tables": {}, "sequences": {}, "edges": [], "migration_history": [] },
  "chunks": [{ "id": "", "type": "", "title": "", "content": "", "metadata": {}, "hint": "" }]
}
```

The TypeScript deserialiser in `cli.ts` maps `snake_case` keys to `camelCase` for the React component layer.

---

## Features

### ① Migrations tab
- Add, edit, or remove SQL migration files directly in the browser
- Files are parsed in Flyway version order (`V1__`, `V2__`, …)
- Supports multi-file sequences with incremental schema changes

### ② Schema Graph tab
- **ERD canvas** — topology-aware layout showing table nodes and FK edges
- **Table detail panel** — per-table view of:
  - Columns with data type, precision/scale, nullability, default value, and inline comment
  - Constraint badges: `PK`, `NOT NULL`, `UNIQUE`, `FK`
  - Outgoing and incoming FK relationships with `ON DELETE` action
  - Indexes (including unique indexes) with version provenance
  - Check constraints
  - Migration action history per table (CREATE, ADD_COLUMN, MODIFY_COLUMN, …)
- **Sequence list** — `START WITH` / `INCREMENT BY` metadata per sequence

### ③ LLM Chunks tab
- **Schema Summary** chunk — table count, column count, FK edge count, migration history, table role classification (root / junction / leaf / standalone)
- **Per-table** chunks — full column inventory + constraint + relationship text in a structured, embedding-friendly format
- **Relationship Graph** chunk — adjacency list of all FK edges for JOIN-path planning
- One-click copy per chunk

---

## Supported DDL

| Statement | Support |
|---|---|
| `CREATE TABLE` | ✅ columns, PK, FK, UNIQUE, CHECK |
| `ALTER TABLE … ADD COLUMN` | ✅ |
| `ALTER TABLE … ADD CONSTRAINT` | ✅ |
| `ALTER TABLE … DROP COLUMN` | ✅ |
| `ALTER TABLE … DROP CONSTRAINT` | ✅ |
| `ALTER TABLE … MODIFY` | ✅ type, precision/scale, default, nullability |
| `ALTER TABLE … RENAME COLUMN` | ✅ |
| `CREATE [UNIQUE] INDEX` | ✅ |
| `DROP TABLE` | ✅ |
| `DROP INDEX` | ✅ |
| `CREATE SEQUENCE` | ✅ |
| `DROP SEQUENCE` | ✅ |
| `COMMENT ON TABLE / COLUMN` | ✅ |

---

## LLM Usage

Each chunk is self-contained and human-readable. Example table chunk:

```
TABLE: APP.ORDERS
Schema: APP | Created: V2

COLUMNS:
  ORDER_ID: NUMBER(10) [PK, NOT NULL]
  USER_ID: NUMBER(10) [NOT NULL, FK]
  TOTAL_AMOUNT: NUMBER(12,2) [NOT NULL]
  STATUS: VARCHAR2(20) [NOT NULL, DEFAULT PENDING]
  CREATED_AT: TIMESTAMP [NOT NULL, DEFAULT SYSTIMESTAMP]

REFERENCES (outgoing FK):
  USER_ID) → APP.USERS(USER_ID) ON DELETE CASCADE [FK_ORDERS_USER]

REFERENCED BY:
  APP.ORDER_ITEMS.ORDER_ID → ORDER_ID

INDEXES:
  IDX_ORDERS_USER: (USER_ID) [V2]
  IDX_ORDERS_STATUS: (STATUS, CREATED_AT) [V2]

MIGRATION ACTIONS:
  V2: CREATE TABLE APP.ORDERS
```

Paste the **Schema Summary** chunk as system context and individual **table chunks** as retrieval results for precise, grounded SQL generation.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Desktop UI | React 19 + Vite + Tauri 2 |
| CLI | Python 3.11+ with sqlglot ≥25 (Oracle AST) |
| Distribution | PyInstaller binary + Tauri desktop bundle |
| Tests | pytest 9 |

---

## Roadmap

- [x] Split into `app/` (React/Vite/Tauri) and `cli/` (Python)
- [x] Shared `samples/` fixtures used by both the app and the test suite
- [x] Migrate parser to **sqlglot** for full Oracle AST fidelity
- [x] `DROP TABLE`, `DROP COLUMN`, `DROP CONSTRAINT`, `MODIFY COLUMN`, `RENAME COLUMN` support
- [x] `SchemaState` dictionary — versioned, serialisable, fingerprinted snapshot
- [x] YAML export of SchemaState (`sqlfy dump --format yaml`)
- [x] Point-in-time reconstruction via `--at`
- [x] Schema diff command (`sqlfy diff`)
- [x] Graph output command (`sqlfy graph` — DOT, Mermaid, ASCII summary)
- [ ] PostgreSQL dialect parity

---

## License

MIT

