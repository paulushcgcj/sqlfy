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
| `lint` | Lint migration SQL for quality and style using sqlfluff |
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
| `lineage` | Column-level lineage and data flow analysis |
| `domains` | Detect semantic business domains using community detection |
| `stability` | Calculate schema stability metrics and churn rates |
| `validate` | Validate migration ordering and detect issues |
| `deps` | Analyze migration dependencies and detect circular dependencies |
| `drift` | Detect schema drift between migration folders and generate repair SQL |
| `classify` | Classify migrations by semantic category (table creation, data migration, cleanup, etc.) |
| `safety` | Score migrations by safety level (SAFE / MEDIUM_RISK / HIGH_RISK / DANGEROUS) |

**Common flags available on most commands:**
- `--dialect oracle|postgres|mysql|sqlite` — SQL dialect (default: `oracle`)
- `--at VERSION` — Point-in-time snapshot at a specific Flyway version
- `--out FILE` — Write output to file instead of stdout
- `--format` — Output format (varies by command)

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
| `--dialect` | `oracle` | SQL dialect: `oracle`, `postgres`, `mysql`, `sqlite` |
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
sqlfy dump ./postgres-migrations --dialect postgres  # PostgreSQL migrations
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

#### `sqlfy provenance`

```
sqlfy provenance <migrations-dir> [--format text|json] [--record] [--out FILE] [--verify MANIFEST]
```

Collect git provenance metadata for migration files. Records per-file commit hash, author, commit date, branches containing the commit, and attempts to detect PR numbers from commit messages.

| Flag | Description |
|---|---|
| `migrations-dir` | Directory containing Flyway `V*__*.sql` files |
| `--format` | `text` (default) or `json` |
| `--record` | Write provenance manifest to disk (defaults to `<migrations-dir>/provenance.json`) |
| `--out FILE` | Write output to file instead of stdout |
| `--verify MANIFEST` | Compare current provenance to an existing manifest JSON file |

**Examples:**
```bash
sqlfy provenance ./samples --format json --out sqlfy-out/provenance-samples.json
sqlfy provenance ./nr-forest-client --record --out nr-forest-client/provenance.json
sqlfy provenance ./nr-waste-plus --verify nr-waste-plus/provenance.json
```

#### `sqlfy lint`

```bash
sqlfy lint <path> [--format text|json] [--min-score N] [--config FILE] 
           [--dialect DIALECT] [--no-recursive] [--out FILE]
```

Lint migration SQL files for quality and style using sqlfluff. Checks keyword capitalization, naming conventions, query anti-patterns (SELECT *), code formatting, and SQL best practices.

**Features:**
- 200+ built-in SQL linting rules from sqlfluff
- Support for multiple dialects (Oracle, PostgreSQL, MySQL, SQLite)
- Configurable rule severity and exclusions via `.sqlfluff` config
- Quality score (0-100) calculation per file
- CI/CD-friendly exit codes and JSON output

| Flag | Default | Description |
|---|---|---|
| `path` | — | Path to SQL file or directory to lint |
| `--format` | `text` | Output format: `text` or `json` |
| `--min-score N` | `0` | Fail if score < N (useful for CI/CD gates) |
| `--config FILE` | — | Path to `.sqlfluff` config file |
| `--dialect` | `oracle` | SQL dialect: `oracle`, `postgres`, `mysql`, `sqlite` |
| `--no-recursive` | `false` | Do not recursively scan subdirectories |
| `--out FILE` | stdout | Write output to file |
| `--fix` | `false` | Apply automatic fixes in-place (creates `.bak` backups) |

**Quality Score:**
- Starts at 100
- -10 per error violation
- -5 per warning violation
- -1 per info violation
- Minimum score is 0

**Violation Severity:**
- **Error** — Critical issues (parse errors, syntax violations)
- **Warning** — Style violations (lowercase keywords, short aliases, SELECT *)
- **Info** — Minor suggestions (whitespace, formatting)

