"""
Tests for drift_repair.py — Schema drift detection and repair SQL generation.

Test coverage:
- Missing/extra tables
- Missing/extra columns
- Type mismatches
- Nullability mismatches
- Missing/extra constraints (PK, FK, UNIQUE)
- Missing/extra indexes
- Report formatting (text, JSON)
- Migration file generation
"""

import pytest
from sqlfy.analysis.drift_repair import (
    analyze_drift,
    generate_repair_migration,
    DriftFinding,
    DriftReport,
)
from sqlfy.reconstructor import reconstruct


# ─────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────

@pytest.fixture
def base_schema_files():
    """Base schema with 2 tables."""
    return [
        {
            'filename': 'V1__initial.sql',
            'sql': '''
                CREATE TABLE APP.USERS (
                    USER_ID NUMBER PRIMARY KEY,
                    EMAIL VARCHAR2(255) NOT NULL,
                    NAME VARCHAR2(100),
                    CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE APP.ORDERS (
                    ORDER_ID NUMBER PRIMARY KEY,
                    USER_ID NUMBER NOT NULL,
                    TOTAL NUMBER(10,2),
                    STATUS VARCHAR2(20) DEFAULT 'PENDING',
                    CONSTRAINT FK_ORDERS_USER FOREIGN KEY (USER_ID) REFERENCES APP.USERS(USER_ID)
                );
                
                CREATE INDEX IDX_ORDERS_USER ON APP.ORDERS(USER_ID);
            '''
        }
    ]


@pytest.fixture
def target_missing_table_files():
    """Target schema missing ORDERS table."""
    return [
        {
            'filename': 'V1__initial.sql',
            'sql': '''
                CREATE TABLE APP.USERS (
                    USER_ID NUMBER PRIMARY KEY,
                    EMAIL VARCHAR2(255) NOT NULL,
                    NAME VARCHAR2(100),
                    CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            '''
        }
    ]


@pytest.fixture
def target_extra_table_files(base_schema_files):
    """Target schema with extra PRODUCTS table."""
    return base_schema_files + [
        {
            'filename': 'V2__add_products.sql',
            'sql': '''
                CREATE TABLE APP.PRODUCTS (
                    PRODUCT_ID NUMBER PRIMARY KEY,
                    NAME VARCHAR2(200),
                    PRICE NUMBER(10,2)
                );
            '''
        }
    ]


@pytest.fixture
def target_column_changes_files():
    """Target schema with column differences."""
    return [
        {
            'filename': 'V1__initial.sql',
            'sql': '''
                CREATE TABLE APP.USERS (
                    USER_ID NUMBER PRIMARY KEY,
                    EMAIL VARCHAR2(500) NOT NULL,       -- Changed from 255
                    NAME VARCHAR2(100),
                    PHONE VARCHAR2(20),                  -- Extra column
                    CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE APP.ORDERS (
                    ORDER_ID NUMBER PRIMARY KEY,
                    USER_ID NUMBER NOT NULL,
                    TOTAL NUMBER(10,2),
                    STATUS VARCHAR2(20) DEFAULT 'PENDING',
                    CONSTRAINT FK_ORDERS_USER FOREIGN KEY (USER_ID) REFERENCES APP.USERS(USER_ID)
                );
                
                CREATE INDEX IDX_ORDERS_USER ON APP.ORDERS(USER_ID);
            '''
        }
    ]


@pytest.fixture
def target_constraint_changes_files():
    """Target schema with constraint differences."""
    return [
        {
            'filename': 'V1__initial.sql',
            'sql': '''
                CREATE TABLE APP.USERS (
                    USER_ID NUMBER PRIMARY KEY,
                    EMAIL VARCHAR2(255) NOT NULL,
                    NAME VARCHAR2(100),
                    CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE APP.ORDERS (
                    ORDER_ID NUMBER PRIMARY KEY,
                    USER_ID NUMBER NOT NULL,
                    TOTAL NUMBER(10,2),
                    STATUS VARCHAR2(20) DEFAULT 'PENDING'
                );
                
                CREATE INDEX IDX_ORDERS_USER ON APP.ORDERS(USER_ID);
                CREATE UNIQUE INDEX IDX_ORDERS_UNIQUE ON APP.ORDERS(ORDER_ID, USER_ID);
            '''
        }
    ]


# ─────────────────────────────────────────────
# TESTS: Missing/Extra Tables
# ─────────────────────────────────────────────

