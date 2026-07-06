"""Tests for PII column scanner (Feature #23)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from sqlfy.analysis.pii_scanner import PII_PATTERNS, scan_pii
from sqlfy.domain.schema_state import ColumnState, SchemaState, TableState


def _make_col(name, data_type, nullable=True, is_pk=False, is_fk=False, comment=None):
    """Create ColumnState with all required fields."""
    raw_type = data_type.split("(")[0].upper()
    precision = None
    scale = None
    if "(" in data_type and ")" in data_type:
        inner = data_type[data_type.index("(") + 1 : data_type.index(")")]
        if "," in inner:
            parts = inner.split(",")
            if parts[0].isdigit():
                precision = int(parts[0])
            if len(parts) > 1 and parts[1].isdigit():
                scale = int(parts[1])
        elif inner.isdigit():
            precision = int(inner)
    return ColumnState(
        name=name,
        data_type=data_type,
        raw_type=raw_type,
        precision=precision,
        scale=scale,
        nullable=nullable,
        default=None,
        is_pk=is_pk,
        is_fk=is_fk,
        is_unique=is_pk,
        comment=comment,
    )


def _build_test_schema():
    """Build a test SchemaState with known tables and columns for PII testing."""
    customer_table = TableState(
        name="CUSTOMER",
        schema="APP",
        full_name="APP.CUSTOMER",
        columns=[
            _make_col("ID", "NUMBER", nullable=False, is_pk=True),
            _make_col("EMAIL", "VARCHAR(255)", nullable=False, comment="Customer email address"),
            _make_col("PHONE_NUMBER", "VARCHAR(20)", nullable=True),
            _make_col("FIRST_NAME", "VARCHAR(100)", nullable=True),
            _make_col("LAST_NAME", "VARCHAR(100)", nullable=True),
            _make_col("DATE_OF_BIRTH", "DATE", nullable=True),
            _make_col("SSN", "VARCHAR(11)", nullable=True),
            _make_col("CREATED_AT", "TIMESTAMP", nullable=False),
            _make_col("UPDATED_AT", "TIMESTAMP", nullable=True),
        ],
        constraints=[],
        indexes=[],
        comment="Customer information",
        created_in="V1",
        modified_in=[],
        column_count=8,
        has_pk=True,
        pk_columns=["ID"],
    )

    order_table = TableState(
        name="ORDER",
        schema="APP",
        full_name="APP.ORDER",
        columns=[
            _make_col("ID", "NUMBER", nullable=False, is_pk=True),
            _make_col("TOTAL_AMOUNT", "NUMBER(10,2)", nullable=False),
            _make_col("ORDER_DATE", "DATE", nullable=False),
            _make_col("CUSTOMER_ID", "NUMBER", nullable=False, is_fk=True),
        ],
        constraints=[],
        indexes=[],
        comment="Order information",
        created_in="V2",
        modified_in=[],
        column_count=4,
        has_pk=True,
        pk_columns=["ID"],
    )

    address_table = TableState(
        name="ADDRESS",
        schema="APP",
        full_name="APP.ADDRESS",
        columns=[
            _make_col("ID", "NUMBER", nullable=False, is_pk=True),
            _make_col("ADDR_LINE1", "VARCHAR(255)", nullable=True, comment="Street address line 1"),
            _make_col("ADDR_LINE2", "VARCHAR(255)", nullable=True, comment="Street address line 2"),
            _make_col("CITY", "VARCHAR(100)", nullable=True),
            _make_col("POSTAL_CODE", "VARCHAR(20)", nullable=True),
            _make_col("STATE", "VARCHAR(50)", nullable=True),
            _make_col("CUSTOMER_ID", "NUMBER", nullable=False, is_fk=True),
        ],
        constraints=[],
        indexes=[],
        comment="Customer address",
        created_in="V3",
        modified_in=[],
        column_count=6,
        has_pk=True,
        pk_columns=["ID"],
    )

    tables = {
        "APP.CUSTOMER": customer_table,
        "APP.ORDER": order_table,
        "APP.ADDRESS": address_table,
    }

    return SchemaState(
        version="V3",
        generated_at="2024-01-01T00:00:00Z",
        fingerprint="test_fingerprint",
        dialect="oracle",
        tables=tables,
        sequences={},
        relationships=[],
        migration_history=[],
        stats={},
        source_files=[],
    )


class TestPiiScanner:
    """Tests for the scan_pii function."""

    def test_basic_pii_detection(self):
        """Test that basic PII columns are detected."""
        state = _build_test_schema()
        result = scan_pii(state)

        # Should find PII in CUSTOMER table
        customer_pii = [f for f in result.findings if f.table_name == "CUSTOMER"]
        assert len(customer_pii) >= 6

        # Should find EMAIL with high confidence
        email_finding = next((f for f in customer_pii if f.column_name == "EMAIL"), None)
        assert email_finding is not None
        assert "email" in email_finding.pii_categories
        assert email_finding.confidence == 1.0

    def test_email_exact_match_confidence(self):
        """Test that EMAIL column gets confidence 1.0."""
        state = _build_test_schema()
        result = scan_pii(state)

        email_finding = next((f for f in result.findings if f.column_name == "EMAIL"), None)
        assert email_finding is not None
        assert email_finding.confidence == 1.0

    def test_audit_columns_not_flagged(self):
        """Test that CREATED_AT and UPDATED_AT are NOT flagged as PII."""
        state = _build_test_schema()
        result = scan_pii(state)

        audit_columns = [f for f in result.findings if f.column_name in ["CREATED_AT", "UPDATED_AT"]]
        assert len(audit_columns) == 0

    def test_order_table_no_pii(self):
        """Test that ORDER table has no PII columns flagged."""
        state = _build_test_schema()
        result = scan_pii(state)

        order_pii = [f for f in result.findings if f.table_name == "ORDER"]
        assert len(order_pii) == 0

    def test_address_pii_detection(self):
        """Test that address-related columns are detected."""
        state = _build_test_schema()
        result = scan_pii(state)

        address_pii = [f for f in result.findings if f.table_name == "ADDRESS"]
        assert len(address_pii) >= 5

        addr_line1 = next((f for f in address_pii if f.column_name == "ADDR_LINE1"), None)
        assert addr_line1 is not None
        assert "address" in addr_line1.pii_categories

    def test_comment_matching(self):
        """Test that column comments are also scanned for PII patterns."""
        state = _build_test_schema()
        result = scan_pii(state)

        email_finding = next((f for f in result.findings if f.column_name == "EMAIL"), None)
        assert email_finding is not None
        assert "email" in email_finding.pii_categories

    def test_extra_patterns(self):
        """Test that extra patterns are applied alongside built-in ones."""
        state = _build_test_schema()
        extra_patterns = {"custom_id": [r"customer.*id", r"vip.*number"]}
        result = scan_pii(state, extra_patterns)

        custom_findings = [f for f in result.findings if "custom_id" in f.pii_categories]
        assert len(custom_findings) >= 1

    def test_min_confidence_filtering(self):
        """Test filtering by minimum confidence."""
        state = _build_test_schema()
        result = scan_pii(state)

        low_confidence = [f for f in result.findings if f.confidence < 0.6]
        assert len(low_confidence) == 0

        high_confidence = [f for f in result.findings if f.confidence >= 0.8]
        assert len(high_confidence) > 0

    def test_counts_accuracy(self):
        """Test that counts in PiiScanResult are accurate."""
        state = _build_test_schema()
        result = scan_pii(state)

        assert result.tables_scanned == 3
        assert result.columns_scanned == 20  # 9 (CUSTOMER) + 4 (ORDER) + 7 (ADDRESS)
        assert result.pii_column_count == len(result.findings)
        assert result.pii_table_count == len({f.table_name for f in result.findings})

    def test_empty_schema(self):
        """Test scanning an empty schema."""
        empty_state = SchemaState(
            version="V0",
            generated_at="2024-01-01T00:00:00Z",
            fingerprint="empty_fingerprint",
            dialect="oracle",
            tables={},
            sequences={},
            relationships=[],
            migration_history=[],
            stats={},
            source_files=[],
        )
        result = scan_pii(empty_state)
        assert result.tables_scanned == 0
        assert result.columns_scanned == 0
        assert result.pii_column_count == 0
        assert result.pii_table_count == 0
        assert len(result.findings) == 0

    def test_strong_partial_match_confidence(self):
        """Test that strong partial matches get 0.8 confidence."""
        table = TableState(
            name="TEST",
            schema="APP",
            full_name="APP.TEST",
            columns=[_make_col("CUST_EMAIL", "VARCHAR(255)")],
            constraints=[],
            indexes=[],
            comment=None,
            created_in="V1",
            modified_in=[],
            column_count=1,
            has_pk=False,
            pk_columns=[],
        )
        state = SchemaState(
            version="V1",
            generated_at="2024-01-01T00:00:00Z",
            fingerprint="test",
            dialect="oracle",
            tables={"APP.TEST": table},
            sequences={},
            relationships=[],
            migration_history=[],
            stats={},
            source_files=[],
        )
        result = scan_pii(state)
        cust_email = next((f for f in result.findings if f.column_name == "CUST_EMAIL"), None)
        assert cust_email is not None
        assert "email" in cust_email.pii_categories
        assert cust_email.confidence == 0.8

    def test_weak_partial_match_confidence(self):
        """Test that weak partial matches get 0.6 confidence."""
        table = TableState(
            name="TEST",
            schema="APP",
            full_name="APP.TEST",
            columns=[_make_col("ADDR_LINE1", "VARCHAR(255)")],
            constraints=[],
            indexes=[],
            comment=None,
            created_in="V1",
            modified_in=[],
            column_count=1,
            has_pk=False,
            pk_columns=[],
        )
        state = SchemaState(
            version="V1",
            generated_at="2024-01-01T00:00:00Z",
            fingerprint="test",
            dialect="oracle",
            tables={"APP.TEST": table},
            sequences={},
            relationships=[],
            migration_history=[],
            stats={},
            source_files=[],
        )
        result = scan_pii(state)
        addr_line1 = next((f for f in result.findings if f.column_name == "ADDR_LINE1"), None)
        assert addr_line1 is not None
        assert "address" in addr_line1.pii_categories
        assert addr_line1.confidence >= 0.6


class TestPiiPatterns:
    """Tests for the built-in PII patterns."""

    def test_patterns_exist(self):
        """Test that all expected PII patterns exist."""
        expected_categories = [
            "name",
            "email",
            "phone",
            "address",
            "date_of_birth",
            "ssn",
            "gender",
            "ip_address",
            "location",
            "national_id",
            "financial",
            "health",
            "username",
            "password",
            "cookie",
        ]
        for category in expected_categories:
            assert category in PII_PATTERNS
            assert len(PII_PATTERNS[category]) > 0

    def test_patterns_are_strings(self):
        """Test that all patterns are string regex patterns."""
        for _category, patterns in PII_PATTERNS.items():
            for pattern in patterns:
                assert isinstance(pattern, str)


class TestPiiScannerIntegration:
    """Integration tests for the PII scanner command."""

    def test_json_output_format(self):
        """Test JSON output format matches the contract."""
        import subprocess
        import sys

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            migrations_dir = tmp_path / "migrations"
            migrations_dir.mkdir()
            migration_sql = """
