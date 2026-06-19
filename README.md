# SQLfy

**Schema Graph Engine** — Parse Flyway migrations into an AST, reconstruct your database schema state, and export LLM-ready vector context.

```
Flyway SQL files  →  sqlglot AST  →  Reconstructor  →  Schema Graph / SchemaState  →  LLM Chunks
```

---

## Installation

**Mac / Linux**
```bash
curl -fsSL https://raw.githubusercontent.com/paulushcgcj/sqlfy/main/install.sh | bash
```

**Windows (PowerShell)**
```powershell
irm https://raw.githubusercontent.com/paulushcgcj/sqlfy/main/install.ps1 | iex
```

> **macOS note:** If you get a security warning, run once:
> `xattr -d com.apple.quarantine /usr/local/bin/sqlfy`

---

## Overview

SQLfy reads a set of Flyway migration files in version order, parses each DDL statement into an abstract syntax tree, and reconstructs the **final state** of your database schema. From that state it produces:

- An interactive **ERD** showing tables and foreign-key relationships
- A structured **table explorer** with columns, types, constraints, indexes, and comments
- Pre-formatted **LLM context chunks** ready to be embedded into a RAG pipeline or pasted into a prompt

Primary target dialect is **OracleDB**. **PostgreSQL**, **MySQL**, and **SQLite** are also supported via the `--dialect` flag.

### Multi-Dialect Support

SQLfy supports multiple SQL dialects with automatic type normalization:

| Dialect | Invoke with | Type Normalization Examples |
|---|---|---|
| **Oracle** _(default)_ | `--dialect oracle` | `VARCHAR2` → `VARCHAR`, `NUMBER` → `NUMERIC` |
| **PostgreSQL** | `--dialect postgres` | `SERIAL` → `INTEGER`, `TEXT` → `VARCHAR` |
| **MySQL** | `--dialect mysql` | `TINYINT` → `SMALLINT`, `DATETIME` → `TIMESTAMP` |
| **SQLite** | `--dialect sqlite` | `TEXT` → `VARCHAR`, `REAL` → `FLOAT` |

**Usage:**
```bash
sqlfy dump ./postgres-migrations --dialect postgres
sqlfy graph ./mysql-migrations --dialect mysql --format mermaid
sqlfy insights ./sqlite-migrations --dialect sqlite
```