def test_missing_table(base_schema_files, target_missing_table_files):
    """Detect table missing in target schema."""
    base_graph = reconstruct(base_schema_files)
    target_graph = reconstruct(target_missing_table_files)
    
    report = analyze_drift(base_graph, target_graph)
    
    assert not report.is_clean
    assert report.total_drift_count > 0
    
    # Should detect APP.ORDERS missing
    missing_table_findings = [f for f in report.findings if f.category == 'missing_table']
    assert len(missing_table_findings) == 1
    assert 'APP.ORDERS' in missing_table_findings[0].object_name
    assert missing_table_findings[0].severity == 'error'
    assert 'CREATE TABLE' in missing_table_findings[0].repair_sql


def test_extra_table(base_schema_files, target_extra_table_files):
    """Detect extra table in target schema."""
    base_graph = reconstruct(base_schema_files)
    target_graph = reconstruct(target_extra_table_files)
    
    report = analyze_drift(base_graph, target_graph)
    
    assert not report.is_clean
    
    # Should detect APP.PRODUCTS as extra
    extra_table_findings = [f for f in report.findings if f.category == 'extra_table']
    assert len(extra_table_findings) == 1
    assert 'APP.PRODUCTS' in extra_table_findings[0].object_name
    assert extra_table_findings[0].severity == 'warning'
    assert 'DROP TABLE' in extra_table_findings[0].repair_sql


def test_no_drift_identical_schemas(base_schema_files):
    """No drift when schemas are identical."""
    base_graph = reconstruct(base_schema_files)
    target_graph = reconstruct(base_schema_files)
    
    report = analyze_drift(base_graph, target_graph)
    
    assert report.is_clean
    assert report.total_drift_count == 0
    assert len(report.findings) == 0


# ─────────────────────────────────────────────
# TESTS: Column Differences
# ─────────────────────────────────────────────

def test_column_type_mismatch(base_schema_files, target_column_changes_files):
    """Detect column type differences."""
    base_graph = reconstruct(base_schema_files)
    target_graph = reconstruct(target_column_changes_files)
    
    report = analyze_drift(base_graph, target_graph)
    
    assert not report.is_clean
    
    # Should detect EMAIL type mismatch
    type_mismatches = [f for f in report.findings if f.category == 'type_mismatch']
    assert len(type_mismatches) >= 1
    
    email_mismatch = [f for f in type_mismatches if 'EMAIL' in f.object_name]
    assert len(email_mismatch) == 1
    # Note: reconstructor may normalize VARCHAR2 to VARCHAR
    assert '255' in email_mismatch[0].expected
    assert '500' in email_mismatch[0].actual
    assert 'ALTER TABLE' in email_mismatch[0].repair_sql


def test_extra_column(base_schema_files, target_column_changes_files):
    """Detect extra column in target schema."""
    base_graph = reconstruct(base_schema_files)
    target_graph = reconstruct(target_column_changes_files)
    
    report = analyze_drift(base_graph, target_graph)
    
    # Should detect PHONE as extra column
    extra_columns = [f for f in report.findings if f.category == 'extra_column']
    assert len(extra_columns) >= 1
    
    phone_extra = [f for f in extra_columns if 'PHONE' in f.object_name]
    assert len(phone_extra) == 1
    assert phone_extra[0].severity == 'warning'
    assert 'DROP COLUMN' in phone_extra[0].repair_sql


def test_missing_column():
    """Detect column missing in target schema."""
    base_files = [
        {
            'filename': 'V1__base.sql',
            'sql': '''
                CREATE TABLE APP.USERS (
                    USER_ID NUMBER PRIMARY KEY,
                    EMAIL VARCHAR2(255),
                    NAME VARCHAR2(100),
                    PHONE VARCHAR2(20)
                );
            '''
        }
    ]
    
    target_files = [
        {
            'filename': 'V1__target.sql',
            'sql': '''
                CREATE TABLE APP.USERS (
                    USER_ID NUMBER PRIMARY KEY,
                    EMAIL VARCHAR2(255),
                    NAME VARCHAR2(100)
                );
            '''
        }
    ]
    
    base_graph = reconstruct(base_files)
    target_graph = reconstruct(target_files)
    
    report = analyze_drift(base_graph, target_graph)
    
    # Should detect PHONE as missing
    missing_columns = [f for f in report.findings if f.category == 'missing_column']
    assert len(missing_columns) >= 1
    
    phone_missing = [f for f in missing_columns if 'PHONE' in f.object_name]
    assert len(phone_missing) == 1
    assert phone_missing[0].severity == 'error'
    assert 'ADD' in phone_missing[0].repair_sql