**Configuration:**

Create a `.sqlfluff` file in your project root to customize rules:

```toml
[sqlfluff]
dialect = oracle
exclude_rules = L034,L042  # Allow SELECT *, table aliases

[sqlfluff:rules:L010]
capitalisation_policy = upper  # Enforce uppercase keywords

[sqlfluff:rules:L014]
extended_capitalisation_policy = upper
```

**Examples:**

```bash
# Preview-only lint report
sqlfy lint ./migrations --format text

# Apply automatic fixes in-place (creates .bak backup files)
sqlfy lint ./migrations --fix
```

**Examples:**

```bash
# Lint a single file
sqlfy lint migrations/V2__add_users.sql

# Lint all files in a directory
sqlfy lint migrations/

# Lint with minimum score threshold (CI/CD gate)
sqlfy lint migrations/ --min-score 80

# Lint with custom config
sqlfy lint migrations/ --config .sqlfluff

# Lint PostgreSQL migrations
sqlfy lint migrations/ --dialect postgres

# JSON output for CI/CD pipelines
sqlfy lint migrations/ --format json --min-score 80

# Non-recursive directory scan
sqlfy lint migrations/ --no-recursive
```

**CI/CD Integration:**

```yaml
# .github/workflows/migration-quality.yml
- name: Lint migrations
  run: |
    pip install sqlfluff>=3.0.0
    sqlfy lint migrations/ --format json --min-score 80
  # Fails build if any file scores < 80
```

**Notes:**
- Requires `sqlfluff>=3.0.0` (install with `pip install sqlfluff`)
- sqlfluff is an optional dependency — install only if you need linting
- sqlfluff performs static analysis only (no database connection required)
- Supports 200+ built-in rules covering SQL style, performance, and best practices

**Examples:**

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

#### `sqlfy lineage`

```bash
sqlfy lineage <migrations-dir> [TABLE.COLUMN] [--downstream|--upstream] [--unused-columns] 
              [--god-columns] [--min-refs N] [--format text|json|mermaid] [--max-depth N]
              [--at VERSION] [--out FILE]
```

Column-level lineage and data flow analysis. Traces column dependencies across tables, views, and stored procedures using SQLLineage integration.

**Modes:**
- **Analyze specific column:** `sqlfy lineage TABLE.COLUMN` — Show upstream/downstream dependencies
- **Find unused columns:** `sqlfy lineage --unused-columns` — Columns defined but never referenced
- **Find god columns:** `sqlfy lineage --god-columns --min-refs N` — Heavily referenced columns (default: 20+ refs)
- **Show overall stats:** `sqlfy lineage` — Summary of all column lineage

| Flag | Default | Description |
|---|---|---|
| `TABLE.COLUMN` | — | Column to analyze (e.g., `APP.USERS.EMAIL`) |
| `--downstream` | `true` | Show downstream dependencies (columns that depend on this one) |
| `--upstream` | `false` | Show upstream dependencies (columns this one depends on) |
| `--unused-columns` | — | Find columns that are never referenced |
| `--god-columns` | — | Find heavily referenced columns |
| `--min-refs` | `20` | Minimum reference count for god columns |
| `--format` | `text` | Output format: `text`, `json`, or `mermaid` |
| `--max-depth` | `3` | Maximum depth for Mermaid diagrams |

