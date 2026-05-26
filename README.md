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
| `manifest` | Output graph manifest/metadata with high-level summary |
| `chunks` | Output LLM vector chunks |
| `diff` | Compare two Schema State Dictionaries or migration directories |
| `graph` | Graph representation (DOT, Mermaid, Excalidraw, Draw.io, JSON, HTML, report) |
| `graph-migrations` | Visualize migration timeline and dependency graph |
| `rollback-analysis` | Analyze migration rollback feasibility and generate rollback scripts |
| `insights` | Analyse schema and report findings (orphan tables, missing PKs, etc.) |
| `health` | Generate migration folder health report with quality score |
| `simulate` | Simulate schema evolution with hypothetical migrations |
| `integrity` | Check migration file integrity using SHA256 hashes |
| `cache` | Manage file-based caching system |
| `ask` | Ask a natural language question about the schema (RAG) |
| `chat` | Interactive multi-turn schema chat session |
| `export` | Export schema as self-contained HTML documentation |
| `query` | Deterministic graph queries (no LLM) |
| `impact` | Analyze impact of schema object changes using graph traversal |

#### `sqlfy dump`

```bash
sqlfy dump <migrations-dir> [--format json|yaml|summary] [--at VERSION] [--out FILE]
sqlfy dump --json-input FILE  [--format json|yaml|summary] [--out FILE]
```

Output the Schema State Dictionary — a clean, versioned, serializable snapshot of the final DB state including tables, columns, constraints, indexes, sequences, relationships, and migration history.

| Flag | Default | Description |
|---|---|---|
| `migrations_dir` | — | Directory containing Flyway `V*__*.sql` files |
| `--json-input FILE` | — | JSON file `[{ filename, sql }]` (Tauri bridge) |
| `--format` | `json` | `json`, `yaml`, or `summary` (human-readable) |
| `--at VERSION` | — | Point-in-time snapshot at a specific Flyway version (e.g. `2`) |
| `--out FILE` | stdout | Write output to file |

**Examples:**
```bash
sqlfy dump ./migrations                    # JSON to stdout
sqlfy dump ./migrations --format yaml      # YAML output
sqlfy dump ./migrations --format summary   # Human-readable
sqlfy dump ./migrations --at 2             # Point-in-time at V2
sqlfy dump ./migrations --out state.json   # Write to file
```

#### `sqlfy manifest`

```bash
sqlfy manifest <migrations-dir> [--at VERSION] [--out FILE]
```

Output graph manifest/metadata with high-level summary including schema version, fingerprint, node/edge counts, dialect, migration count, generation timestamp, and SQLfy version.

#### `sqlfy chunks`

```bash
sqlfy chunks <migrations-dir> [--format json|text] [--at VERSION] [--out FILE]
```

Output LLM vector chunks from the schema. Each chunk is self-contained and embedding-ready.

**Examples:**
```bash
sqlfy chunks ./migrations                   # Human-readable chunks
sqlfy chunks ./migrations --format json     # JSON array
sqlfy chunks ./migrations --out chunks.json # Write to file
```

#### `sqlfy diff`

```bash
sqlfy diff <state-a> <state-b> [--format json|text] [--out FILE]
```

Compare two Schema State Dictionaries or migration directories. Detects added/removed/modified tables, columns, constraints, and relationships.

Both arguments accept either a `.json` state file (from `sqlfy dump`) or a migrations directory reconstructed on the fly.

**Examples:**
```bash
sqlfy diff state_v2.json state_v5.json              # Diff two state files
sqlfy diff state_v2.json state_v5.json --format json
sqlfy diff ./migrations-v1 ./migrations-v2          # Diff two directories
```

#### `sqlfy graph`

```bash
sqlfy graph <migrations-dir> [--format FORMAT] [--title TEXT] [--at VERSION] [--out FILE]
              [--output-dir PATH] [--resolution FLOAT] [--min-cohesion FLOAT] [--no-split]
```

Output a graph representation of the schema in various formats.

| Format | Description |
|---|---|
| `dot` _(default)_ | Graphviz DOT — render with `dot -Tsvg schema.dot -o schema.svg` |
| `mermaid` | Mermaid ERD — paste into GitHub Markdown or https://mermaid.live |
| `excalidraw` | Excalidraw JSON — open in excalidraw.com or VSCode extension |
| `drawio` | Draw.io XML — open in draw.io or VSCode extension |
| `summary` | Compact ASCII adjacency list — useful for LLM prompts |
| `json` | NetworkX node-link graph (graph.json) with community detection |
| `html` | Interactive vis.js visualization (graph.html) |
| `report` | Human-readable graph summary (GRAPH_REPORT.md) |
| `all` | Generate json, html, and report together |