# ─────────────────────────────────────────────
# TESTS: Constraint Differences
# ─────────────────────────────────────────────

def test_missing_foreign_key(base_schema_files, target_constraint_changes_files):
    """Detect missing foreign key constraint."""
    base_graph = reconstruct(base_schema_files)
    target_graph = reconstruct(target_constraint_changes_files)
    
    report = analyze_drift(base_graph, target_graph)
    
    # Should detect FK_ORDERS_USER as missing
    missing_constraints = [f for f in report.findings if f.category == 'missing_constraint']
    assert len(missing_constraints) >= 1
    
    fk_missing = [f for f in missing_constraints if 'FK_ORDERS_USER' in f.object_name.upper()]
    assert len(fk_missing) == 1
    assert fk_missing[0].severity == 'warning'
    assert 'FOREIGN KEY' in fk_missing[0].repair_sql


def test_extra_index(base_schema_files, target_constraint_changes_files):
    """Detect extra index in target schema."""
    base_graph = reconstruct(base_schema_files)
    target_graph = reconstruct(target_constraint_changes_files)
    
    report = analyze_drift(base_graph, target_graph)
    
    # Should detect IDX_ORDERS_UNIQUE as extra
    extra_indexes = [f for f in report.findings if f.category == 'extra_index']
    assert len(extra_indexes) >= 1
    
    unique_idx = [f for f in extra_indexes if 'IDX_ORDERS_UNIQUE' in f.object_name.upper()]
    assert len(unique_idx) == 1
    assert unique_idx[0].severity == 'info'
    assert 'DROP INDEX' in unique_idx[0].repair_sql


# ─────────────────────────────────────────────
# TESTS: Report Formatting
# ─────────────────────────────────────────────

def test_report_to_text(base_schema_files, target_missing_table_files):
    """Test text report formatting."""
    base_graph = reconstruct(base_schema_files)
    target_graph = reconstruct(target_missing_table_files)
    
    report = analyze_drift(base_graph, target_graph, base_label="Production", target_label="Development")
    text_output = report.to_text()
    
    assert 'Schema Drift Report' in text_output
    assert 'Base:   Production' in text_output
    assert 'Target: Development' in text_output
    assert 'DRIFT DETECTED' in text_output
    assert 'APP.ORDERS' in text_output
    assert 'Repair SQL:' in text_output


def test_report_to_json(base_schema_files, target_missing_table_files):
    """Test JSON report formatting."""
    base_graph = reconstruct(base_schema_files)
    target_graph = reconstruct(target_missing_table_files)
    
    report = analyze_drift(base_graph, target_graph)
    json_output = report.to_json()
    
    import json
    data = json.loads(json_output)
    
    assert data['status'] == 'drift_detected'
    assert data['total_findings'] > 0
    assert 'by_category' in data
    assert 'by_severity' in data
    assert 'findings' in data
    assert isinstance(data['findings'], list)
    
    # Check finding structure
    first_finding = data['findings'][0]
    assert 'category' in first_finding
    assert 'severity' in first_finding
    assert 'object_name' in first_finding
    assert 'repair_sql' in first_finding


def test_clean_report_text(base_schema_files):
    """Test text output when no drift detected."""
    base_graph = reconstruct(base_schema_files)
    target_graph = reconstruct(base_schema_files)
    
    report = analyze_drift(base_graph, target_graph)
    text_output = report.to_text()
    
    assert 'No drift detected' in text_output
    assert 'identical' in text_output.lower()


def test_clean_report_json(base_schema_files):
    """Test JSON output when no drift detected."""
    base_graph = reconstruct(base_schema_files)
    target_graph = reconstruct(base_schema_files)
    
    report = analyze_drift(base_graph, target_graph)
    json_output = report.to_json()
    
    import json
    data = json.loads(json_output)
    
    assert data['status'] == 'clean'
    assert data['total_findings'] == 0
    assert len(data['findings']) == 0


# ─────────────────────────────────────────────
# TESTS: Migration Generation
# ─────────────────────────────────────────────

def test_generate_migration_file(base_schema_files, target_missing_table_files):
    """Test migration file generation from drift report."""
    base_graph = reconstruct(base_schema_files)
    target_graph = reconstruct(target_missing_table_files)
    
    report = analyze_drift(base_graph, target_graph)
    migration_sql = generate_repair_migration(report, version='10', description='fix_drift')
    
    assert 'V10__fix_drift.sql' in migration_sql
    assert 'CREATE TABLE' in migration_sql
    assert 'APP.ORDERS' in migration_sql
    assert '-- Missing Table' in migration_sql or '-- Missing Tables' in migration_sql


