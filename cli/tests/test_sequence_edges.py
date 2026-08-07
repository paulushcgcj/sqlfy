"""
test_sequence_edges.py
=======================
Unit tests for Sequence-to-Table graph edge extraction and inferencing.
"""

from __future__ import annotations

from sqlfy.graph.builder import build_networkx_graph
from sqlfy.reconstructor import Reconstructor


def test_trigger_sequence_edge():
    create_tbl = "CREATE TABLE THE.USERS (USER_ID NUMBER(10) NOT NULL);"
    create_seq = "CREATE SEQUENCE THE.SEQ_USERS START WITH 1;"
    create_trg = """
    CREATE OR REPLACE TRIGGER THE.TRG_USERS
    BEFORE INSERT ON THE.USERS
    FOR EACH ROW
    BEGIN
        SELECT THE.SEQ_USERS.NEXTVAL INTO :NEW.USER_ID FROM DUAL;
    END;
    """

    r = Reconstructor(dialect="oracle")
    r.apply_file("V1__tbl.sql", create_tbl)
    r.apply_file("V2__seq.sql", create_seq)
    r.apply_file("V3__trg.sql", create_trg)

    graph = r.snapshot()
    nx_g = build_networkx_graph(graph)

    assert nx_g.has_edge("THE.USERS", "THE.SEQ_USERS")
    edge_data = nx_g.edges["THE.USERS", "THE.SEQ_USERS"]
    assert edge_data["relation"] == "uses_sequence"
    assert edge_data["confidence"] == "EXTRACTED"


def test_naming_pattern_sequence_edge():
    create_tbl = "CREATE TABLE THE.ORDERS (ORDER_ID NUMBER(10) NOT NULL);"
    create_seq = "CREATE SEQUENCE THE.ORDERS_SEQ START WITH 1;"

    r = Reconstructor(dialect="oracle")
    r.apply_file("V1__tbl.sql", create_tbl)
    r.apply_file("V2__seq.sql", create_seq)

    graph = r.snapshot()
    nx_g = build_networkx_graph(graph)

    assert nx_g.has_edge("THE.ORDERS", "THE.ORDERS_SEQ")
    edge_data = nx_g.edges["THE.ORDERS", "THE.ORDERS_SEQ"]
    assert edge_data["relation"] == "uses_sequence"
    assert edge_data["confidence"] == "INFERRED"
