# Impact Analysis

## Overview

The `impact` command analyzes the transitive blast radius of schema object
changes. It uses BFS traversal over the schema dependency graph to discover
all objects (tables, columns, etc.) that would be directly or transitively
affected by a change to one or more source objects.

## Usage

```bash
sqlfy impact <migrations-dir> [OBJECT_ID]          \
             [--table TABLE] ...                    \
             [--from-diff [GIT_REF]]                \
             [--depth N]                            \
             [--direction in|out]                   \
             [--format text|json]                   \
             [--at VERSION]                         \
             [--out FILE]                           \
             [--dialect DIALECT]
```

## Flags

| Flag | Description |
|------|-------------|
| `migrations-dir` | Path to directory containing migration `.sql` files |
| `OBJECT_ID` | (Positional, optional with `--from-diff`) Schema object to analyze, e.g. `APP.USERS` |
| `--table TABLE` | Repeatable; additional table(s) to include in analysis |
| `--from-diff` | Read git diff to discover changed tables automatically. Optional `GIT_REF` (default: staged changes) |
| `--depth N` | Maximum BFS traversal depth (default: 5) |
| `--direction in\|out` | Traversal direction: `out` (downstream impact, default) or `in` (upstream dependencies) |
| `--format text\|json` | Output format (default: text) |
| `--at VERSION` | Reconstruct schema at a specific migration version |
| `--out FILE` | Write output to file instead of stdout |
| `--dialect DIALECT` | SQL dialect (default: oracle) |

## How `--from-diff` Works

1. **Git diff**: Runs `git diff --name-only <REF> HEAD` (or `git diff --cached --name-only`
   if no ref given) to list changed files.
2. **Filter**: Keeps only `.sql` files inside `<migrations-dir>`.
3. **Extract**: Parses each changed `.sql` file with `sqlglot`, walks the AST for
   `CREATE TABLE`, `ALTER TABLE`, and `DROP TABLE` statements, and collects table names.
4. **Merge**: Combines the extracted tables with any explicitly provided `--table` arguments.
5. **Analyze**: Runs impact analysis on each table using BFS graph traversal.
6. **Report**: Merges all individual results into a single consolidated report.

## Output Formats

### Text Output (Default)

```
Changed by diff (HEAD~1..HEAD):
  migrations/V12__add_order_status.sql
    → ORDER_STATUS_CODE (CREATE TABLE)
    → ORDER_HEADER (ALTER TABLE)

Downstream impact:
  ORDER_HEADER (changed)
    └─ ORDER_LINE (FK: ORDER_LINE.ORDER_ID → ORDER_HEADER.ID)
    └─ INVOICE (FK: INVOICE.ORDER_ID → ORDER_HEADER.ID)
  ORDER_STATUS_CODE (changed)
    └─ ORDER_HEADER (FK: ORDER_HEADER.STATUS_CODE → ORDER_STATUS_CODE.CODE)

Summary: 2 changed tables, 3 downstream tables affected.
```

### JSON Output

```json
{
  "objectId": "__from_diff__",
  "changedTables": ["ORDER_STATUS_CODE", "ORDER_HEADER"],
  "migrationFiles": ["migrations/V12__add_order_status.sql"],
  "direct": ["ORDER_LINE", "INVOICE"],
  "transitive": [],
  "depthMap": {
    "ORDER_LINE": 1,
    "INVOICE": 1
  },
  "byType": {
    "table": ["ORDER_LINE", "INVOICE"]
  },
  "criticalPaths": [
    ["ORDER_HEADER", "ORDER_LINE"],
    ["ORDER_HEADER", "INVOICE"]
  ],
  "maxDepth": 1,
  "totalCount": 2
}
```

## Examples

### Analyze a single table

```bash
sqlfy impact ./migrations APP.USERS
```

### Analyze tables changed between commits

```bash
sqlfy impact ./migrations --from-diff HEAD~1
```

### Analyze staged (uncommitted) changes

```bash
sqlfy impact ./migrations --from-diff
```

### Combine diff-detected tables with an explicit table

```bash
sqlfy impact ./migrations --from-diff HEAD~1 --table APP.REF_DATA
```

### Analyze multiple specific tables

```bash
sqlfy impact ./migrations --table APP.USERS --table APP.ORDERS
```

### JSON output for CI/automation

```bash
sqlfy impact ./migrations --from-diff main --format json --out impact-report.json
```