| Flag | Description |
|---|---|
| `--output-dir PATH` | Output directory for json/html/report (default: `sqlfy-out`) |
| `--resolution FLOAT` | Community detection resolution: >1 = more communities, <1 = fewer (default: 1.0) |
| `--min-cohesion FLOAT` | Minimum cohesion score to keep a community (default: 0.1) |
| `--no-split` | Disable oversized community splitting |

**Examples:**
```bash
sqlfy graph ./migrations                              # DOT format
sqlfy graph ./migrations --format mermaid --out erd.md
sqlfy graph ./migrations --format excalidraw --out schema.json
sqlfy graph ./migrations --format drawio --out schema.drawio
sqlfy graph ./migrations --format json --output-dir ./out
sqlfy graph ./migrations --format html --output-dir ./out
sqlfy graph ./migrations --format all                 # All formats
```

#### `sqlfy graph-migrations`

```bash
sqlfy graph-migrations <migrations-dir> [--format FORMAT] [--at VERSION] [--out FILE]
```

Visualize the migration timeline and dependency graph. Shows which migrations depend on others based on DDL operations (CREATE TABLE, ALTER TABLE, CREATE VIEW, foreign keys).

| Format | Description |
|---|---|
| `timeline` _(default)_ | Text-based chronological view with dependency annotations |
| `dot` | Graphviz DOT format — render with `dot -Tsvg migrations.dot -o migrations.svg` |
| `html` | Interactive vis.js visualization with hierarchical layout |
| `json` | Machine-readable graph structure with nodes and edges |

**Dependency detection:**
- `CREATE TABLE` → no dependencies
- `ALTER TABLE` → depends on migrations that created the table
- `CREATE VIEW` → depends on tables used in the view
- `Foreign keys` → depends on referenced tables
- Transitive dependency resolution

**Examples:**
```bash
sqlfy graph-migrations ./migrations                   # Timeline view
sqlfy graph-migrations ./migrations --format dot      # Graphviz format
sqlfy graph-migrations ./migrations --format html --out migrations.html
sqlfy graph-migrations ./migrations --format json --out graph.json
```

#### `sqlfy rollback-analysis`

```bash
sqlfy rollback-analysis <migrations-dir> [--format text|json] [--generate] [--at VERSION] [--out FILE]
```

Analyze migration rollback feasibility. Determines whether each migration can be safely rolled back and generates rollback scripts where possible.

**Classifications:**
- **Reversible** — Can be undone without data loss (rare)
- **Partially reversible** — Can be undone with caveats (CREATE TABLE, ADD COLUMN)
- **Irreversible** — Cannot be undone (DROP, DELETE, UPDATE, MODIFY)

**Analysis includes:**
- Rollback difficulty score (0-100)
- Generated rollback script (for reversible operations)
- Data loss warnings
- Backup and testing recommendations

| Format | Description |
|---|---|
| `text` _(default)_ | Human-readable report with rollback scripts and warnings |
| `json` | Machine-readable JSON with summary statistics |

| Flag | Description |
|---|---|
| `--generate` | Generate rollback scripts for reversible migrations _(default: true)_ |

**Examples:**
```bash
sqlfy rollback-analysis ./migrations                  # Full analysis
sqlfy rollback-analysis ./migrations --format json    # JSON output
sqlfy rollback-analysis ./migrations --out report.txt
```

#### `sqlfy insights`

```bash
sqlfy insights <migrations-dir> [--format text|json] [--severity error|warning|info] 
               [--strict] [--at VERSION] [--out FILE]
```

Analyse the schema and report Graphify-style insights. Detects orphan tables, missing PKs, unindexed tables, missing FK candidates, unresolved FK targets, nullable PKs/FKs, circular references, wide tables, orphaned sequences, duplicate indexes, and disconnected islands. Also detects migration-specific anti-patterns like ADD NOT NULL without DEFAULT, SELECT * in views, complex triggers, and DELETE without WHERE.

