"""
test_alter_constraints.py
==========================
Unit tests for ALTER TABLE constraint parsing (Foreign Keys & Primary Keys) in Reconstructor.
"""

from __future__ import annotations

from sqlfy.reconstructor import Reconstructor


def test_reconstructor_alter_table_foreign_key_oracle():
    create_sql1 = "CREATE TABLE THE.USERS (USER_ID NUMBER(10) NOT NULL);"
    create_sql2 = "CREATE TABLE THE.ORDERS (ORDER_ID NUMBER(10) NOT NULL, USER_ID NUMBER(10) NOT NULL);"
    fk_sql = """
    ALTER TABLE THE.ORDERS
        ADD CONSTRAINT FK_ORDERS_USER FOREIGN KEY (USER_ID)
        REFERENCES THE.USERS (USER_ID)
        RELY NOVALIDATE;
    """

    r = Reconstructor(dialect="oracle")
    r.apply_file("V1__users.sql", create_sql1)
    r.apply_file("V2__orders.sql", create_sql2)
    r.apply_file("V3__fk.sql", fk_sql)

    graph = r.snapshot()
    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert edge.from_table == "THE.ORDERS"
    assert edge.to_table == "THE.USERS"
    assert edge.from_cols == ["USER_ID"]
    assert edge.to_cols == ["USER_ID"]


def test_reconstructor_alter_table_primary_key_oracle():
    create_sql = "CREATE TABLE THE.USERS (USER_ID NUMBER(10) NOT NULL, EMAIL VARCHAR2(100));"
    pk_sql = """
    ALTER TABLE THE.USERS
        ADD CONSTRAINT PK_USERS PRIMARY KEY (USER_ID)
        USING INDEX TABLESPACE TS_INDX ENABLE;
    """

    r = Reconstructor(dialect="oracle")
    r.apply_file("V1__users.sql", create_sql)
    r.apply_file("V2__pk.sql", pk_sql)

    table = r.tables.get("THE.USERS") or r.tables.get("USERS")
    assert table is not None
    pk_col = next(c for c in table.columns if c.name == "USER_ID")
    assert pk_col.primary_key is True
