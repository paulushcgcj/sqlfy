"""
tests.test_insights_migrations
================================
Tests for migration-specific anti-pattern detection (Feature #20).
"""

import pytest
from sqlfy.analysis.insights import InsightsEngine
from sqlfy.reconstructor import reconstruct
from sqlfy.domain.schema_state import SchemaStateBuilder


def test_add_not_null_no_default_detected():
    """Detect ALTER TABLE ADD column with NOT NULL but no DEFAULT."""
    files = [
        {
            'filename': 'V1__create_table.sql',
            'sql': 'CREATE TABLE users (id NUMBER(10) PRIMARY KEY, name VARCHAR2(100));'
        },
        {
            'filename': 'V2__bad_alter.sql',
            'sql': 'ALTER TABLE users ADD (status VARCHAR2(20) NOT NULL);'
        }
    ]
    
    graph = reconstruct(files, dialect='oracle')
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    report = InsightsEngine.analyse(state)
    
    # Should detect ADD_NOT_NULL_NO_DEFAULT
    findings = [f for f in report.findings if f.code == 'ADD_NOT_NULL_NO_DEFAULT']
    assert len(findings) >= 1
    assert findings[0].severity == 'error'
    assert 'status' in findings[0].message


def test_add_not_null_with_default_not_flagged():
    """ALTER TABLE ADD with NOT NULL and DEFAULT should NOT be flagged."""
    files = [
        {
            'filename': 'V1__create_table.sql',
            'sql': 'CREATE TABLE users (id NUMBER(10) PRIMARY KEY, name VARCHAR2(100));'
        },
        {
            'filename': 'V2__good_alter.sql',
            'sql': 'ALTER TABLE users ADD (status VARCHAR2(20) DEFAULT \'active\' NOT NULL);'
        }
    ]
    
    graph = reconstruct(files, dialect='oracle')
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    report = InsightsEngine.analyse(state)
    
    # Should NOT detect ADD_NOT_NULL_NO_DEFAULT
    findings = [f for f in report.findings if f.code == 'ADD_NOT_NULL_NO_DEFAULT']
    assert len(findings) == 0


def test_select_star_view_detected():
    """Detect CREATE VIEW with SELECT * pattern."""
    files = [
        {
            'filename': 'V1__create_tables.sql',
            'sql': '''
                CREATE TABLE users (id NUMBER(10), name VARCHAR2(100));
                CREATE VIEW active_users AS SELECT * FROM users WHERE status = 'active';
            '''
        }
    ]
    
    graph = reconstruct(files, dialect='oracle')
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    report = InsightsEngine.analyse(state)
    
    # Should detect SELECT_STAR_VIEW
    findings = [f for f in report.findings if f.code == 'SELECT_STAR_VIEW']
    assert len(findings) >= 1
    assert findings[0].severity == 'warning'
    assert 'active_users' in findings[0].message


def test_select_star_view_not_detected_without_star():
    """CREATE VIEW with explicit columns should NOT be flagged."""
    files = [
        {
            'filename': 'V1__create_views.sql',
            'sql': '''
                CREATE TABLE users (id NUMBER(10), name VARCHAR2(100));
                CREATE VIEW user_names AS SELECT id, name FROM users;
            '''
        }
    ]
    
    graph = reconstruct(files, dialect='oracle')
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    report = InsightsEngine.analyse(state)
    
    # Should NOT detect SELECT_STAR_VIEW
    findings = [f for f in report.findings if f.code == 'SELECT_STAR_VIEW']
    assert len(findings) == 0


def test_trigger_with_business_logic_detected():
    """Detect complex triggers with business logic."""
    files = [
        {
            'filename': 'V1__create_trigger.sql',
            'sql': '''
                CREATE TABLE orders (id NUMBER(10), status VARCHAR2(20));
                CREATE OR REPLACE TRIGGER order_status_check
                BEFORE INSERT OR UPDATE ON orders
                FOR EACH ROW
                BEGIN
                    IF :NEW.status = 'approved' THEN
                        IF :NEW.amount > 1000 THEN
                            RAISE_APPLICATION_ERROR(-20001, 'Amount too large');
                        END IF;
                        :NEW.approved_date := SYSDATE;
                    ELSIF :NEW.status = 'rejected' THEN
                        :NEW.rejected_date := SYSDATE;
                        :NEW.rejected_by := USER;
                    ELSE
                        CASE :NEW.status
                            WHEN 'pending' THEN :NEW.pending_date := SYSDATE;
                            WHEN 'canceled' THEN :NEW.canceled_date := SYSDATE;
                        END CASE;
                    END IF;
                END;
            '''
        }
    ]
    
    graph = reconstruct(files, dialect='oracle')
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    report = InsightsEngine.analyse(state)
    
    # Should detect TRIGGER_WITH_BUSINESS_LOGIC
    findings = [f for f in report.findings if f.code == 'TRIGGER_WITH_BUSINESS_LOGIC']
    assert len(findings) >= 1
    assert findings[0].severity == 'warning'
    assert 'order_status_check' in findings[0].message