**How it works:**
- The `--dialect` flag is passed to [sqlglot](https://github.com/tobymao/sqlglot) for parsing
- Types are normalized to canonical forms (e.g., `SERIAL` → `INTEGER`, `VARCHAR2` → `VARCHAR`)
- Auto-increment columns are detected per-dialect (`SERIAL`, `AUTO_INCREMENT`, `IDENTITY`)
- Output formats work consistently across all dialects

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

## Distribution

### Automated releases (Recommended)

Every time you create a new tag, GitHub Actions automatically builds binaries for all platforms:

```bash
# Create and push a tag
git tag v0.20.0
git push origin v0.20.0
```

This triggers the build workflow which creates:
- `sqlfy-macos-arm64.zip` (macOS Apple Silicon)
- `sqlfy-linux-amd64.zip` (Linux x86_64)
- `sqlfy-windows-amd64.zip` (Windows x86_64)

Each zip contains the binary + README.md. The workflow automatically creates a GitHub Release with all files attached.

**Users download from:** `https://github.com/paulushcgcj/sqlfy/releases`

### Building a standalone binary locally

To build manually for your current platform:

```bash
cd cli
bash build-binary.sh
```

This creates `cli/dist/sqlfy-binary/sqlfy` (~35 MB) — a self-contained executable with zero dependencies.

**To share:**
1. Zip the binary: `tar -czf sqlfy-macos.tar.gz -C dist/sqlfy-binary sqlfy`
2. Send `sqlfy-macos.tar.gz` to your user
3. They extract and run: `tar -xzf sqlfy-macos.tar.gz && chmod +x sqlfy && ./sqlfy --help`

**Cross-platform:** Build on macOS → works on macOS. Build on Linux → works on Linux.

**Alternative (requires Python 3.11+):**
```bash
cd cli
python -m build                    # creates wheel
pip install dist/sqlfy-*.whl       # install from wheel
```

---

## CLI Reference

SQLfy has 31 CLI subcommands covering schema reconstruction, graph visualization, impact analysis, linting, drift detection, domain analysis, RAG Q&A, and more.

See the [full command reference on the wiki](https://github.com/paulushcgcj/sqlfy.wiki/wiki/commands/) for documentation on every command, including usage, flags, and examples.

### Quick reference

| Subcommand | Description |
|---|---|
| `dump` | Output the Schema State Dictionary |
| `manifest` | Output graph manifest/metadata with high-level summary |
| `chunks` | Output LLM vector chunks |
| `diff` | Compare two Schema State Dictionaries or migration directories |
| `diff-versions` | Compare two version snapshots from the same migration set |
| `graph` | Graph representation (DOT, Mermaid, Excalidraw, Draw.io, JSON, HTML, report) |
| `graph-migrations` | Visualize migration timeline and dependency graph |
| `build-graph` | Build complete graphify-out/ directory (unified all-in-one) |
| `rollback-analysis` | Analyze migration rollback feasibility and generate rollback scripts |
| `lint` | Lint migration SQL for quality and style using sqlfluff |
| `insights` | Analyse schema and report findings (orphan tables, missing PKs, etc.) |
| `health` | Generate migration folder health report with quality score |
| `simulate` | Simulate schema evolution with hypothetical migrations |
| `integrity` | Check migration file integrity using SHA256 hashes |
| `provenance` | Collect git provenance for migration files |
| `cache` | Manage file-based caching system |
| `ask` | Ask a natural language question about the schema (RAG) |
| `chat` | Interactive multi-turn schema chat session |
| `export` | Export schema as self-contained HTML documentation |
| `query` | Deterministic graph queries (no LLM) |
| `impact` | Analyze impact of schema object changes using graph traversal |
| `lineage` | Column-level lineage and data flow analysis |
| `domains` | Detect semantic business domains using community detection |
| `stability` | Calculate schema stability metrics and churn rates |
| `validate` | Validate migration ordering and detect issues |
| `deps` | Analyze migration dependencies and detect circular dependencies |
| `drift` | Detect schema drift between migration folders and generate repair SQL |
| `classify` | Classify migrations by semantic category (table creation, data migration, cleanup, etc.) |
| `naming` | Enforce migration filename naming conventions (Flyway pattern, description format) |
| `cost` | Estimate migration execution cost (score, category, estimated_seconds) |
| `safety` | Score migrations by safety level (SAFE / MEDIUM_RISK / HIGH_RISK / DANGEROUS) |

**Common flags available on most commands:**
- `--dialect oracle|postgres|mysql|sqlite` — SQL dialect (default: `oracle`)
- `--at VERSION` — Point-in-time snapshot at a specific Flyway version
- `--out FILE` — Write output to file instead of stdout
- `--format` — Output format (varies by command)


> Use `sqlfy <subcommand> --help` for detailed usage.

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
### ④ Ask tab
- Natural-language Q&A against your schema using RAG (Retrieval-Augmented Generation)
- Choose retrieval strategy: local BM25 (no keys) or dense embeddings (requires API key)
- Shows source chunks and provenance for transparency and reproducibility
- Useful for quick schema discovery: "Which tables lack a PRIMARY KEY?", "How do orders join to customers?"

### ⑤ Schema tab
- Table explorer and compact schema panel with per-table details:
  - Columns with data type, nullability, defaults, and inline comments
  - Constraint, index, and FK badges with provenance
  - Migration history for the selected table (CREATE / ALTER operations)
- Includes a lightweight "Run insights" action to analyse the current schema from this panel

### ⑥ Insights tab
- Dedicated schema quality analysis panel powered by the `sqlfy insights` engine:
  - Health score (0–100) and grade (A–D)
  - Severity filter (Error / Warning / Info), category dropdown, and keyword search
  - Expandable finding cards with full detail and suggested fix or SQL
  - CLI-required: runs the Python CLI (`sqlfy insights --format json`) via Tauri or the dev-server proxy
  - Browser-only mode shows a clear "CLI required" message and documentation on how to enable the CLI

### ⑦ Graph Export tab
- Export the schema graph to multiple formats: Mermaid, DOT, Excalidraw, Draw.io, JSON, HTML, or a human-readable summary
- Advanced options: diagram title, layout resolution, `--no-split` subgraph behavior, and point-in-time `--at` version
- Uses the CLI sidecar in Tauri or the dev-server proxy; browser fallback produces a limited in-process Mermaid/DOT rendering

### ⑧ Simulate tab
- Test hypothetical DDL changes against the current schema without modifying any files
- Enter any SQL statement (DDL), optionally specify a base migration version (`--at`), and run a sandboxed simulation
- Results show: safety badge (✓ Safe / ✕ Unsafe), breaking-change flag, health score, schema diff stats (tables/columns/sequences/relationships added or removed), and collapsible warnings list
- Requires CLI (Tauri or Vite dev server) — not available in pure-browser mode

---
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

> [!IMPORTANT]
> **Vector embeddings require an API key.**
> The `ask` and `chat` subcommands support a `--embed` flag that switches from
> BM25 retrieval to dense vector search using [Voyage AI](https://voyageai.com)
> (model `voyage-3`, accessed via the Anthropic API).
> Set `ANTHROPIC_API_KEY` in your environment before using `--embed`.
> Without the flag, all retrieval is local BM25 — no key needed.
>
> TODO: evaluate whether to replace with a local embedding model (e.g. `nomic-embed-text`
> via Ollama) to remove the external dependency entirely.

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
- [x] Graph output command (`sqlfy graph` — DOT, Mermaid, Excalidraw, Draw.io, JSON, HTML, report)
- [x] Schema insights (`sqlfy insights` — orphan tables, missing PKs, FK candidates, circular refs, islands)
- [x] Health report (`sqlfy health` — migration quality score)
- [x] Schema simulator (`sqlfy simulate` — test what-if migrations)
- [x] Migration integrity checks (`sqlfy integrity` — SHA256 hashing)
- [x] File-based caching (`sqlfy cache`)
- [x] Natural language queries (`sqlfy ask` — single-shot RAG)
- [x] Interactive chat (`sqlfy chat` — multi-turn conversations)
- [x] HTML documentation export (`sqlfy export`)
- [x] Deterministic graph queries (`sqlfy query` — tables, columns, fk-path, refs, orphans, islands, cycles, missing-pk, indexes)
- [x] Impact analysis (`sqlfy impact` — graph traversal for change impact)
- [x] Manifest generation (`sqlfy manifest` — metadata summary)
- [x] Community detection in graph exports (NetworkX + Louvain algorithm)
- [ ] PostgreSQL dialect parity
- [ ] Vector embeddings: evaluate replacing Voyage AI (`ANTHROPIC_API_KEY`) with a local model (e.g. Ollama `nomic-embed-text`) — see LLM Usage note above

---

## License

MIT