| Flag | Description |
|---|---|
| `--format text` _(default)_ | Human-readable report with severity sections |
| `--format json` | Machine-readable JSON grouped by severity |
| `--severity LEVEL` | Filter output to `error`, `warning`, or `info` only |
| `--strict` | Exit with code 1 if any `error`-severity findings exist (useful in CI) |

**Finding codes:**

| Code | Severity | Category |
|---|---|---|
| `ORPHAN_TABLE` | warning | structural |
| `NO_PK` | error | structural |
| `NO_INDEXES` | info | structural |
| `WIDE_TABLE` | info | structural |
| `EMPTY_TABLE_COMMENT` | info | structural |
| `MISSING_FK_CANDIDATE` | warning | referential |
| `UNRESOLVED_FK` | error | referential |
| `NULLABLE_FK` | info | referential |
| `CIRCULAR_FK` | warning | referential |
| `NULLABLE_PK` | error | modelling |
| `VARCHAR_ID` | warning | modelling |
| `ORPHAN_SEQUENCE` | info | modelling |
| `DUPLICATE_INDEX` | warning | modelling |
| `UNIQUE_WITHOUT_INDEX` | info | modelling |
| `ISLAND` | warning | connectivity |

**Examples:**
```bash
sqlfy insights ./migrations                        # Full report
sqlfy insights ./migrations --severity error       # Errors only
sqlfy insights ./migrations --format json --out findings.json
sqlfy insights ./migrations --strict               # Exit 1 if errors found
```

#### `sqlfy health`

```bash
sqlfy health <migrations-dir> [--format text|json] [--strict] [--at VERSION] [--out FILE]
```

Generate migration folder health report with high-level summary of migration quality including safe vs unsafe migrations, irreversible operations, and health score (0-100).

| Flag | Description |
|---|---|
| `--format text` _(default)_ | Human-readable health report |
| `--format json` | Machine-readable JSON |
| `--strict` | Exit with code 1 if health score is critical |

**Examples:**
```bash
sqlfy health ./migrations                          # Health report
sqlfy health ./migrations --format json            # JSON format
sqlfy health ./migrations --strict                 # Exit 1 if critical
```

#### `sqlfy simulate`

```bash
sqlfy simulate <migrations-dir> [--sql SQL | --file PATH] [--format text|json] 
               [--diff] [--strict] [--at VERSION] [--out FILE]
```

Simulate schema evolution with hypothetical migrations. Test DDL changes before committing by applying what-if SQL on top of existing state, comparing simulated vs actual state, and validating migration safety.

| Flag | Description |
|---|---|
| `--sql SQL` | Inline SQL to simulate |
| `--file PATH` | Path to SQL file to simulate |
| `--diff` | Show diff between base and simulated state |
| `--strict` | Exit with error if simulation is unsafe |

**Examples:**
```bash
sqlfy simulate ./migrations --sql "ALTER TABLE APP.USERS ADD COLUMN EMAIL VARCHAR2(255)"
sqlfy simulate ./migrations --file ./test-migration.sql --diff
sqlfy simulate ./migrations --file ./test.sql --strict --format json
```

#### `sqlfy integrity`

```bash
sqlfy integrity <migrations-dir> [--strict] [--update-manifest]
```

Check migration file integrity using SHA256 hashes. Detect tampering or edits to migration files by comparing current file hashes against a manifest of previously recorded hashes.

| Flag | Description |
|---|---|
| `--strict` | Exit with error if modified migrations detected |
| `--update-manifest` | Accept modifications and update manifest |

**Examples:**
```bash
sqlfy integrity ./migrations                       # Check integrity
sqlfy integrity ./migrations --strict              # Exit 1 if modified
sqlfy integrity ./migrations --update-manifest     # Update after review
```

#### `sqlfy cache`

```bash
sqlfy cache <clear|info>
```

Manage the file-based caching system.

| Subcommand | Description |
|---|---|
| `clear` | Delete all cache entries |
| `info` | Show cache statistics (entry count, total size) |

**Examples:**
```bash
sqlfy cache info                                   # Show cache stats
sqlfy cache clear                                  # Clear all cache
```

#### `sqlfy ask`

```bash
sqlfy ask <migrations-dir> <question> [--format text|json] [--embed] [--api-key KEY]
          [-k N] [--no-sources] [--no-cache] [--at VERSION] [--out FILE]
```

