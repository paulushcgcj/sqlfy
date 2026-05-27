"""Migration execution cost estimation (Feature #19).

Estimate relative execution cost of migrations using heuristics based on SQL
operations (table rewrites, index builds, DML scans, constraint validation).

This is intentionally heuristic: without table statistics we produce a
relative `score` (0-100) and a human-friendly `category` (low/medium/high/very_high).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

import sqlglot
import sqlglot.expressions as exp


# ── Weight profiles ──────────────────────────────────────────────────────────
# Each profile maps op_type substrings (case-insensitive) to a multiplier.
# Patterns are checked via "fragment in op_type.lower()"; first match wins.
# The special key "*" is the catch-all fallback multiplier (default 1.0).
WEIGHT_PROFILES: Dict[str, Dict[str, float]] = {
    # Default: conservative — all operations scored at face value.
    "default": {},
    # PL/SQL: tuned for Oracle-heavy repos where packages, procedures, triggers,
    # and functions are routine deploy objects. Reduces score inflation from
    # procedural code so high scores reflect genuine data/DDL risk.
    "plsql": {
        "create proc/view":   0.1,   # Package/procedure/trigger creation is cheap
        "unclassified":       0.2,   # Most unclassified commands are PL/SQL bodies
        "command":            0.2,   # Catch-all Command nodes inside packages
        "insert ... select":  0.8,   # Still expensive but reduce noise
        "insert":             0.5,   # Single-row inserts in packages are cheap
        "*":                  1.0,
    },
    # Data-migration: tuned for repos dominated by bulk data loads. Amplifies bulk
    # DML scores to surface expensive data pumps and reduces DDL noise.
    "data-migration": {
        "insert ... select":  1.5,
        "merge":              1.5,
        "update (no where)": 1.5,
        "delete (no where)": 1.5,
        "insert":             1.3,
        "create proc/view":   0.3,
        "unclassified":       0.5,
        "*":                  1.0,
    },
}


def _apply_profile(ops: List["OperationEstimate"], profile_name: str) -> None:
    """Apply weight-profile multipliers to a list of OperationEstimate objects in-place."""
    profile = WEIGHT_PROFILES.get(profile_name, {})
    if not profile:
        return
    catch_all = profile.get("*", 1.0)
    for op in ops:
        op_lower = op.op_type.lower()
        multiplier = catch_all
        for fragment, mult in profile.items():
            if fragment == "*":
                continue
            if fragment in op_lower:
                multiplier = mult
                break
        op.weight = max(1, int(round(op.weight * multiplier)))


@dataclass
class OperationEstimate:
    op_type: str
    weight: int
    reason: str
    tables: List[str] = field(default_factory=list)
    est_seconds: float = 0.0


@dataclass
class MigrationCost:
    filename: str
    score: int
    category: str
    operations: List[OperationEstimate] = field(default_factory=list)
    estimated_seconds: float = 0.0


def _column_is_not_null_no_default(col_def: exp.ColumnDef) -> bool:
    constraints = getattr(col_def, "constraints", [])
    has_not_null = any(
        isinstance(c.args.get("kind"), exp.NotNullColumnConstraint)
        for c in constraints
    )
    has_default = any(
        isinstance(c.args.get("kind"), exp.DefaultColumnConstraint)
        for c in constraints
    )
    return has_not_null and not has_default


def _estimate_statement(stmt: exp.Expression, raw_sql: str) -> List[OperationEstimate]:
    ops: List[OperationEstimate] = []
    raw_up = raw_sql.upper()

    # CREATE
    if isinstance(stmt, exp.Create):
        create_kind = (stmt.args.get("kind") or "").upper()
        if create_kind == "TABLE":
            # CTAS (CREATE TABLE AS SELECT) is expensive
            if re.search(r"\bAS\s+SELECT\b", raw_up):
                ops.append(OperationEstimate("CREATE TABLE AS SELECT", 60, "CTAS reads source tables and writes new table"))
            else:
                ops.append(OperationEstimate("CREATE TABLE", 20, "Create table (low cost unless CTAS)"))
        elif create_kind == "INDEX":
            if "CONCURRENTLY" in raw_up:
                ops.append(OperationEstimate("CREATE INDEX CONCURRENTLY", 20, "Non-blocking index build"))
            else:
                ops.append(OperationEstimate("CREATE INDEX", 40, "Index build may block writes or be costly"))
        else:
            ops.append(OperationEstimate(f"CREATE {create_kind}", 10, "Object creation (low cost)"))

    # ALTER TABLE family
    elif isinstance(stmt, exp.Alter):
        for action in stmt.args.get("actions", []):
            if isinstance(action, exp.Schema):
                for col in action.expressions:
                    if isinstance(col, exp.ColumnDef):
                        if _column_is_not_null_no_default(col):
                            ops.append(OperationEstimate("ADD COLUMN NOT NULL", 80, "Adds NOT NULL without DEFAULT — requires table rewrite"))
                        else:
                            ops.append(OperationEstimate("ADD COLUMN", 10, "Add nullable column (low cost)"))
            elif isinstance(action, exp.ColumnDef):
                if _column_is_not_null_no_default(action):
                    ops.append(OperationEstimate("ADD COLUMN NOT NULL", 80, "Adds NOT NULL without DEFAULT — requires table rewrite"))
                else:
                    ops.append(OperationEstimate("ADD COLUMN", 10, "Add nullable column (low cost)"))
            elif isinstance(action, exp.Drop):
                kind = (action.args.get("kind") or "").upper()
                if kind == "COLUMN":
                    ops.append(OperationEstimate("DROP COLUMN", 70, "Drop column — may require table rewrite or is destructive"))
                elif kind == "INDEX":
                    ops.append(OperationEstimate("DROP INDEX", 5, "Drop index (low cost)"))
                else:
                    ops.append(OperationEstimate("ALTER DROP", 30, "Structural alteration"))
            elif isinstance(action, exp.AddConstraint):
                ops.append(OperationEstimate("ADD CONSTRAINT", 60, "Constraint validation may scan table"))
            elif isinstance(action, (exp.RenameColumn, exp.AlterRename)):
                ops.append(OperationEstimate("RENAME COLUMN", 30, "Renaming columns may require code updates"))
            elif isinstance(action, exp.AlterColumn):
                ops.append(OperationEstimate("MODIFY COLUMN", 80, "Column type change may require table rewrite"))
            elif isinstance(action, exp.Command):
                if "MODIFY" in raw_up:
                    ops.append(OperationEstimate("MODIFY COLUMN", 80, "Column type change may require table rewrite"))
                elif "RENAME" in raw_up:
                    ops.append(OperationEstimate("RENAME", 30, "Rename operation"))
                else:
                    ops.append(OperationEstimate("ALTER (command)", 30, "Alter command (unclassified)"))

    # INSERT
    elif isinstance(stmt, exp.Insert):
        if re.search(r"INSERT\s+INTO[\s\S]+SELECT", raw_up):
            ops.append(OperationEstimate("INSERT ... SELECT", 60, "Bulk insert from SELECT — reads source tables"))
        else:
            ops.append(OperationEstimate("INSERT", 10, "Insert rows (low cost)"))

    # DELETE
    elif isinstance(stmt, exp.Delete):
        has_where = stmt.args.get("where") is not None
        if has_where:
            ops.append(OperationEstimate("DELETE (where)", 50, "Deletes rows with filter — may be expensive"))
        else:
            ops.append(OperationEstimate("DELETE (no where)", 90, "Deletes all rows — very expensive and destructive"))

    # UPDATE
    elif isinstance(stmt, exp.Update):
        has_where = stmt.args.get("where") is not None
        if has_where:
            ops.append(OperationEstimate("UPDATE (where)", 50, "Updates rows with filter — may be expensive"))
        else:
            ops.append(OperationEstimate("UPDATE (no where)", 90, "Updates all rows — very expensive and destructive"))

    # TRUNCATE
    elif hasattr(exp, "TruncateTable") and isinstance(stmt, exp.TruncateTable):
        ops.append(OperationEstimate("TRUNCATE", 80, "Irreversible fast delete (high impact)"))

    # MERGE / UPSERT
    elif stmt.__class__.__name__.upper() == "MERGE":
        ops.append(OperationEstimate("MERGE", 90, "Merge/upsert — complex, may scan and modify many rows"))

    # PROCEDURAL / VIEW creation — low cost
    elif isinstance(stmt, exp.Command):
        if re.match(r"CREATE\s+(TRIGGER|PROCEDURE|FUNCTION|PACKAGE|VIEW)\b", raw_up):
            ops.append(OperationEstimate("CREATE PROC/VIEW", 5, "Procedural or view creation — metadata only"))
        elif re.match(r"TRUNCATE\b", raw_up):
            ops.append(OperationEstimate("TRUNCATE", 80, "Irreversible fast delete (high impact)"))
        else:
            ops.append(OperationEstimate(type(stmt).__name__, 30, "Unclassified command"))

    else:
        ops.append(OperationEstimate(type(stmt).__name__, 10, "Unclassified statement (assume low cost)"))

    return ops


def _extract_table_names(stmt: exp.Expression, raw_sql: str) -> List[str]:
    """Return a list of table names referenced in the statement (best-effort)."""
    names: List[str] = []
    try:
        for t in stmt.find_all(exp.Table):
            try:
                n = t.sql(dialect="oracle")
            except Exception:
                n = str(t)
            n = n.strip().strip('"').lower()
            if n:
                names.append(n)
    except Exception:
        # Fallback: simple regex-based extraction
        for m in re.finditer(r"\bFROM\s+([A-Za-z0-9_\.]+)", raw_sql, re.IGNORECASE):
            names.append(m.group(1).lower())
        for m in re.finditer(r"\bINSERT\s+INTO\s+([A-Za-z0-9_\.]+)", raw_sql, re.IGNORECASE):
            names.append(m.group(1).lower())
        for m in re.finditer(r"\bUPDATE\s+([A-Za-z0-9_\.]+)", raw_sql, re.IGNORECASE):
            names.append(m.group(1).lower())
        for m in re.finditer(r"\bALTER\s+TABLE\s+([A-Za-z0-9_\.]+)", raw_sql, re.IGNORECASE):
            names.append(m.group(1).lower())
        for m in re.finditer(r"\bCREATE\s+TABLE\s+([A-Za-z0-9_\.]+)", raw_sql, re.IGNORECASE):
            names.append(m.group(1).lower())

    # Deduplicate while preserving order
    seen = set()
    out: List[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _get_table_stats(name: str, table_stats: Dict[str, Dict[str, Any]] | None, default_rows: int, default_size: int) -> tuple[int, int]:
    """Lookup table stats by exact or short name; return (rows, avg_row_size).

    Table stats keys are normalized to lower-case when provided.
    """
    if not table_stats:
        return default_rows, default_size

    key = name.lower()
    if key in table_stats:
        s = table_stats[key]
        return int(s.get("rows", default_rows)), int(s.get("avg_row_size", default_size))

    # Try short name after dot
    if "." in key:
        short = key.split(".")[-1]
        if short in table_stats:
            s = table_stats[short]
            return int(s.get("rows", default_rows)), int(s.get("avg_row_size", default_size))

    # Try suffix match
    for k, v in table_stats.items():
        if k.endswith("." + key) or k == key or k.endswith("." + key.split(".")[-1]):
            return int(v.get("rows", default_rows)), int(v.get("avg_row_size", default_size))

    return default_rows, default_size


def estimate_migration(
    filename: str,
    content: str,
    dialect: str = "oracle",
    table_stats: Dict[str, Dict[str, Any]] | None = None,
    throughput_bytes_per_sec: int = 100 * 1024 * 1024,
    default_rows: int = 100_000,
    default_row_size: int = 200,
    weight_profile: str = "default",
) -> MigrationCost:
    """Estimate migration cost and runtime.

    Args:
        filename: migration filename
        content: SQL content
        dialect: sqlglot dialect
        table_stats: optional mapping table -> {rows:int, avg_row_size:int}
        throughput_bytes_per_sec: assumed disk throughput for IO-bound ops
        default_rows: fallback row count when stats missing
        default_row_size: fallback avg row size in bytes
        weight_profile: scoring profile — 'default', 'plsql', or 'data-migration'
    """
    stmts = sqlglot.parse(content, dialect=dialect, error_level=sqlglot.ErrorLevel.WARN)
    ops: List[OperationEstimate] = []
    total_seconds = 0.0

    for stmt in stmts:
        if stmt is None:
            continue
        raw_sql = stmt.sql(dialect=dialect)
        stmt_ops = _estimate_statement(stmt, raw_sql)
        tables = _extract_table_names(stmt, raw_sql)

        for o in stmt_ops:
            o.tables = tables
            # Compute per-op estimated seconds using heuristics and available table stats
            secs = 0.0
            # Heuristic: CTAS / INSERT SELECT
            if "AS SELECT" in o.op_type or "INSERT ... SELECT" in o.op_type:
                # sum source table sizes
                total_rows = 0
                total_bytes = 0
                for t in tables:
                    rows, avg = _get_table_stats(t, table_stats, default_rows, default_row_size)
                    total_rows += rows
                    total_bytes += rows * avg
                if total_rows == 0:
                    total_rows = default_rows
                    total_bytes = default_rows * default_row_size
                # read + write + overhead
                secs = (total_bytes * 2) / float(throughput_bytes_per_sec) * 1.2

            elif o.op_type.startswith("CREATE INDEX"):
                # build index over target table
                tgt = tables[0] if tables else None
                rows, avg = _get_table_stats(tgt, table_stats, default_rows, default_row_size)
                secs = (rows * avg) / float(throughput_bytes_per_sec) * 1.2

            elif o.op_type in ("ADD COLUMN NOT NULL", "MODIFY COLUMN", "DROP COLUMN"):
                # table rewrite
                tgt = tables[0] if tables else None
                rows, avg = _get_table_stats(tgt, table_stats, default_rows, default_row_size)
                secs = (rows * avg) / float(throughput_bytes_per_sec) * 1.5

            elif o.op_type in ("DELETE (no where)", "UPDATE (no where)"):
                tgt = tables[0] if tables else None
                rows, avg = _get_table_stats(tgt, table_stats, default_rows, default_row_size)
                # full table scan/update
                mult = 0.8 if "DELETE" in o.op_type else 1.2
                secs = (rows * avg) / float(throughput_bytes_per_sec) * mult

            elif o.op_type == "TRUNCATE":
                secs = 1.0

            elif o.op_type == "MERGE":
                total_bytes = 0
                for t in tables:
                    rows, avg = _get_table_stats(t, table_stats, default_rows, default_row_size)
                    total_bytes += rows * avg
                secs = (total_bytes * 1.5) / float(throughput_bytes_per_sec)

            else:
                # Fallback proportional to weight
                secs = max(0.1, o.weight * 0.02)

            o.est_seconds = float(secs)
            total_seconds += secs

        ops.extend(stmt_ops)

    # Apply weight profile multipliers before computing score
    _apply_profile(ops, weight_profile)

    raw_score = sum(o.weight for o in ops)
    score = min(100, int(raw_score))

    if score < 25:
        category = "low"
    elif score < 50:
        category = "medium"
    elif score < 75:
        category = "high"
    else:
        category = "very_high"

    return MigrationCost(
        filename=filename,
        score=score,
        category=category,
        operations=ops,
        estimated_seconds=round(total_seconds, 3),
    )


def estimate_migrations(
    files: List[Dict[str, Any]],
    dialect: str = "oracle",
    table_stats: Dict[str, Dict[str, Any]] | None = None,
    throughput_bytes_per_sec: int = 100 * 1024 * 1024,
    weight_profile: str = "default",
) -> List[MigrationCost]:
    return [
        estimate_migration(
            f["filename"],
            f["sql"],
            dialect=dialect,
            table_stats=table_stats,
            throughput_bytes_per_sec=throughput_bytes_per_sec,
            weight_profile=weight_profile,
        )
        for f in files
    ]


def format_text(results: List[MigrationCost], verbose: bool = False, weight_profile: str = "default") -> str:
    if not results:
        return "No migrations to estimate."

    profile_note = f"  (weight profile: {weight_profile})" if weight_profile != "default" else ""
    lines: List[str] = [f"Migration Cost Estimates{profile_note}", "=" * 24, ""]
    max_name = max(len(r.filename) for r in results)
    for r in results:
        pad = max_name - len(r.filename)
        lines.append(f"  {r.filename}{' ' * pad}  →  Score={r.score:3d}  Category={r.category}")
        if verbose and r.operations:
            for o in r.operations:
                lines.append(f"       - {o.op_type}: weight={o.weight} — {o.reason}")
    return "\n".join(lines)


def format_json(results: List[MigrationCost]) -> str:
    data = {
        "migrations": [
            {
                "filename": r.filename,
                "score": r.score,
                "category": r.category,
                "estimated_seconds": r.estimated_seconds,
                "operations": [{"op": o.op_type, "weight": o.weight, "reason": o.reason, "tables": o.tables, "est_seconds": o.est_seconds} for o in r.operations],
            }
            for r in results
        ],
        "summary": {
            "total": len(results),
            "avg_score": (sum(r.score for r in results) / len(results)) if results else 0,
            "avg_estimated_seconds": (sum(r.estimated_seconds for r in results) / len(results)) if results else 0,
        },
    }
    return json.dumps(data, indent=2)