def test_simple_trigger_not_flagged():
    """Simple triggers without complex logic should NOT be flagged."""
    files = [
        {
            'filename': 'V1__simple_trigger.sql',
            'sql': '''
                CREATE TABLE audit_log (id NUMBER(10));
                CREATE TRIGGER audit_insert
                AFTER INSERT ON orders
                FOR EACH ROW
                BEGIN
                    INSERT INTO audit_log (id) VALUES (:NEW.id);
                END;
            '''
        }
    ]
    
    graph = reconstruct(files, dialect='oracle')
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    report = InsightsEngine.analyse(state)
    
    # Should NOT detect TRIGGER_WITH_BUSINESS_LOGIC (too short, no IF/CASE)
    findings = [f for f in report.findings if f.code == 'TRIGGER_WITH_BUSINESS_LOGIC']
    assert len(findings) == 0


def test_large_delete_no_where_detected():
    """Detect DELETE FROM without WHERE clause."""
    files = [
        {
            'filename': 'V1__create_table.sql',
            'sql': 'CREATE TABLE temp_data (id NUMBER(10), value VARCHAR2(100));'
        },
        {
            'filename': 'V2__cleanup.sql',
            'sql': 'DELETE FROM temp_data;'
        }
    ]
    
    graph = reconstruct(files, dialect='oracle')
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    report = InsightsEngine.analyse(state)
    
    # Should detect LARGE_DELETE_NO_WHERE
    findings = [f for f in report.findings if f.code == 'LARGE_DELETE_NO_WHERE']
    assert len(findings) >= 1
    assert findings[0].severity == 'warning'
    assert 'temp_data' in findings[0].message


def test_delete_with_where_not_flagged():
    """DELETE FROM with WHERE clause should NOT be flagged."""
    files = [
        {
            'filename': 'V1__create_table.sql',
            'sql': 'CREATE TABLE users (id NUMBER(10), status VARCHAR2(20));'
        },
        {
            'filename': 'V2__cleanup_old.sql',
            'sql': "DELETE FROM users WHERE status = 'inactive';"
        }
    ]
    
    graph = reconstruct(files, dialect='oracle')
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    report = InsightsEngine.analyse(state)
    
    # Should NOT detect LARGE_DELETE_NO_WHERE
    findings = [f for f in report.findings if f.code == 'LARGE_DELETE_NO_WHERE']
    assert len(findings) == 0


def test_migration_findings_category():
    """Migration-specific findings should have category='migrations'."""
    files = [
        {
            'filename': 'V1__issues.sql',
            'sql': '''
                CREATE TABLE users (id NUMBER(10));
                ALTER TABLE users ADD (status VARCHAR2(20) NOT NULL);
                DELETE FROM users;
            '''
        }
    ]
    
    graph = reconstruct(files, dialect='oracle')
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    report = InsightsEngine.analyse(state)
    
    # All migration-specific findings should have category='migrations'
    migration_findings = [f for f in report.findings if f.code in (
        'ADD_NOT_NULL_NO_DEFAULT', 'SELECT_STAR_VIEW',
        'TRIGGER_WITH_BUSINESS_LOGIC', 'LARGE_DELETE_NO_WHERE'
    )]
    
    for finding in migration_findings:
        assert finding.category == 'migrations'


def test_multiple_migration_antipatterns_in_one_file():
    """Multiple anti-patterns in a single file should all be detected."""
    files = [
        {
            'filename': 'V1__bad_migration.sql',
            'sql': '''
                CREATE TABLE users (id NUMBER(10));
                ALTER TABLE users ADD (status VARCHAR2(20) NOT NULL);
                CREATE VIEW all_users AS SELECT * FROM users;
                DELETE FROM users;
            '''
        }
    ]
    
    graph = reconstruct(files, dialect='oracle')
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    report = InsightsEngine.analyse(state)
    
    # Should detect all three patterns
    codes = {f.code for f in report.findings}
    assert 'ADD_NOT_NULL_NO_DEFAULT' in codes
    assert 'SELECT_STAR_VIEW' in codes
    assert 'LARGE_DELETE_NO_WHERE' in codes