**Examples:**
```bash
# Analyze specific column
sqlfy lineage ./migrations APP.USERS.EMAIL --downstream
  APP.USERS.EMAIL
    → APP.USER_ORDERS.CUSTOMER_EMAIL (via JOIN on user_id)
    → APP.REPORTS.CONTACT_INFO (via CTE user_details)
  
  Downstream: 2 columns

# Find upstream dependencies
sqlfy lineage ./migrations APP.USER_ORDERS.CUSTOMER_EMAIL --upstream
  APP.USER_ORDERS.CUSTOMER_EMAIL
    ← APP.USERS.EMAIL (source via JOIN)

# Find unused columns
sqlfy lineage ./migrations --unused-columns
  Unused Columns Report
  ══════════════════════════════════════════════════════════
  
  Found 3 unused column(s):
  
    APP.USERS.LEGACY_FIELD
      Created: V2
      Status: Never referenced in views/procedures
    
    APP.PRODUCTS.DEPRECATED_SKU
      Created: V5
      Status: Never referenced in views/procedures

# Find god columns (heavily referenced)
sqlfy lineage ./migrations --god-columns --min-refs 30
  God Columns Report (min_refs=30)
  ══════════════════════════════════════════════════════════
  
  Found 2 god column(s):
  
    APP.USERS.USER_ID
      Total references: 47
      Downstream columns: 15
      Type: Primary Key
    
    APP.PRODUCTS.PRODUCT_ID
      Total references: 31
      Downstream columns: 8
      Type: Primary Key

# Generate Mermaid diagram
sqlfy lineage ./migrations APP.USERS.EMAIL --format mermaid --max-depth 5 > lineage.mmd

# JSON output for programmatic access
sqlfy lineage ./migrations APP.USERS.EMAIL --format json > lineage.json
```

**Use Cases:**
- **Column rename impact:** Identify all views/procedures that reference a column before renaming
- **Dead code detection:** Find unused columns that can be safely removed
- **Performance optimization:** Identify heavily used columns that should be indexed
- **Data flow understanding:** Trace how data flows from source tables through views and aggregations

#### `sqlfy drift`

```bash
sqlfy drift <base-migrations-dir> <target-migrations-dir> [--format text|json] 
            [--generate-migration] [--next-version N] [--description DESC] 
            [--dialect DIALECT] [--out FILE]
```

Detect schema drift between two migration folders and generate repair SQL. Compares two migration-derived schemas and identifies:
- **Missing/extra tables** — Tables present in one schema but not the other
- **Column changes** — Missing/extra columns, type mismatches, nullability differences
- **Constraint differences** — Missing/extra primary keys, foreign keys, unique constraints
- **Index differences** — Missing/extra indexes (unique or non-unique)

| Flag | Default | Description |
|---|---|---|
| `base_migrations` | — | Base migrations directory (e.g., production, main branch, V5) |
| `target_migrations` | — | Target migrations directory (e.g., development, feature branch, V10) |
| `--format` | `text` | Output format: `text` (human-readable) or `json` (programmatic) |
| `--generate-migration` | — | Generate catch-up migration file in target directory |
| `--next-version` | auto | Version number for generated migration (default: auto-detect from target) |
| `--description` | `catch_up_drift` | Description for generated migration file |
| `--dialect` | `oracle` | SQL dialect: `oracle`, `postgres`, `mysql`, `sqlite` |
| `--out` | stdout | Write output to file |

**Drift Categories:**
- `missing_table` — Table exists in base but not in target (severity: error)
- `extra_table` — Table exists in target but not in base (severity: warning)
- `missing_column` — Column exists in base but not in target (severity: error)
- `extra_column` — Column exists in target but not in base (severity: warning)
- `type_mismatch` — Column type differs between base and target (severity: error)
- `nullability_mismatch` — Column nullability differs (severity: warning)
- `missing_constraint` — Constraint exists in base but not in target (severity: warning)
- `extra_constraint` — Constraint exists in target but not in base (severity: info)
- `missing_index` — Index exists in base but not in target (severity: info)
- `extra_index` — Index exists in target but not in base (severity: info)