Ask a natural language question about the schema (single question). Uses RAG to retrieve the most relevant schema chunks, then passes them as context to Claude for a grounded, accurate answer.

**Requires:** `ANTHROPIC_API_KEY` environment variable.

| Flag | Description |
|---|---|
| `question` | The question to ask (positional, can be multiple words) |
| `--embed` | Use dense vector search (Voyage AI) instead of BM25 |
| `--api-key KEY` | Override environment variable |
| `-k N` | Number of chunks to retrieve (default: 6) |
| `--no-sources` | Hide source chunk references in output |
| `--no-cache` | Skip chunk cache (rebuild from scratch) |

**Examples:**
```bash
sqlfy ask ./migrations "What tables store user data?"
sqlfy ask ./migrations "How do orders relate to users?" --format json
sqlfy ask ./migrations "Show me all foreign keys" --embed -k 10
```

#### `sqlfy chat`

```bash
sqlfy chat <migrations-dir> [--embed] [--api-key KEY] [-k N] [--at VERSION]
```

Start an interactive multi-turn chat session about the schema. Follow-up questions maintain context from previous turns. Type `exit`, `quit`, or Ctrl-C to end. Type `reset` to clear conversation history.

**Requires:** `ANTHROPIC_API_KEY` environment variable.

**Examples:**
```bash
sqlfy chat ./migrations                            # Start chat session
sqlfy chat ./migrations --embed -k 10              # With embeddings
```

#### `sqlfy export`

```bash
sqlfy export <migrations-dir> [--title TEXT] [--insights] [--at VERSION] [--out FILE]
```

Export schema as a self-contained HTML documentation file with no external dependencies. Includes searchable/filterable table list with column details, inline Mermaid ERD diagram, optional schema insights panel, migration history timeline, and dark/light mode toggle.

| Flag | Description |
|---|---|
| `--title TEXT` | Document title (default: "Schema Documentation — V{version}") |
| `--insights` | Include insights panel in the HTML output |
| `--out FILE` | Output filename (default: `schema_docs.html`) |

**Examples:**
```bash
sqlfy export ./migrations                          # Basic HTML export
sqlfy export ./migrations --insights --out docs.html
sqlfy export ./migrations --title "My Schema" --at 5
```

#### `sqlfy query`

```bash
sqlfy query <migrations-dir> <query-type> [OPTIONS] [--format text|json|csv] [--out FILE]
```

Run a deterministic graph-traversal query against the schema. No LLM, no API calls — instant results.

| Query Type | Description |
|---|---|
| `tables` | List/filter tables by pattern, schema, properties |
| `columns` | List/filter columns by name, type, flags |
| `fk-path` | Shortest FK path between two tables (BFS) |
| `refs` | Tables referencing or referenced by a table |
| `orphans` | Tables with no FK relationships |
| `islands` | Disconnected clusters of tables |
| `cycles` | Circular FK references |
| `missing-pk` | Tables without a primary key |
| `missing-fk` | Columns that look like FKs but have no constraint |
| `impact` | Tables affected by dropping a given table |
| `indexes` | List all indexes |

| Flag | Description |
|---|---|
| `--pattern REGEX` | Name regex filter |
| `--schema NAME` | Schema filter |
| `--table TABLE` | Table name (full) |
| `--type-like TYPE` | Column type substring |
| `--from-table TABLE` | fk-path: source table |
| `--to-table TABLE` | fk-path: target table |
| `--direction in\|out\|both` | refs: direction (default: both) |
| `--has-pk BOOL` | Filter by PK presence (true/false) |
| `--is-orphan BOOL` | Filter by orphan status |
| `--is-pk BOOL` | Filter columns: is primary key |
| `--is-fk BOOL` | Filter columns: is foreign key |
| `--is-unique BOOL` | Filter columns: is unique |
| `--nullable BOOL` | Filter columns: is nullable |
| `--has-default BOOL` | Filter columns: has default |
| `--min-cols N` | Min column count |
| `--max-cols N` | Max column count |
| `--created-in VER` | Filter by created version |
| `--unique-only` | indexes: unique only |

