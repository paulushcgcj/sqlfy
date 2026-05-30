"""
sqlfy.domain.sqlglot_compat
============================
Runtime detection of sqlglot features and version-specific compatibility layer.

Key concepts
------------
Feature Detection
    Detect at runtime whether sqlglot supports specific SQL features natively,
    enabling graceful fallback to regex-based parsing for older versions.

Dual-Path Architecture
    For each feature (e.g., ALTER TABLE MODIFY), maintain both:
    - Native sqlglot parsing path (faster, more robust)
    - Regex fallback path (for older sqlglot versions)

Usage
-----
    from .sqlglot_compat import SQLGLOT_HAS_MODIFY

    if SQLGLOT_HAS_MODIFY:
        # Use native sqlglot AST parsing
        parse_modify_native(sql)
    else:
        # Use regex fallback
        parse_modify_regex(sql)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

try:
    import sqlglot
    from sqlglot import exp
    _SQLGLOT_AVAILABLE = True
except ImportError:
    _SQLGLOT_AVAILABLE = False
    sqlglot = None  # type: ignore
    exp = None  # type: ignore

logger = logging.getLogger(__name__)

# Suppress sqlglot "unsupported syntax" warnings — handled via regex fallback
logging.getLogger("sqlglot").setLevel(logging.CRITICAL)


# ─────────────────────────────────────────────
# FEATURE DETECTION
# ─────────────────────────────────────────────

def _detect_modify_support() -> bool:
    """
    Detect if sqlglot parses ALTER TABLE MODIFY as a structured AST node.

    Returns:
        True if sqlglot supports MODIFY natively, False if regex fallback needed.

    Notes:
        - sqlglot <30: MODIFY may be parsed as Command (raw text) → False
        - sqlglot 30+: MODIFY should be parsed as AlterTable with structured actions → True
        - This check runs once at module import and caches the result
        - As of sqlglot 30.8.0, MODIFY is still parsed as Command, so regex fallback is used
    """
    if not _SQLGLOT_AVAILABLE:
        return False
    assert sqlglot is not None
    assert exp is not None

    try:
        # Test case: simple ALTER TABLE MODIFY statement
        test_sql = "ALTER TABLE users MODIFY (email VARCHAR2(255) NOT NULL)"
        stmt = sqlglot.parse_one(test_sql, dialect="oracle")

        # If sqlglot supports MODIFY, the statement should be an Alter node
        if not isinstance(stmt, exp.Alter):
            return False

        # Check if it has structured actions (not just raw Command)
        if not hasattr(stmt, 'actions') or not stmt.actions:
            return False

        # Look for AlterColumn or similar action types
        # sqlglot may use different action node types across versions
        for action in stmt.actions:
            # Check for any structured action (not Command)
            if not isinstance(action, exp.Command):
                logger.info(
                    f"sqlglot native MODIFY support detected: {type(action).__name__}"
                )
                return True

        logger.warning(
            "sqlglot parsed MODIFY as Command (raw text) — using regex fallback"
        )
        return False

    except Exception as e:
        logger.warning(
            f"Failed to detect sqlglot MODIFY support: {e} — using regex fallback"
        )
        return False


def _detect_rename_column_support() -> bool:
    """
    Detect if sqlglot parses ALTER TABLE RENAME COLUMN as a structured AST node.

    Returns:
        True if sqlglot supports RENAME COLUMN natively, False otherwise.
    """
    if not _SQLGLOT_AVAILABLE:
        return False
    assert sqlglot is not None
    assert exp is not None

    try:
        test_sql = "ALTER TABLE users RENAME COLUMN old_name TO new_name"
        stmt = sqlglot.parse_one(test_sql, dialect="oracle")

        if not isinstance(stmt, exp.Alter):
            return False

        if not hasattr(stmt, 'actions') or not stmt.actions:
            return False

        for action in stmt.actions:
            if not isinstance(action, exp.Command):
                logger.info(
                    f"sqlglot native RENAME COLUMN support detected: {type(action).__name__}"
                )
                return True

        return False

    except Exception:
        return False


# ─────────────────────────────────────────────
# CACHED FEATURE FLAGS
# ─────────────────────────────────────────────

# These are computed once at module import and cached for the entire process
SQLGLOT_HAS_MODIFY = _detect_modify_support()
SQLGLOT_HAS_RENAME_COLUMN = _detect_rename_column_support()


# ─────────────────────────────────────────────
# NATIVE PARSING HELPERS
# ─────────────────────────────────────────────

class ModifyColumnInfo:
    """Parsed information from ALTER TABLE MODIFY statement."""
    def __init__(
        self,
        column_name: str,
        data_type: Optional[str] = None,
        precision: Optional[int] = None,
        scale: Optional[int] = None,
        nullable: Optional[bool] = None,
        default: Optional[str] = None,
    ):
        self.column_name = column_name
        self.data_type = data_type
        self.precision = precision
        self.scale = scale
        self.nullable = nullable
        self.default = default


def parse_modify_native(sql: str, dialect: str = "oracle") -> tuple[str, list[ModifyColumnInfo]]:
    """
    Parse ALTER TABLE MODIFY using native sqlglot AST.

    Args:
        sql: ALTER TABLE MODIFY statement
        dialect: SQL dialect (default: oracle)

    Returns:
        (table_name, list of ModifyColumnInfo)

    Raises:
        ValueError: If statement cannot be parsed or is not ALTER TABLE MODIFY
    """
    if not SQLGLOT_HAS_MODIFY:
        raise ValueError("sqlglot does not support native MODIFY parsing")
    assert sqlglot is not None
    assert exp is not None

    stmt = sqlglot.parse_one(sql, dialect=dialect)

    if not isinstance(stmt, exp.Alter):
        raise ValueError(f"Expected Alter, got {type(stmt).__name__}")

    # Extract table name
    table_name = stmt.this.name if hasattr(stmt.this, 'name') else str(stmt.this)

    modifications = []

    for action in stmt.actions:
        if isinstance(action, exp.Command):
            continue  # Skip unparsed commands

        # Extract column information from the action
        # Note: actual AST structure varies by sqlglot version
        col_info = _extract_modify_info_from_action(action)
        if col_info:
            modifications.append(col_info)

    return table_name.upper(), modifications


def _extract_modify_info_from_action(action: Any) -> Optional[ModifyColumnInfo]:
    """
    Extract ModifyColumnInfo from a sqlglot action node.

    This is version-specific and may need updates as sqlglot evolves.
    """
    # Try to extract column name
    col_name = None
    if hasattr(action, 'this') and hasattr(action.this, 'name'):
        col_name = action.this.name
    elif hasattr(action, 'name'):
        col_name = action.name

    if not col_name:
        return None

    # Extract data type
    data_type = None
    precision = None
    scale = None
    if hasattr(action, 'kind'):
        kind = action.kind
        if hasattr(kind, 'this'):
            data_type = str(kind.this)
        # Check for precision/scale in DataType node
        if hasattr(kind, 'expressions'):
            expressions = kind.expressions
            if len(expressions) >= 1:
                precision = int(expressions[0].this) if hasattr(expressions[0], 'this') else None
            if len(expressions) >= 2:
                scale = int(expressions[1].this) if hasattr(expressions[1], 'this') else None

    # Extract nullability
    nullable = None
    if hasattr(action, 'constraints') and exp is not None:
        for constraint in action.constraints:
            if isinstance(constraint, exp.NotNullColumnConstraint):
                nullable = False
            elif hasattr(exp, 'NullColumnConstraint') and isinstance(constraint, exp.NullColumnConstraint):  # type: ignore[attr-defined]
                nullable = True

    # Extract default value
    default = None
    if hasattr(action, 'constraints'):
        for constraint in action.constraints:
            if hasattr(constraint, 'kind') and 'DEFAULT' in str(constraint.kind).upper():
                default = str(constraint.kind)

    return ModifyColumnInfo(
        column_name=col_name.upper(),
        data_type=data_type,
        precision=precision,
        scale=scale,
        nullable=nullable,
        default=default,
    )


# ─────────────────────────────────────────────
# LOGGING / DIAGNOSTICS
# ─────────────────────────────────────────────

def log_sqlglot_capabilities():
    """Log detected sqlglot version and feature support for diagnostics."""
    if not _SQLGLOT_AVAILABLE:
        logger.info("sqlglot not available — all parsing uses regex fallback")
        return

    version = getattr(sqlglot, '__version__', 'unknown')
    logger.info(f"sqlglot version: {version}")
    logger.info(f"  MODIFY support: {'✓' if SQLGLOT_HAS_MODIFY else '✗ (using regex)'}")
    logger.info(f"  RENAME COLUMN support: {'✓' if SQLGLOT_HAS_RENAME_COLUMN else '✗ (using regex)'}")