**Examples:**
```bash
# Compare dev vs production migrations
sqlfy drift migrations-prod/ migrations-dev/
  Schema Drift Report
  ══════════════════════════════════════════════════════════
  
  Base:   migrations-prod
  Target: migrations-dev
  
  Status: DRIFT DETECTED
  Total findings: 5
  
  By Category:
    missing_table      : 1
    extra_column       : 2
    type_mismatch      : 2
  
  By Severity:
    error   : 3
    warning : 2
  
  ─────────────────────────────────────────────────────────
  
  MISSING TABLES (1)
  
    [ERROR] APP.AUDIT_LOG
      Expected: Exists (created in V3)
      Actual:   Does not exist
      
      Repair SQL:
        CREATE TABLE APP.AUDIT_LOG (
          LOG_ID NUMBER PRIMARY KEY,
          TABLE_NAME VARCHAR2(100),
          RECORD_ID NUMBER,
          ACTION VARCHAR2(20),
          CHANGED_BY VARCHAR2(100),
          CHANGED_AT TIMESTAMP
        );

# Generate catch-up migration
sqlfy drift migrations-prod/ migrations-dev/ --generate-migration
  ✓ Generated migrations-dev/V10__catch_up_drift.sql

# Compare with custom version
sqlfy drift migrations-prod/ migrations-dev/ --generate-migration --next-version 15
  ✓ Generated migrations-dev/V15__catch_up_drift.sql

# JSON output for programmatic access
sqlfy drift migrations-prod/ migrations-dev/ --format json > drift.json
  {
    "status": "drift_detected",
    "base_label": "migrations-prod",
    "target_label": "migrations-dev",
    "total_findings": 5,
    "by_category": {
      "missing_table": 1,
      "extra_column": 2,
      "type_mismatch": 2
    },
    "by_severity": {
      "error": 3,
      "warning": 2
    },
    "findings": [...]
  }

# Compare branch migrations
sqlfy drift migrations-main/ migrations-feature-branch/ --generate-migration
  ✓ Generated migrations-feature-branch/V8__catch_up_drift.sql

# Write report to file
sqlfy drift migrations-v5/ migrations-v10/ --out drift-v5-to-v10.txt
```

**Use Cases:**
- **Dev vs Production:** Detect when someone made manual schema changes in production outside migrations
- **Branch Reconciliation:** Compare feature branch migrations with main branch, generate catch-up migration
- **Version Comparison:** Compare migrations at different versions (e.g., V5 vs V10) to see what changed
- **Migration Gap Detection:** Identify missing migrations when branches diverge
- **Automated Reconciliation:** Generate SQL to bring target schema in sync with base schema

**Key Advantages:**
- **No Database Connection Required** — Compares migration files directly, no credentials needed
- **Branch-Safe** — Compare any two migration folders (dev/prod, main/feature, v5/v10)
- **Automatic Repair SQL** — Every finding includes SQL to fix the drift
- **Deterministic** — Same inputs always produce same drift report
- **CI/CD Ready** — JSON output for automation, exit code 1 if drift detected

#### `sqlfy domains`

```bash
sqlfy domains <migrations-dir> [--format text|json] [--resolution FLOAT] 
              [--min-cohesion FLOAT] [--no-split] [--at VERSION] [--out FILE]
```

Detect semantic business domains in the schema using community detection algorithms (Leiden/Louvain). Automatically clusters tables into domains based on:
- **Dependency density** — Tables frequently referencing each other
- **Naming patterns** — Common prefixes (e.g., `order_`, `user_`)
- **Cross-domain dependencies** — Strength classification (weak/medium/strong)

| Flag | Description |
|---|---|
| `--resolution FLOAT` | Community detection resolution: >1 = more communities, <1 = fewer (default: 1.0) |
| `--min-cohesion FLOAT` | Minimum cohesion score to keep a domain (default: 0.1) |
| `--no-split` | Disable oversized domain splitting |

**Outputs:**
- List of domains with table membership
- Domain cohesion scores (0.0-1.0)
- Cross-domain dependencies with strength classification
- Semantic labels inferred from table names