**Examples:**
```bash
# Tables
sqlfy query ./migrations tables                     # All tables
sqlfy query ./migrations tables --pattern "order"   # Name match
sqlfy query ./migrations tables --has-pk false      # No PK
sqlfy query ./migrations tables --is-orphan true    # Orphan tables

# Columns
sqlfy query ./migrations columns --type-like VARCHAR
sqlfy query ./migrations columns --is-fk true --nullable false

# FK path
sqlfy query ./migrations fk-path --from-table APP.ORDER_ITEMS --to-table APP.USERS

# References
sqlfy query ./migrations refs --table APP.USERS --direction out

# Analysis
sqlfy query ./migrations orphans                    # Orphan tables
sqlfy query ./migrations islands                    # Disconnected clusters
sqlfy query ./migrations cycles                     # Circular FKs
sqlfy query ./migrations missing-pk                 # No PK
sqlfy query ./migrations impact --table APP.USERS   # Drop impact

# Indexes
sqlfy query ./migrations indexes --table APP.ORDERS
sqlfy query ./migrations indexes --unique-only
```

#### `sqlfy impact`

```bash
sqlfy impact <migrations-dir> <object-id> [--depth N] [--direction in|out] 
             [--format text|json] [--at VERSION] [--out FILE]
```

Analyze impact of changes to a schema object using graph traversal. Finds all objects (tables, views, columns, etc.) that would be affected by changes to the specified object. Supports direct dependencies (depth 1), transitive dependencies (depth > 1), critical path identification, and grouping by object type.

| Flag | Description |
|---|---|
| `object-id` | Schema object to analyze (e.g., APP.USERS, APP.USERS.EMAIL) |
| `--depth N` | Maximum traversal depth (default: 5) |
| `--direction in\|out` | Traversal direction: out=affected by, in=depends on (default: out) |

**Examples:**
```bash
sqlfy impact ./migrations APP.USERS                 # Impact of USER table
sqlfy impact ./migrations APP.USERS.EMAIL --depth 3
sqlfy impact ./migrations APP.ORDERS --direction in --format json
```

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
# ──────────────────────────────────────────────────────────────
# Schema State & Metadata
# ──────────────────────────────────────────────────────────────

# Schema State Dictionary (JSON)
sqlfy dump ./migrations
sqlfy dump ./migrations --format yaml              # YAML output
sqlfy dump ./migrations --format summary           # Human-readable
sqlfy dump ./migrations --at 2                     # Point-in-time at V2
sqlfy dump ./migrations --out state.json           # Write to file

# Schema manifest
sqlfy manifest ./migrations                        # Metadata summary

# ──────────────────────────────────────────────────────────────
# LLM Chunks & Export
# ──────────────────────────────────────────────────────────────

# LLM vector chunks
sqlfy chunks ./migrations
sqlfy chunks ./migrations --format json --out chunks.json

# HTML documentation
sqlfy export ./migrations --insights --out docs.html

# ──────────────────────────────────────────────────────────────
# Schema Analysis
# ──────────────────────────────────────────────────────────────

# Schema insights
sqlfy insights ./migrations
sqlfy insights ./migrations --severity error       # Errors only
sqlfy insights ./migrations --format json --out findings.json
sqlfy insights ./migrations --strict               # Exit 1 if errors

# Health report
sqlfy health ./migrations
sqlfy health ./migrations --strict --format json

# ──────────────────────────────────────────────────────────────
# Comparison & Impact
# ──────────────────────────────────────────────────────────────

# Diff two state files
sqlfy diff state_v2.json state_v5.json
sqlfy diff state_v2.json state_v5.json --format json

# Diff two directories
sqlfy diff ./migrations-v1 ./migrations-v2

# Impact analysis
sqlfy impact ./migrations APP.USERS
sqlfy impact ./migrations APP.USERS.EMAIL --depth 3

# ──────────────────────────────────────────────────────────────
# Graph Visualization
# ──────────────────────────────────────────────────────────────

# Graph output
sqlfy graph ./migrations                           # DOT format
sqlfy graph ./migrations --format mermaid --out schema.md
sqlfy graph ./migrations --format excalidraw --out schema.json
sqlfy graph ./migrations --format drawio --out schema.drawio
sqlfy graph ./migrations --format json --output-dir ./out
sqlfy graph ./migrations --format html --output-dir ./out
sqlfy graph ./migrations --format all              # All formats

# ──────────────────────────────────────────────────────────────
# Structured Queries (no LLM)
# ──────────────────────────────────────────────────────────────

# Query tables
sqlfy query ./migrations tables --pattern "order"
sqlfy query ./migrations tables --has-pk false

