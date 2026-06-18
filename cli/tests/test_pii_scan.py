"""Tests for sqlfy.pii_scanner — scan_pii, confidence, extra_patterns, JSON contract."""

from __future__ import annotations

import json

import pytest

from sqlfy.core import apply_migrations
from sqlfy.domain.schema_state import SchemaStateBuilder, SchemaState
from sqlfy.analysis.pii_scanner import scan_pii, format_text
from sqlfy.models import PiiScanResult as PiiScanResultModel, PiiScanFinding as PiiScanFindingModel


def _inline(*pairs: tuple[str, str]) -> SchemaState:
    files = [{"filename": f, "sql": s} for f, s in pairs]
    graph = apply_migrations(files)
    return SchemaStateBuilder.from_graph(graph, source_files=files)


CUSTOMER_SQL = """
CREATE TABLE CUSTOMER (
    ID NUMBER PRIMARY KEY,
    EMAIL VARCHAR2(255),
    PHONE VARCHAR2(20),
    NAME VARCHAR2(100),
    CREATED_AT DATE,
    UPDATED_AT DATE
);
"""

ORDER_WITH_PII = """
CREATE TABLE ORDERS (
    ID NUMBER PRIMARY KEY,
    TOTAL_AMOUNT NUMBER(10,2),
    SSN VARCHAR2(11),
    DOB DATE
);
"""


def test_pii_scan_finds_known_pii_columns():
    state = _inline(("V1__test.sql", CUSTOMER_SQL))
    result = scan_pii(state)

    assert result.tables_scanned == 1
    assert result.columns_scanned == 6
    assert result.pii_table_count == 1
    assert result.pii_column_count == 3

    col_names = {f.column_name for f in result.findings}
    assert col_names == {"EMAIL", "PHONE", "NAME"}


def test_email_confidence():
    state = _inline(("V1__test.sql", CUSTOMER_SQL))
    result = scan_pii(state)

    email_finding = next(f for f in result.findings if f.column_name == "EMAIL")
    assert email_finding.pii_categories == ["email"]
    assert email_finding.confidence == 1.0


def test_phone_confidence():
    state = _inline(("V1__test.sql", CUSTOMER_SQL))
    result = scan_pii(state)

    phone_finding = next(f for f in result.findings if f.column_name == "PHONE")
    assert phone_finding.pii_categories == ["phone"]
    assert phone_finding.confidence == 1.0


def test_audit_columns_not_flagged():
    state = _inline(("V1__test.sql", CUSTOMER_SQL))
    result = scan_pii(state)

    flagged = {f.column_name for f in result.findings}
    assert "CREATED_AT" not in flagged
    assert "UPDATED_AT" not in flagged


def test_no_pii_in_order_table():
    state = _inline(
        ("V1__test.sql", CUSTOMER_SQL),
        ("V2__orders.sql", """
            CREATE TABLE ORDERS (
                ID NUMBER PRIMARY KEY,
                TOTAL_AMOUNT NUMBER(10,2)
            );
        """),
    )
    result = scan_pii(state)

    order_findings = [f for f in result.findings if f.table_name == "ORDERS"]
    assert len(order_findings) == 0


def test_min_confidence_filter():
    state = _inline(("V1__test.sql", CUSTOMER_SQL))
    raw = scan_pii(state)
    assert len(raw.findings) == 3

    # Filter with min_confidence 0.9 — all are 1.0 so all should remain
    raw.findings = [f for f in raw.findings if f.confidence >= 0.9]
    assert len(raw.findings) == 3

    # Filter with min_confidence 1.1 — none should remain
    raw.findings = [f for f in raw.findings if f.confidence >= 1.1]
    assert len(raw.findings) == 0


def test_pii_scan_no_findings():
    state = _inline(("V1__empty.sql", """
        CREATE TABLE AUDIT_LOG (
            ID NUMBER PRIMARY KEY,
            ACTION VARCHAR2(50),
            TIMESTAMP DATE
        );
    """))
    result = scan_pii(state)

    assert result.pii_column_count == 0
    assert result.pii_table_count == 0
    assert len(result.findings) == 0
    text = format_text(result)
    assert "No PII columns found." in text


def test_json_contract():
    state = _inline(("V1__test.sql", CUSTOMER_SQL))
    result = scan_pii(state)

    findings = [
        PiiScanFindingModel(
            table_name=f.table_name,
            column_name=f.column_name,
            column_type=f.column_type,
            pii_categories=f.pii_categories,
            confidence=f.confidence,
            evidence=f.evidence,
        )
        for f in result.findings
    ]
    model = PiiScanResultModel(
        findings=findings,
        tables_scanned=result.tables_scanned,
        columns_scanned=result.columns_scanned,
        pii_table_count=len({f.table_name for f in result.findings}),
        pii_column_count=len(result.findings),
    )
    raw = json.loads(model.model_dump_json(by_alias=True))

    assert "findings" in raw
    assert raw["tablesScanned"] == 1
    assert raw["columnsScanned"] == 6
    assert raw["piiTableCount"] == 1
    assert raw["piiColumnCount"] == 3

    first = raw["findings"][0]
    assert "tableName" in first
    assert "columnName" in first
    assert "piiCategories" in first
    assert "confidence" in first


