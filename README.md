# SQLfy

**Schema Graph Engine** — Parse Flyway migrations into an AST, reconstruct your database schema state, and export LLM-ready vector context.

```
Flyway SQL files  →  AST Parser  →  State Reconstructor  →  Schema Graph  →  LLM Chunks
```

---

## Overview

SQLfy reads a set of Flyway migration files in version order, parses each DDL statement into an abstract syntax tree, and reconstructs the **final state** of your database schema. From that state it produces:

- An interactive **ERD** showing tables and foreign-key relationships
- A structured **table explorer** with columns, types, constraints, indexes, and comments
- Pre-formatted **LLM context chunks** ready to be embedded into a RAG pipeline or pasted into a prompt

Primary target dialect is **OracleDB**. PostgreSQL support is planned.

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
| `ALTER TABLE … ADD` | ✅ columns and constraints |
| `CREATE [UNIQUE] INDEX` | ✅ |
| `CREATE SEQUENCE` | ✅ |
| `COMMENT ON TABLE / COLUMN` | ✅ |
| `DROP TABLE` | planned |
| `ALTER TABLE … MODIFY / DROP COLUMN` | planned |

---

## Planned Architecture

The project is being split into two packages:

```
sqlfy/
├── app/      React + Vite + Tauri desktop UI
└── cli/      Python CLI (binary-distributable via PyInstaller)
```

The UI will shell out to the CLI binary rather than bundling parser logic in the frontend. The CLI will be independently usable for scripting and CI pipelines.

### Planned CLI commands

```bash
# Reconstruct schema state and print as JSON
sqlfy parse ./migrations --output json

# Visualize schema graph in the terminal
sqlfy graph ./migrations

# Compare two migration sets
sqlfy diff ./migrations-v1 ./migrations-v2

# Export LLM chunks
sqlfy chunks ./migrations --format text
```

---

## Quick Start (current single-file build)

No build step required. Open `index.html` directly in any modern browser:

```bash
open index.html
# or serve it locally
npx serve .
```

1. The **Migrations** tab is pre-loaded with a sample Oracle schema (users, products, orders, audit_log).
2. Replace the sample SQL with your own Flyway files, or add files with **+ Add Migration File**.
3. Click **▶ Parse →** to process the files.
4. Explore the **Schema Graph** and copy **LLM Chunks** as needed.

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

CHECK CONSTRAINTS:
  CK_ORDERS_STATUS: CHECK (status IN ('PENDING','PROCESSING','SHIPPED','DELIVERED','CANCELLED'))
```

Paste the **Schema Summary** chunk as system context and individual **table chunks** as retrieval results for precise, grounded SQL generation.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Current UI | Vanilla HTML/CSS/JS (single file) |
| Target UI | React 19 + Vite + Tauri |
| Target CLI | Python + sqlglot (Oracle AST) |
| Distribution | PyInstaller binary + Tauri desktop bundle |

---

## Roadmap

- [ ] Split into `app/` (React/Vite/Tauri) and `cli/` (Python)
- [ ] Migrate parser to **sqlglot** for full Oracle/PostgreSQL AST fidelity
- [ ] `DROP TABLE` and `ALTER TABLE … MODIFY/DROP COLUMN` support
- [ ] Schema diff command
- [ ] JSON / YAML export of the Schema State Dictionary
- [ ] Graph topology insights (orphan tables, missing FK targets, circular references)
- [ ] PostgreSQL dialect support

---

## License

MIT