**Use cases:**
- **Architecture review** — Ensure domains are properly separated
- **Microservice extraction** — Identify schema boundaries for splitting
- **Documentation** — Auto-generate domain documentation

**Examples:**
```bash
sqlfy domains ./migrations                         # Detect domains
sqlfy domains ./migrations --format json           # JSON output
sqlfy domains ./migrations --resolution 1.5        # More granular domains
sqlfy domains ./migrations --min-cohesion 0.5      # Filter weak domains
```

**Example output:**
```
╔══════════════════════════════════════════╗
║     SEMANTIC DOMAIN DETECTION            ║
╚══════════════════════════════════════════╝

Algorithm: louvain
Total tables: 15
Domains detected: 3


━━━ User Management Domain (cohesion: 0.85) ━━━
  Tables (5):
    • APP.USERS
    • APP.USER_PROFILES
    • APP.USER_ROLES
    • APP.USER_SESSIONS
    • APP.USER_PREFERENCES
  Description: Domain containing 5 related tables

━━━ Order Processing Domain (cohesion: 0.72) ━━━
  Tables (6):
    • APP.ORDERS
    • APP.ORDER_ITEMS
    • APP.ORDER_HISTORY
    • APP.SHIPPING
    • APP.INVOICES
    • APP.PAYMENTS
  Description: Domain containing 6 related tables


╔══════════════════════════════════════════╗
║     CROSS-DOMAIN DEPENDENCIES            ║
╚══════════════════════════════════════════╝

● Order Processing → User Management (strong: 12 FKs)
◐ Order Processing → Product Catalog (medium: 6 FKs)
○ Product Catalog → User Management (weak: 2 FKs)
```

#### `sqlfy stability`

```bash
sqlfy stability <migrations-dir> [--format text|json] [--show-all]
                [--high-churn-threshold FLOAT] [--stable-threshold FLOAT]
                [--at VERSION] [--out FILE]
```

Calculate schema stability metrics and churn rates to identify unstable tables requiring refactoring. Analyzes how frequently tables change across migrations.

| Flag | Description |
|---|---|
| `--show-all` | Show all tables in text output (default: only high-churn and stable) |
| `--high-churn-threshold FLOAT` | Churn rate threshold for high-churn classification (default: 20.0%) |
| `--stable-threshold FLOAT` | Churn rate threshold for stable classification (default: 10.0%) |

**Metrics:**
- **Churn rate** — Percentage of migrations affecting each table (0-100%)
- **Stability score** — Inverse of churn, 0-100 scale (higher is better)
- **Volatility** — Standard deviation of modification counts across tables
- **Letter grade** — Overall assessment (A=Excellent, F=Critical)

**Outputs:**
- Overall stability score with letter grade
- High-churn tables (>=20% churn) — candidates for refactoring
- Stable tables (<10% churn) — well-designed tables
- Modification count per table
- Versions where each table was modified

**Use cases:**
- **Identify unstable tables** — Find tables modified too frequently
- **Architecture assessment** — Measure schema design quality
- **Refactoring prioritization** — Focus on high-churn areas
- **Team velocity tracking** — Monitor schema change rate

**Examples:**
```bash
sqlfy stability ./migrations                       # Stability report
sqlfy stability ./migrations --format json         # JSON output
sqlfy stability ./migrations --show-all            # Include all tables
sqlfy stability ./migrations --high-churn-threshold 15.0  # Lower threshold
```

**Example output:**
```
╔══════════════════════════════════════════╗
║     SCHEMA STABILITY METRICS             ║
╚══════════════════════════════════════════╝

Overall:
  Total migrations: 50
  Stability score: 68/100
  Volatility (std dev): 2.34

  Grade: C (Fair)


High Churn Tables (4):
  (Tables with churn rate >= 20%)

  • APP.USERS
      18 modifications
      36.0% churn rate
      Stability score: 28/100
      Modified in versions: 3, 7, 12, 15, 18, 22, 25...

  • APP.ORDERS
      12 modifications
      24.0% churn rate
      Stability score: 52/100


Stable Tables (12):
  (Tables with churn rate < 10%)

  • APP.PRODUCTS
      3 modifications
      6.0% churn rate
      Stability score: 88/100

  • APP.CATEGORIES
      2 modifications
      4.0% churn rate
      Stability score: 92/100
```

