"""sqlfy.analysis.safety
=====================
Migration safety-level scoring engine (Feature #15).

Scores each migration file by the worst-case SQL operation it contains:

  SAFE         – Non-destructive additions (CREATE TABLE, ADD nullable COLUMN).
  MEDIUM_RISK  – Potentially blocking or structural (CREATE INDEX, ADD CONSTRAINT).
  HIGH_RISK    – Data loss or schema rewrites (DROP COLUMN, MODIFY type, NOT NULL add).
  DANGEROUS    – Irreversible destruction (DROP TABLE, TRUNCATE, DELETE/UPDATE without WHERE).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Literal

import sqlglot
import sqlglot.expressions as exp

SafetyLevel = Literal["SAFE", "MEDIUM_RISK", "HIGH_RISK", "DANGEROUS"]

_LEVEL_ORDER: dict[str, int] = {
    "SAFE": 0,
    "MEDIUM_RISK": 1,
    "HIGH_RISK": 2,
    "DANGEROUS": 3,
}

_LEVEL_ICON: dict[str, str] = {
    "SAFE": "✅",
    "MEDIUM_RISK": "⚠",
    "HIGH_RISK": "⚠⚠",
    "DANGEROUS": "❌",
}


@dataclass
class StatementRisk:
    """Risk assessment for a single SQL statement."""

    sql_preview: str
    level: str
    reason: str
    statement_type: str


@dataclass
class MigrationSafety:
    """Safety assessment for a single migration file."""

    filename: str
    overall_level: str
    statement_risks: list[StatementRisk] = field(default_factory=list)

    @property
    def requires_approval(self) -> bool:
        """True when the migration must be manually reviewed before production deployment."""
        return self.overall_level in ("HIGH_RISK", "DANGEROUS")

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "overall_level": self.overall_level,
            "requires_approval": self.requires_approval,
            "statements": [
                {
                    "statement_type": r.statement_type,
                    "level": r.level,
                    "reason": r.reason,
                    "sql_preview": r.sql_preview,
                }
                for r in self.statement_risks
            ],
        }


# ─────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────

def _column_is_not_null_no_default(col_def: exp.ColumnDef) -> bool:
    """Return True when the column has NOT NULL but no DEFAULT — requires table rewrite."""
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


def _score_alter(stmt: exp.Alter, raw_sql: str) -> StatementRisk:
    """Score an ALTER TABLE statement using its worst-case action."""
    level: str = "SAFE"
    reason = "Non-destructive alteration"
    stmt_type = "ALTER TABLE"

    for action in stmt.args.get("actions", []):
        # Oracle ADD (col TYPE ...) wraps columns in Schema
        if isinstance(action, exp.Schema):
            for col in action.expressions:
                if isinstance(col, exp.ColumnDef):
                    if _column_is_not_null_no_default(col):
                        lvl, rsn, typ = "HIGH_RISK", "NOT NULL without DEFAULT requires table rewrite", "ADD COLUMN NOT NULL"
                    else:
                        lvl, rsn, typ = "SAFE", "Non-destructive column addition", "ADD COLUMN"
                    # Use >= so the first ADD COLUMN always replaces the default "ALTER TABLE" type
                    if _LEVEL_ORDER[lvl] >= _LEVEL_ORDER[level]:
                        level, reason, stmt_type = lvl, rsn, typ

        elif isinstance(action, exp.ColumnDef):
            # Non-Oracle ADD col TYPE syntax
            if _column_is_not_null_no_default(action):
                lvl, rsn, typ = "HIGH_RISK", "NOT NULL without DEFAULT requires table rewrite", "ADD COLUMN NOT NULL"
            else:
                lvl, rsn, typ = "SAFE", "Non-destructive column addition", "ADD COLUMN"
            # Use >= so the first ADD COLUMN always replaces the default "ALTER TABLE" type
            if _LEVEL_ORDER[lvl] >= _LEVEL_ORDER[level]:
                level, reason, stmt_type = lvl, rsn, typ

        elif isinstance(action, exp.Drop):
            kind = (action.args.get("kind") or "").upper()
            if kind == "COLUMN":
                lvl, rsn, typ = "HIGH_RISK", "Data loss, schema change", "DROP COLUMN"
            elif kind == "INDEX":
                lvl, rsn, typ = "MEDIUM_RISK", "Removes query optimisation", "DROP INDEX"
            elif kind in ("CONSTRAINT", "PRIMARY_KEY", "FOREIGN_KEY", "UNIQUE"):
                lvl, rsn, typ = "MEDIUM_RISK", "Removes data integrity rule", "DROP CONSTRAINT"
            else:
                lvl, rsn, typ = "MEDIUM_RISK", "Structural modification", "ALTER TABLE DROP"
            if _LEVEL_ORDER[lvl] > _LEVEL_ORDER[level]:
                level, reason, stmt_type = lvl, rsn, typ

        elif isinstance(action, exp.AddConstraint):
            lvl, rsn, typ = "MEDIUM_RISK", "Constraint validation may fail on existing data", "ADD CONSTRAINT"
            if _LEVEL_ORDER[lvl] > _LEVEL_ORDER[level]:
                level, reason, stmt_type = lvl, rsn, typ

        elif isinstance(action, (exp.RenameColumn, exp.AlterRename)):
            lvl, rsn, typ = "MEDIUM_RISK", "Breaks code referencing original name", "RENAME"
            if _LEVEL_ORDER[lvl] > _LEVEL_ORDER[level]:
                level, reason, stmt_type = lvl, rsn, typ

        elif isinstance(action, exp.AlterColumn):
            # Native MODIFY COLUMN support
            lvl, rsn, typ = "HIGH_RISK", "Column type change may truncate or lose data", "MODIFY COLUMN"
            if _LEVEL_ORDER[lvl] > _LEVEL_ORDER[level]:
                level, reason, stmt_type = lvl, rsn, typ

        elif isinstance(action, exp.Command):
            # Oracle MODIFY / RENAME parsed as raw Command inside ALTER
            raw_up = raw_sql.upper()
            if "MODIFY" in raw_up:
                lvl, rsn, typ = "HIGH_RISK", "Column type change may truncate or lose data", "MODIFY COLUMN"
                if _LEVEL_ORDER[lvl] > _LEVEL_ORDER[level]:
                    level, reason, stmt_type = lvl, rsn, typ
            elif "RENAME" in raw_up:
                lvl, rsn, typ = "MEDIUM_RISK", "Breaks code referencing original name", "RENAME"
                if _LEVEL_ORDER[lvl] > _LEVEL_ORDER[level]:
                    level, reason, stmt_type = lvl, rsn, typ

    return StatementRisk(
        sql_preview=raw_sql[:120].strip(),
        level=level,
        reason=reason,
        statement_type=stmt_type,
    )


def _score_command(stmt: exp.Command, raw_sql: str) -> StatementRisk:
    """Score Oracle-specific statements that sqlglot parses as raw Command nodes."""
    raw_up = raw_sql.strip().upper()

    if re.match(r"TRUNCATE\b", raw_up):
        return StatementRisk(raw_sql[:120].strip(), "DANGEROUS", "Irreversible data loss", "TRUNCATE")

    if re.match(r"ALTER\s+TABLE\b", raw_up) and "MODIFY" in raw_up:
        return StatementRisk(raw_sql[:120].strip(), "HIGH_RISK", "Column type change may truncate or lose data", "MODIFY COLUMN")

    if re.match(r"ALTER\s+TABLE\b", raw_up) and "RENAME" in raw_up:
        return StatementRisk(raw_sql[:120].strip(), "MEDIUM_RISK", "Breaks code referencing original name", "RENAME")

    if re.match(r"CREATE\s+(OR\s+REPLACE\s+)?(TRIGGER|PROCEDURE|FUNCTION|PACKAGE|VIEW)\b", raw_up):
        return StatementRisk(raw_sql[:120].strip(), "SAFE", "Procedural object creation", "CREATE PROC/TRIGGER/VIEW")

    if re.match(r"CREATE\s+(UNIQUE\s+)?INDEX\b", raw_up):
        return StatementRisk(raw_sql[:120].strip(), "MEDIUM_RISK", "Blocks writes during index build", "CREATE INDEX")

    return StatementRisk(raw_sql[:120].strip(), "MEDIUM_RISK", "Unclassified operation", type(stmt).__name__)


def _score_statement(stmt: exp.Expression, raw_sql: str) -> StatementRisk:
    """Score a single parsed SQL statement and return its StatementRisk."""
    if isinstance(stmt, exp.Drop):
        kind = (stmt.args.get("kind") or "").upper()
        if kind == "TABLE":
            return StatementRisk(raw_sql[:120].strip(), "DANGEROUS", "Irreversible data loss", "DROP TABLE")
        if kind == "VIEW":
            return StatementRisk(raw_sql[:120].strip(), "HIGH_RISK", "Breaks dependent code", "DROP VIEW")
        if kind == "COLUMN":
            return StatementRisk(raw_sql[:120].strip(), "HIGH_RISK", "Data loss, schema change", "DROP COLUMN")
        if kind == "INDEX":
            return StatementRisk(raw_sql[:120].strip(), "MEDIUM_RISK", "Removes query optimisation", "DROP INDEX")
        if kind in ("CONSTRAINT", "FOREIGN_KEY", "PRIMARY_KEY", "UNIQUE"):
            return StatementRisk(raw_sql[:120].strip(), "MEDIUM_RISK", "Removes data integrity rule", "DROP CONSTRAINT")
        return StatementRisk(raw_sql[:120].strip(), "MEDIUM_RISK", f"DROP {kind}", f"DROP {kind}")

    if isinstance(stmt, exp.Create):
        create_kind = (stmt.args.get("kind") or "").upper()
        if create_kind == "TABLE":
            return StatementRisk(raw_sql[:120].strip(), "SAFE", "Non-destructive schema addition", "CREATE TABLE")
        if create_kind == "INDEX":
            if "concurrently" in raw_sql.lower():
                return StatementRisk(raw_sql[:120].strip(), "SAFE", "Non-blocking concurrent index build", "CREATE INDEX CONCURRENTLY")
            return StatementRisk(raw_sql[:120].strip(), "MEDIUM_RISK", "Blocks writes during index build", "CREATE INDEX")
        if create_kind in ("SEQUENCE", "SCHEMA", "TYPE"):
            return StatementRisk(raw_sql[:120].strip(), "SAFE", "Non-destructive object creation", f"CREATE {create_kind}")
        # VIEW, PROCEDURE, TRIGGER, FUNCTION, PACKAGE — also safe
        return StatementRisk(raw_sql[:120].strip(), "SAFE", "Procedural object creation", f"CREATE {create_kind}")

    if isinstance(stmt, exp.Alter):
        return _score_alter(stmt, raw_sql)

    if isinstance(stmt, exp.Insert):
        return StatementRisk(raw_sql[:120].strip(), "SAFE", "Additive data operation", "INSERT")

    if isinstance(stmt, exp.Delete):
        has_where = stmt.args.get("where") is not None
        if has_where:
            return StatementRisk(raw_sql[:120].strip(), "HIGH_RISK", "Data loss, cannot undo without backup", "DELETE")
        return StatementRisk(raw_sql[:120].strip(), "DANGEROUS", "Deletes all rows, no filter", "DELETE WITHOUT WHERE")

    if isinstance(stmt, exp.Update):
        has_where = stmt.args.get("where") is not None
        if has_where:
            return StatementRisk(raw_sql[:120].strip(), "HIGH_RISK", "Data modification, cannot undo without backup", "UPDATE")
        return StatementRisk(raw_sql[:120].strip(), "DANGEROUS", "Updates all rows without filter", "UPDATE WITHOUT WHERE")

    if hasattr(exp, "TruncateTable") and isinstance(stmt, exp.TruncateTable):
        return StatementRisk(raw_sql[:120].strip(), "DANGEROUS", "Irreversible data loss", "TRUNCATE")

    # COMMENT ON TABLE/COLUMN — purely metadata, non-destructive
    if hasattr(exp, "Comment") and isinstance(stmt, exp.Comment):
        return StatementRisk(raw_sql[:120].strip(), "SAFE", "Metadata comment", "COMMENT")

    if isinstance(stmt, exp.Command):
        return _score_command(stmt, raw_sql)

    # PL/SQL block terminators (END;) generated as EndStatement — treat as safe
    if hasattr(exp, "EndStatement") and isinstance(stmt, exp.EndStatement):
        return StatementRisk(raw_sql[:120].strip(), "SAFE", "PL/SQL block terminator", "END")

    return StatementRisk(raw_sql[:120].strip(), "MEDIUM_RISK", "Unclassified operation", type(stmt).__name__)


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def score_migration(
    filename: str,
    content: str,
    dialect: str = "oracle",
) -> MigrationSafety:
    """Score a single migration file.

    Args:
        filename: Migration filename (used in output only).
        content:  Full SQL text of the migration.
        dialect:  SQL dialect for sqlglot parsing (default ``oracle``).

    Returns:
        :class:`MigrationSafety` with per-statement risks and overall level.
    """
    stmts = sqlglot.parse(content, dialect=dialect, error_level=sqlglot.ErrorLevel.WARN)
    statement_risks: list[StatementRisk] = []

    for stmt in stmts:
        if stmt is None:
            continue
        raw_sql = stmt.sql(dialect=dialect)
        risk = _score_statement(stmt, raw_sql)
        statement_risks.append(risk)

    if not statement_risks:
        overall: str = "SAFE"
    else:
        overall = max(statement_risks, key=lambda r: _LEVEL_ORDER[r.level]).level

    return MigrationSafety(
        filename=filename,
        overall_level=overall,
        statement_risks=statement_risks,
    )


def score_migrations(
    files: list[dict],
    dialect: str = "oracle",
) -> list[MigrationSafety]:
    """Score all migrations from a loaded file list.

    Args:
        files:   List of ``{"filename": str, "sql": str}`` dicts.
        dialect: SQL dialect (default ``oracle``).

    Returns:
        List of :class:`MigrationSafety` in file order.
    """
    return [score_migration(f["filename"], f["sql"], dialect=dialect) for f in files]


# ─────────────────────────────────────────────
# FORMATTERS
# ─────────────────────────────────────────────

def format_text(scores: list[MigrationSafety], *, verbose: bool = False) -> str:
    """Render the safety report as human-readable text.

    Args:
        scores:  List of :class:`MigrationSafety` results.
        verbose: When True, include per-statement breakdown under each file.
    """
    if not scores:
        return "No migrations to score."

    lines: list[str] = ["Migration Safety Report", "=" * 23, ""]

    max_name = max(len(s.filename) for s in scores)
    for s in scores:
        icon = _LEVEL_ICON[s.overall_level]
        label = s.overall_level.replace("_", " ")
        pad = max_name - len(s.filename)
        lines.append(f"  {s.filename}{' ' * pad}  →  {label:<15}  {icon}")

        if verbose:
            for r in s.statement_risks:
                r_icon = _LEVEL_ICON[r.level]
                lines.append(f"       {r_icon}  [{r.level}] {r.statement_type}")
                lines.append(f"            → {r.reason}")
                if r.sql_preview:
                    preview = r.sql_preview[:100] + ("…" if len(r.sql_preview) > 100 else "")
                    lines.append(f"            {preview}")

    counts: dict[str, int] = {}
    for s in scores:
        counts[s.overall_level] = counts.get(s.overall_level, 0) + 1

    lines += ["", "Summary", "-------"]
    for level in ("DANGEROUS", "HIGH_RISK", "MEDIUM_RISK", "SAFE"):
        if level in counts:
            label = level.replace("_", " ")
            lines.append(f"  {label:<20} {counts[level]}")

    lines += ["", "Risk Distribution", "-----------------"]
    for level in ("DANGEROUS", "HIGH_RISK", "MEDIUM_RISK", "SAFE"):
        if level in counts:
            icon = _LEVEL_ICON[level]
            label = level.replace("_", " ")
            lines.append(f"  {icon}  {label:<20} {counts[level]} migration(s)")

    approvals_needed = sum(1 for s in scores if s.requires_approval)
    if approvals_needed:
        lines += ["", f"⚠  {approvals_needed} migration(s) require manual approval before deployment."]

    return "\n".join(lines)


def format_json(scores: list[MigrationSafety]) -> str:
    """Render the safety report as JSON."""
    counts: dict[str, int] = {}
    for s in scores:
        counts[s.overall_level] = counts.get(s.overall_level, 0) + 1

    data = {
        "migrations": [s.to_dict() for s in scores],
        "summary": {
            "total": len(scores),
            "by_level": counts,
            "requires_approval": sum(1 for s in scores if s.requires_approval),
        },
    }
    return json.dumps(data, indent=2)