# Query columns
sqlfy query ./migrations columns --type-like VARCHAR --is-fk true

# FK path
sqlfy query ./migrations fk-path --from-table APP.ORDER_ITEMS --to-table APP.USERS

# Query analysis
sqlfy query ./migrations orphans                   # Orphan tables
sqlfy query ./migrations islands                   # Disconnected clusters
sqlfy query ./migrations cycles                    # Circular FKs
sqlfy query ./migrations missing-pk                # Tables without PK

# ──────────────────────────────────────────────────────────────
# Schema Evolution & Safety
# ──────────────────────────────────────────────────────────────

# Simulate changes
sqlfy simulate ./migrations --sql "ALTER TABLE APP.USERS ADD COLUMN EMAIL VARCHAR2(255)"
sqlfy simulate ./migrations --file ./test-migration.sql --diff

# Check integrity
sqlfy integrity ./migrations
sqlfy integrity ./migrations --strict

# ──────────────────────────────────────────────────────────────
# Natural Language (RAG)
# ──────────────────────────────────────────────────────────────

# Ask questions
sqlfy ask ./migrations "What tables store user data?"
sqlfy ask ./migrations "How do orders relate to users?" --embed

# Interactive chat
sqlfy chat ./migrations
sqlfy chat ./migrations --embed -k 10

# ──────────────────────────────────────────────────────────────
# Cache Management
# ──────────────────────────────────────────────────────────────

sqlfy cache info                                   # Show cache stats
sqlfy cache clear                                  # Clear all cache

# ──────────────────────────────────────────────────────────────
# Legacy Mode (backward compatible)
# ──────────────────────────────────────────────────────────────

sqlfy ./migrations --all                           # Combined graph + chunks
sqlfy --json-input /tmp/sqlfy-input.json --all     # From JSON input
```

---

## CLI Features Overview

### 🔍 Schema Analysis & Insights
- **Schema State Dictionary**: Versioned, serializable snapshot of final DB state (JSON/YAML/human-readable)
- **Insights Engine**: Detects 15+ schema anti-patterns (missing PKs, orphan tables, circular FKs, etc.)
- **Health Reports**: Migration quality scoring (0-100) with safe/unsafe operation counts
- **Impact Analysis**: Graph traversal to find all objects affected by schema changes
- **Integrity Checks**: SHA256-based tamper detection for migration files

### 📊 Graph & Visualization
- **Multiple Export Formats**: DOT (Graphviz), Mermaid, Excalidraw, Draw.io, JSON, HTML
- **Community Detection**: Louvain algorithm for automatic table clustering
- **Interactive HTML**: Vis.js-powered visualization with zoom/pan/search
- **Self-Contained Reports**: Single-file HTML documentation with no external dependencies

### 🔎 Query & Search
- **Deterministic Queries**: 11 query types (tables, columns, FK paths, orphans, islands, cycles, etc.)
- **No LLM Required**: Instant graph traversal results
- **Multiple Output Formats**: Text, JSON, CSV
- **Rich Filtering**: Pattern matching, type filtering, property-based selection

### 🤖 Natural Language (RAG)
- **Single-Shot Q&A**: Ask questions about your schema with `sqlfy ask`
- **Interactive Chat**: Multi-turn conversations with `sqlfy chat`
- **Hybrid Retrieval**: BM25 (local, no API key) or dense embeddings (Voyage AI via Anthropic)
- **Source Attribution**: See which schema chunks were used to answer each question

### 🛠️ Schema Evolution & Safety
- **What-If Simulator**: Test hypothetical migrations before applying
- **Schema Diff**: Compare two states or migration directories
- **Point-in-Time**: Reconstruct schema at any migration version (`--at`)
- **Migration History**: Track all changes per table/column/constraint

### ⚡ Performance & Caching
- **File-Based Cache**: Automatic caching of parsed migration files
- **Chunk Cache**: Pre-computed LLM chunks for faster RAG queries
- **Cache Management**: `sqlfy cache info` / `sqlfy cache clear`
- **Incremental Processing**: Only re-parse changed files

### 📤 Export & Documentation
- **HTML Documentation**: Searchable, filterable schema docs with dark/light mode
- **LLM Chunks**: Pre-formatted context for embedding or direct prompting
- **Manifest Generation**: High-level metadata (version, fingerprint, stats)
- **Multiple Dialects**: Oracle (primary), PostgreSQL (planned)

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