#### `sqlfy validate`

```bash
sqlfy validate <migrations-dir> [--format text|json] [--strict] [--fix-numbering] [--out FILE]
```

Validate migration folder structure and ordering to prevent deployment failures. Detects out-of-order migrations, version gaps, duplicate versions, and invalid filename formats.

| Flag | Description |
|---|---|
| `--strict` | Exit with code 1 on warnings (not just errors) — recommended for CI/CD |
| `--fix-numbering` | Show renumbering suggestions to fix ordering issues |

**Detection Categories:**

1. **Out-of-Order Migrations** (Error)  
   Filename sort differs from version sort (e.g., V10__aaa.sql before V2__zzz.sql alphabetically)

2. **Duplicate Versions** (Error)  
   Two or more files with the same version number (e.g., two V5 files)

3. **Version Gaps** (Warning)  
   Missing sequential versions in simple sequences (e.g., V1, V2, V5 — missing V3, V4)  
   _Note:_ Only detected for simple integer versions, not dotted versions (1.2.3)

4. **Invalid Filename Format** (Warning)  
   File doesn't match Flyway naming standard (V<version>__<description>.sql)

**Supported Filename Formats:**
- `V1__description.sql` — Simple versioned migration
- `V1.2.3__description.sql` — Dotted version
- `V1_2_3__description.sql` — Underscore version (converted to dots)
- `R__repeatable.sql` — Repeatable migration
- `U1__undo.sql` — Undo migration

**Exit Codes:**
- `0` — No issues (or warnings in non-strict mode)
- `1` — Errors found (or warnings in strict mode)

**Use Cases:**
- **CI/CD Gate** — Prevent deployment of misconfigured migrations
- **Pre-commit Hook** — Catch ordering issues before push
- **Team Onboarding** — Validate migration folder structure
- **Migration Refactoring** — Detect issues after reorganization

**Examples:**
```bash
sqlfy validate ./migrations                        # Basic validation
sqlfy validate ./migrations --strict               # Treat warnings as errors
sqlfy validate ./migrations --fix-numbering        # Show renumbering suggestions
sqlfy validate ./migrations --format json          # JSON output for automation
sqlfy validate ./migrations --out validation.json  # Write to file
```

**Example Output (with issues):**
```
╔══════════════════════════════════════════╗
║   MIGRATION ORDERING VALIDATION          ║
╚══════════════════════════════════════════╝

Total migrations: 15

❌ 1 error(s):

  [OUT_OF_ORDER] Migrations are not in version order by filename
    File: V10__add_email_index.sql
    → Expected V2__add_orders.sql at position 2, found V10__add_email_index.sql

⚠  2 warning(s):

  [VERSION_GAP] Gap in version sequence: V2 → V10
    → Missing versions: V3, V4, V5, V6, V7, V8, V9

  [INVALID_FILENAME] Non-standard migration filename (not Flyway format)
    File: create_users.sql
    → Use Flyway format: V<version>__<description>.sql
```

**Example with `--fix-numbering`:**
```
📋 Renumbering suggestions:
  V10__add_email_index.sql → V3__add_email_index.sql
  V15__add_foreign_keys.sql → V4__add_foreign_keys.sql
```

**Example Output (no issues):**
```
╔══════════════════════════════════════════╗
║   MIGRATION ORDERING VALIDATION          ║
╚══════════════════════════════════════════╝

Total migrations: 20

✓ All migrations validated successfully
```