def test_partial_confidence():
    state = _inline(("V1__pii.sql", """
        CREATE TABLE USERS (
            ID NUMBER PRIMARY KEY,
            CUST_EMAIL VARCHAR2(255),
            ADDR_LINE1 VARCHAR2(100)
        );
    """))
    result = scan_pii(state)

    email_finding = next(f for f in result.findings if f.column_name == "CUST_EMAIL")
    assert email_finding.confidence == 0.8

    addr_finding = next(f for f in result.findings if f.column_name == "ADDR_LINE1")
    assert addr_finding.confidence == 0.6


def test_comment_matches():
    state = _inline(("V1__comments.sql", """
        CREATE TABLE EMPLOYEE (
            ID NUMBER PRIMARY KEY,
            NOTES VARCHAR2(500)
        );
        COMMENT ON COLUMN EMPLOYEE.NOTES IS 'Contains personal email and phone contact info';
    """))
    result = scan_pii(state)

    notes_finding = next((f for f in result.findings if f.column_name == "NOTES"), None)
    assert notes_finding is not None
    # Comment-only match should get confidence 0.6
    assert notes_finding.confidence == 0.6
    assert "email" in notes_finding.pii_categories or "phone" in notes_finding.pii_categories


def test_extra_patterns():
    state = _inline(("V1__extra.sql", """
        CREATE TABLE CUSTOMER (
            ID NUMBER PRIMARY KEY,
            CUSTOM_RATING VARCHAR2(10)
        );
    """))
    extra = {"rating": [r"rating"]}

    # Without extra patterns — should not flag CUSTOM_RATING
    result_without = scan_pii(state)
    assert not any(f.column_name == "CUSTOM_RATING" for f in result_without.findings)

    # With extra patterns — should flag it
    result_with = scan_pii(state, extra_patterns=extra)
    rating_finding = next((f for f in result_with.findings if f.column_name == "CUSTOM_RATING"), None)
    assert rating_finding is not None
    assert "rating" in rating_finding.pii_categories


def test_multiple_categories():
    state = _inline(("V1__multi.sql", """
        CREATE TABLE CONTACT (
            ID NUMBER PRIMARY KEY,
            CONTACT_NAME VARCHAR2(100)
        );
    """))
    result = scan_pii(state)

    contact_finding = next(f for f in result.findings if f.column_name == "CONTACT_NAME")
    assert len(contact_finding.pii_categories) >= 1
    # "name" is the primary match, but "contact" could also match via the name pattern
    assert "name" in contact_finding.pii_categories or contact_finding.confidence > 0


def test_date_of_birth_variants():
    state = _inline(("V1__dob.sql", """
        CREATE TABLE PERSON (
            ID NUMBER PRIMARY KEY,
            DOB DATE,
            BIRTH_DATE DATE,
            DATE_OF_BIRTH DATE
        );
    """))
    result = scan_pii(state)

    flagged = {f.column_name for f in result.findings}
    assert "DOB" in flagged
    assert "BIRTH_DATE" in flagged
    assert "DATE_OF_BIRTH" in flagged

    for f in result.findings:
        assert "date_of_birth" in f.pii_categories


def test_ssn_detection():
    state = _inline(("V1__ssn.sql", """
        CREATE TABLE TAX (
            ID NUMBER PRIMARY KEY,
            SSN VARCHAR2(11),
            TAX_ID VARCHAR2(20),
            NATIONAL_ID VARCHAR2(20)
        );
    """))
    result = scan_pii(state)

    flagged = {f.column_name for f in result.findings}
    assert "SSN" in flagged
    assert "TAX_ID" in flagged
    assert "NATIONAL_ID" in flagged

    ssn = next(f for f in result.findings if f.column_name == "SSN")
    assert ssn.confidence == 1.0


def test_password_component():
    state = _inline(("V1__pwd.sql", """
        CREATE TABLE AUTH (
            ID NUMBER PRIMARY KEY,
            PASSWORD_HASH VARCHAR2(256)
        );
    """))
    result = scan_pii(state)

    pwd = next(f for f in result.findings if f.column_name == "PASSWORD_HASH")
    assert pwd is not None
    assert "password" in pwd.pii_categories
    # PASSWORD_HASH has "password" as a component → 0.8
    assert pwd.confidence == 0.8