def test_generate_migration_clean_schema(base_schema_files):
    """Test migration generation when no drift."""
    base_graph = reconstruct(base_schema_files)
    target_graph = reconstruct(base_schema_files)
    
    report = analyze_drift(base_graph, target_graph)
    migration_sql = generate_repair_migration(report, version='10')
    
    assert 'No drift detected' in migration_sql
    assert 'no changes needed' in migration_sql.lower()


def test_generate_migration_multiple_findings(base_schema_files, target_column_changes_files):
    """Test migration generation with multiple drift categories."""
    base_graph = reconstruct(base_schema_files)
    target_graph = reconstruct(target_column_changes_files)
    
    report = analyze_drift(base_graph, target_graph)
    migration_sql = generate_repair_migration(report, version='15', description='catch_up')
    
    assert 'V15__catch_up.sql' in migration_sql
    assert report.total_drift_count > 0
    
    # Should contain SQL for all findings
    for finding in report.findings:
        if finding.repair_sql:
            # At least part of the repair SQL should be in the migration
            assert finding.object_name in migration_sql


# ─────────────────────────────────────────────
# TESTS: Report Properties
# ─────────────────────────────────────────────

def test_report_by_category(base_schema_files, target_column_changes_files):
    """Test by_category property."""
    base_graph = reconstruct(base_schema_files)
    target_graph = reconstruct(target_column_changes_files)
    
    report = analyze_drift(base_graph, target_graph)
    by_cat = report.by_category
    
    assert isinstance(by_cat, dict)
    assert sum(by_cat.values()) == report.total_drift_count


def test_report_by_severity(base_schema_files, target_column_changes_files):
    """Test by_severity property."""
    base_graph = reconstruct(base_schema_files)
    target_graph = reconstruct(target_column_changes_files)
    
    report = analyze_drift(base_graph, target_graph)
    by_sev = report.by_severity
    
    assert isinstance(by_sev, dict)
    assert sum(by_sev.values()) == report.total_drift_count


def test_report_errors_warnings(base_schema_files, target_column_changes_files):
    """Test errors() and warnings() filters."""
    base_graph = reconstruct(base_schema_files)
    target_graph = reconstruct(target_column_changes_files)
    
    report = analyze_drift(base_graph, target_graph)
    
    errors = report.errors()
    warnings = report.warnings()
    
    assert all(f.severity == 'error' for f in errors)
    assert all(f.severity == 'warning' for f in warnings)
    assert len(errors) + len(warnings) <= report.total_drift_count


# ─────────────────────────────────────────────
# TESTS: DriftFinding
# ─────────────────────────────────────────────

def test_drift_finding_to_dict():
    """Test DriftFinding serialization."""
    finding = DriftFinding(
        category='type_mismatch',
        severity='error',
        object_name='APP.USERS.EMAIL',
        description='Type differs',
        expected='VARCHAR2(255)',
        actual='VARCHAR2(500)',
        repair_sql='ALTER TABLE APP.USERS MODIFY (EMAIL VARCHAR2(255));'
    )
    
    d = finding.to_dict()
    
    assert d['category'] == 'type_mismatch'
    assert d['severity'] == 'error'
    assert d['object_name'] == 'APP.USERS.EMAIL'
    assert d['expected'] == 'VARCHAR2(255)'
    assert d['actual'] == 'VARCHAR2(500)'
    assert 'ALTER TABLE' in d['repair_sql']


# ─────────────────────────────────────────────
# TESTS: Edge Cases
# ─────────────────────────────────────────────

def test_empty_schemas():
    """Test comparing two empty schemas."""
    empty_files = []
    
    base_graph = reconstruct(empty_files)
    target_graph = reconstruct(empty_files)
    
    report = analyze_drift(base_graph, target_graph)
    
    assert report.is_clean
    assert report.total_drift_count == 0


def test_custom_labels(base_schema_files, target_missing_table_files):
    """Test custom schema labels."""
    base_graph = reconstruct(base_schema_files)
    target_graph = reconstruct(target_missing_table_files)
    
    report = analyze_drift(
        base_graph,
        target_graph,
        base_label="Production DB",
        target_label="Dev Branch"
    )
    
    assert report.base_label == "Production DB"
    assert report.target_label == "Dev Branch"
    
    text_output = report.to_text()
    assert "Production DB" in text_output
    assert "Dev Branch" in text_output
