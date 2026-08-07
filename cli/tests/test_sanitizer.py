"""
test_sanitizer.py
=================
Unit tests for dialect-gated SQL sanitizer and Oracle DDL parsing.
"""

from __future__ import annotations

from sqlfy.parsing.sanitizer import sanitize_sql
from sqlfy.reconstructor import Reconstructor


def test_sanitize_oracle_ddl():
    raw = """
    CREATE TABLE THE.PROXY_CONTROL (
        ROLE_NAME VARCHAR2 (50 BYTE) NOT NULL,
        MIN_CONNECTIONS NUMBER (3)
    ) NO INMEMORY TABLESPACE MY_TS STORAGE (INITIAL 64K);
    """
    cleaned = sanitize_sql(raw, dialect="oracle")

    assert "BYTE" not in cleaned
    assert "NO INMEMORY" not in cleaned
    assert "TABLESPACE MY_TS" not in cleaned
    assert "STORAGE" not in cleaned
    assert "VARCHAR2(50)" in cleaned


def test_sanitize_other_dialects_untouched():
    raw = "CREATE TABLE my_table (id INT, data VARCHAR2 (50 BYTE));"

    assert sanitize_sql(raw, dialect="postgres") == raw
    assert sanitize_sql(raw, dialect="sqlite") == raw
    assert sanitize_sql(raw, dialect="mysql") == raw


def test_reconstructor_oracle_tablespace_parsing():
    sql = """
    CREATE TABLE THE.EMP_TEST (
        EMP_ID NUMBER(10) NOT NULL,
        EMP_NAME VARCHAR2(100 BYTE) NOT NULL
    ) TABLESPACE USERS STORAGE (INITIAL 10K);
    """
    r = Reconstructor(dialect="oracle")
    res = r.apply_file("V1__emp.sql", sql)

    assert "EMP_TEST" in r.tables or "THE.EMP_TEST" in r.tables
    table = r.tables.get("THE.EMP_TEST") or r.tables.get("EMP_TEST")
    assert table is not None
    assert any(c.name == "EMP_ID" for c in table.columns)
    assert any(c.name == "EMP_NAME" for c in table.columns)
