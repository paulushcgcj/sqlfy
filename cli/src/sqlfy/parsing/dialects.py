"""
sqlfy.parsing.dialects
======================
Re-exports DialectAdapter and concrete adapters from sqlfy.dialects.

All dialect logic lives in a single canonical location (sqlfy.dialects).
This module exists only for backward-compatibility imports within the
parsing package.
"""

from ..dialects import (  # noqa: F401
    DialectAdapter,
    OracleAdapter,
    PostgresAdapter,
    MySQLAdapter,
    SQLiteAdapter,
)
