"""
sqlfy.parsing.sanitizer
======================
Dialect-specific DDL sanitization and normalization.
Strips vendor-specific physical storage and memory clauses prior to parsing.
"""

from __future__ import annotations

import re


def sanitize_sql(sql: str, dialect: str = "oracle") -> str:
    """Sanitize DDL SQL for the specified dialect.

    Args:
        sql: Raw SQL text.
        dialect: Dialect name (e.g. 'oracle', 'postgres', 'mysql', 'sqlite').

    Returns:
        Sanitized SQL text if matching dialect, otherwise original SQL.
    """
    if not sql or not isinstance(sql, str):
        return sql

    d = (dialect or "").strip().lower()
    if d == "oracle":
        return _clean_oracle_ddl(sql)

    return sql


def _clean_oracle_ddl(sql: str) -> str:
    """Strip Oracle physical storage, memory, and vendor-specific DDL clauses."""
    # Data type specifiers: VARCHAR2 (50 BYTE) / CHAR (10 BYTE) -> VARCHAR2(50)
    sql = re.sub(
        r"\b(VARCHAR2?|CHAR|NVARCHAR2?)\s*\(\s*(\d+)\s*(?:BYTE|CHAR)\s*\)",
        r"\1(\2)",
        sql,
        flags=re.I,
    )

    # Physical storage / tablespace / memory clauses
    sql = re.sub(r"\bNO\s+INMEMORY\b", "", sql, flags=re.I)
    sql = re.sub(r"\bINMEMORY\b", "", sql, flags=re.I)
    sql = re.sub(r"\bTABLESPACE\s+[\"\w$]+\b", "", sql, flags=re.I)
    sql = re.sub(r"\bPCTFREE\s+\d+\b", "", sql, flags=re.I)
    sql = re.sub(r"\bPCTUSED\s+\d+\b", "", sql, flags=re.I)
    sql = re.sub(r"\bINITRANS\s+\d+\b", "", sql, flags=re.I)
    sql = re.sub(r"\bMAXTRANS\s+\d+\b", "", sql, flags=re.I)
    sql = re.sub(r"\bSTORAGE\s*\([^)]+\)", "", sql, flags=re.I)
    sql = re.sub(r"\bSEGMENT\s+CREATION\s+(?:IMMEDIATE|DEFERRED)\b", "", sql, flags=re.I)
    sql = re.sub(r"\bORGANIZATION\s+INDEX\b", "", sql, flags=re.I)
    sql = re.sub(r"\bNOPARALLEL\b", "", sql, flags=re.I)
    sql = re.sub(r"\bPARALLEL(?:\s+\d+)?\b", "", sql, flags=re.I)
    sql = re.sub(r"\bLOGGING\b", "", sql, flags=re.I)
    sql = re.sub(r"\bNOLOGGING\b", "", sql, flags=re.I)
    sql = re.sub(r"\bCACHE(?:\s+\d+)?\b", "", sql, flags=re.I)
    sql = re.sub(r"\bNOCACHE\b", "", sql, flags=re.I)
    sql = re.sub(r"\bMONITORING\b", "", sql, flags=re.I)
    sql = re.sub(r"\bNOMONITORING\b", "", sql, flags=re.I)
    sql = re.sub(r"\bUSING\s+INDEX\s+TABLESPACE\s+(?:\"?[\w$]+\"?\.)?\"?[\w$]+\"?", "", sql, flags=re.I)
    sql = re.sub(r"\bUSING\s+INDEX\s+(?:\"?[\w$]+\"?\.)?\"?[\w$]+\"?", "", sql, flags=re.I)
    sql = re.sub(r"\bUSING\s+INDEX\b", "", sql, flags=re.I)
    sql = re.sub(r"\bENABLE\b", "", sql, flags=re.I)
    sql = re.sub(r"\bDISABLE\b", "", sql, flags=re.I)
    sql = re.sub(r"\bVALIDATE\b", "", sql, flags=re.I)
    sql = re.sub(r"\bNOVALIDATE\b", "", sql, flags=re.I)
    sql = re.sub(r"\bRELY\b", "", sql, flags=re.I)
    sql = re.sub(r"\bNORELY\b", "", sql, flags=re.I)
    sql = re.sub(r"\bINITIALLY\s+(?:IMMEDIATE|DEFERRED)\b", "", sql, flags=re.I)
    sql = re.sub(r"\bNOT\s+DEFERRABLE\b", "", sql, flags=re.I)
    sql = re.sub(r"\bDEFERRABLE\b", "", sql, flags=re.I)
    sql = re.sub(r"\bCASCADE\s+CONSTRAINTS?\b", "", sql, flags=re.I)
    sql = re.sub(r"\bLOB\s*\([^)]+\)\s*STORE\s+AS\s*(?:\([^)]*\)|[^\n;]+)?", "", sql, flags=re.I)

    return sql