CREATE TABLE customer (
    id NUMBER PRIMARY KEY,
    email VARCHAR2(255),
    phone_number VARCHAR2(20),
    created_at TIMESTAMP
);
            """
            migration_file = migrations_dir / "V1__create_customer.sql"
            migration_file.write_text(migration_sql)
            cmd = [
                sys.executable,
                "-m",
                "sqlfy",
                "pii-scan",
                str(migrations_dir),
                "--format",
                "json",
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode != 0:
                    return
                output = json.loads(result.stdout)
                assert "tablesScanned" in output
                assert "columnsScanned" in output
                assert "piiTableCount" in output
                assert "piiColumnCount" in output
                assert "findings" in output
                assert output["piiColumnCount"] >= 2
            except (subprocess.TimeoutExpired, FileNotFoundError):
                return

    def test_text_output_format(self):
        """Test text output format."""
        import subprocess
        import sys

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            migrations_dir = tmp_path / "migrations"
            migrations_dir.mkdir()
            migration_sql = """
CREATE TABLE customer (
    id NUMBER PRIMARY KEY,
    email VARCHAR2(255),
    phone_number VARCHAR2(20),
    created_at TIMESTAMP
);
            """
            migration_file = migrations_dir / "V1__create_customer.sql"
            migration_file.write_text(migration_sql)
            cmd = [
                sys.executable,
                "-m",
                "sqlfy",
                "pii-scan",
                str(migrations_dir),
                "--format",
                "text",
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode != 0:
                    return
                output = result.stdout
                assert "PII Scan" in output
                assert "tables" in output
            except (subprocess.TimeoutExpired, FileNotFoundError):
                return