**CI/CD Integration Example (GitHub Actions):**
```yaml
- name: Validate Migration Order
  run: sqlfy validate ./migrations --strict
```

**Pre-commit Hook Example:**
```bash
#!/bin/bash
sqlfy validate ./migrations --strict || {
  echo "Migration validation failed. Run 'sqlfy validate ./migrations --fix-numbering' for suggestions."
  exit 1
}
```

#### `sqlfy deps`

```bash
sqlfy deps <migrations-dir> [--format text|json|dot] [--validate] [--strict] [--critical-path] [--summary-only] [--out FILE]
```

Analyze migration dependencies to detect circular dependencies, unreferenced objects, parallel-safe migrations, and the critical path. Uses NetworkX graph analysis to validate that migrations reference objects that are actually created.

| Flag | Description |
|---|---|
| `--format text\|json\|dot` | Output format: text (default), json, or dot (Graphviz) |
| `--validate` | Show validation summary with pass/fail status |
| `--strict` | Exit with code 1 on warnings (not just errors) |
| `--critical-path` | Show longest dependency chain |
| `--summary-only` | Show only summary statistics (skip detailed dependencies) |
| `--out FILE` | Write output to file instead of stdout |

**Detection Categories:**

1. **Circular Dependencies** (Error)  
   Impossible migration order where migrations depend on each other in a cycle

2. **Unreferenced Objects** (Error)  
   Migrations reference or alter tables that are never created

3. **Isolated Migrations** (Warning)  
   Migrations with no dependencies that create no objects

**Analysis Features:**

- **Dependency Map** — Shows which migrations depend on which other migrations
- **Reverse Dependency Map** — Shows which migrations are required by others
- **Parallel-Safe Sets** — Groups migrations that can run concurrently (topological layers)
- **Critical Path** — Longest dependency chain (minimum sequential execution time)
- **Validation** — Detects unreferenced objects and circular dependencies

**Exit Codes:**
- `0` — No issues (or warnings in non-strict mode)
- `1` — Errors found (or warnings in strict mode)

**Use Cases:**
- **CI/CD Gate** — Prevent deployment of migrations with dependency errors
- **Optimization** — Identify migrations that can run in parallel
- **Debugging** — Understand why migrations are failing at runtime
- **Documentation** — Generate dependency graphs for team reference

**Examples:**
```bash
# Basic dependency analysis
sqlfy deps ./migrations

# Show validation summary
sqlfy deps ./migrations --validate

# Show critical path
sqlfy deps ./migrations --critical-path

# Export as Graphviz DOT
sqlfy deps ./migrations --format dot --out deps.dot
dot -Tsvg deps.dot -o deps.svg

# Export as JSON for automation
sqlfy deps ./migrations --format json --out deps.json

# Summary only (skip detailed dependencies)
sqlfy deps ./migrations --summary-only

# Strict mode for CI/CD
sqlfy deps ./migrations --validate --strict
```

**Example Output:**
```
Migration Dependency Analysis
==================================================

Total Migrations: 6
Total Dependencies: 5
Circular Dependencies: 0
Parallel-Safe Sets: 3
Critical Path Length: 4

Issues Found: 0 total
  ✅ No issues found

Critical Path (Longest Dependency Chain)
--------------------------------------------------
V1 → V2 → V3 → V5
(4 migrations must run sequentially)

Parallel-Safe Migration Sets
--------------------------------------------------
Layer 1: V1
Layer 2: V2, V4 (can run in parallel)
Layer 3: V3, V5 (can run in parallel)
Layer 4: V6

Migration Dependencies
--------------------------------------------------

V1__create_users.sql
  Depends on: (none)
  Required by: V2__create_profiles.sql, V3__add_foreign_key.sql

V2__create_profiles.sql
  Depends on: V1__create_users.sql
  Required by: V3__add_foreign_key.sql

...
```

**Example with Issues:**
```
Migration Dependency Analysis
==================================================

Total Migrations: 3
Total Dependencies: 0
Circular Dependencies: 0
Parallel-Safe Sets: 1
Critical Path Length: 1

Issues Found: 2 total
  ❌ 2 error(s)

Issues Detail
--------------------------------------------------

ERRORS:
  [UNREFERENCED_OBJECT] Migration V2 alters table ORDERS that is never created
  [UNREFERENCED_OBJECT] Migration V3 references table USERS that is never created
```

**CI/CD Integration Example (GitHub Actions):**
```yaml
- name: Validate Migration Dependencies
  run: sqlfy deps ./migrations --validate --strict
```

#### `sqlfy safety`

```bash
sqlfy safety <migrations-dir> [--format text|json] [--threshold LEVEL] [--verbose] [--out FILE]
```

Score each migration by its worst-case SQL operation risk level.

| Flag | Description |
|---|---|
| `--format` | `text` (default) or `json` |
| `--threshold LEVEL` | `safe`, `medium`, `high`, `dangerous` — exit 1 if any migration is at or above this level |
| `--verbose` | Show per-statement breakdown with reason for each migration |
| `--out FILE` | Write output to file |

**Risk levels:**

| Level | Triggers |
|---|---|
| `SAFE` | CREATE TABLE/SEQUENCE, ADD nullable COLUMN, INSERT, COMMENT |
| `MEDIUM_RISK` | CREATE INDEX (non-concurrent), ADD CONSTRAINT, DROP INDEX/CONSTRAINT, RENAME |
| `HIGH_RISK` | DROP COLUMN/VIEW, ADD COLUMN NOT NULL w/o DEFAULT, MODIFY type, DELETE/UPDATE with WHERE |
| `DANGEROUS` | DROP TABLE, TRUNCATE, DELETE/UPDATE without WHERE |

**Examples:**
```bash
sqlfy safety ./migrations                          # Scored list to stdout
sqlfy safety ./migrations --verbose                # Per-statement breakdown
sqlfy safety ./migrations --threshold high         # Exit 1 on HIGH_RISK or DANGEROUS
sqlfy safety ./migrations --format json            # JSON output for CI/CD
sqlfy safety ./migrations --threshold dangerous    # Exit 1 only on DANGEROUS
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

# Build complete knowledge graph (unified graphify-style output)
sqlfy build-graph ./migrations                     # Creates graphify-out/ directory
sqlfy build-graph ./migrations --output-dir ./out
sqlfy build-graph ./migrations --at V5             # Graph at specific version
sqlfy build-graph ./migrations --no-queries        # Skip pre-computed queries
sqlfy build-graph ./migrations --no-viz            # Skip viz formats
sqlfy build-graph ./migrations --min-refs 10       # God node threshold

# Graph output (individual formats)
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

# Safety scoring
sqlfy safety ./migrations
sqlfy safety ./migrations --verbose
sqlfy safety ./migrations --threshold high         # Exit 1 if HIGH_RISK or DANGEROUS
sqlfy safety ./migrations --format json

# Classify migrations by semantic category
sqlfy classify ./migrations
sqlfy classify ./migrations --category data_migration
sqlfy classify ./migrations --format json

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
- **Unified Graph Builder**: `sqlfy build-graph` — One command to generate complete graphify-out/ directory with all graph features orchestrated
- **Multiple Export Formats**: DOT (Graphviz), Mermaid, Excalidraw, Draw.io, JSON, HTML
- **Community Detection**: Leiden/Louvain algorithm for automatic table clustering into business domains
- **Interactive HTML**: Vis.js-powered visualization with zoom/pan/search
- **Self-Contained Reports**: Single-file HTML documentation with no external dependencies
- **Pre-computed Queries**: Orphans, cycles, islands, missing PK/FK analysis in JSON format
- **God Nodes & Columns**: Automatically identify highly-connected tables and frequently-referenced columns

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

