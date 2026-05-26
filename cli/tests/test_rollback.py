"""
test_rollback.py
================
Tests for rollback feasibility analysis module (Feature #22).
"""

from sqlfy.analysis.rollback import (
    analyze_rollback_feasibility,
    analyze_migrations,
    format_rollback_text,
    format_rollback_json,
    RollbackAnalysis,
)
import json


# ─────────────────────────────────────────────
# Basic Analysis Tests
# ─────────────────────────────────────────────

def test_reversible_create_table():
    """Test CREATE TABLE is classified as reversible with rollback script."""
    sql = """
    CREATE TABLE users (
        id NUMBER PRIMARY KEY,
        name VARCHAR2(255)
    );
    """
    
    result = analyze_rollback_feasibility('V1__create_users.sql', sql)
    
    assert result.feasibility == 'partial'  # CREATE TABLE has data loss warning
    assert result.score >= 80
    assert result.rollback_script is not None
    assert 'DROP TABLE USERS' in result.rollback_script
    assert len(result.warnings) > 0
    assert any('data will be lost' in w for w in result.warnings)


def test_reversible_add_column():
    """Test ADD COLUMN is classified as partially reversible."""
    sql = "ALTER TABLE users ADD COLUMN email VARCHAR2(255);"
    
    result = analyze_rollback_feasibility('V2__add_email.sql', sql)
    
    assert result.feasibility == 'partial'
    assert result.score >= 70
    assert result.rollback_script is not None
    assert 'DROP COLUMN' in result.rollback_script.upper()
    assert any('data will be lost' in w for w in result.warnings)


def test_irreversible_drop_table():
    """Test DROP TABLE is classified as irreversible."""
    sql = "DROP TABLE old_logs;"
    
    result = analyze_rollback_feasibility('V3__drop_old_logs.sql', sql)
    
    assert result.feasibility == 'irreversible'
    assert result.score == 0
    assert result.rollback_script is None
    assert any('Cannot restore' in w for w in result.warnings)


def test_irreversible_drop_column():
    """Test DROP COLUMN is classified as irreversible."""
    sql = "ALTER TABLE users DROP COLUMN temp_field;"
    
    result = analyze_rollback_feasibility('V4__drop_column.sql', sql)
    
    assert result.feasibility == 'irreversible'
    assert result.score == 0
    assert result.rollback_script is None
    assert any('Cannot restore' in w for w in result.warnings)


def test_irreversible_delete():
    """Test DELETE is classified as irreversible."""
    sql = "DELETE FROM logs WHERE created_at < '2025-01-01';"
    
    result = analyze_rollback_feasibility('V5__cleanup.sql', sql)
    
    assert result.feasibility == 'irreversible'
    assert result.score == 0
    assert result.rollback_script is None
    assert any('Cannot undo DELETE' in w for w in result.warnings)


def test_irreversible_update():
    """Test UPDATE is classified as irreversible."""
    sql = "UPDATE users SET status = 'active' WHERE status IS NULL;"
    
    result = analyze_rollback_feasibility('V6__update_status.sql', sql)
    
    assert result.feasibility == 'irreversible'
    assert result.score == 0
    assert result.rollback_script is None
    assert any('Cannot undo UPDATE' in w for w in result.warnings)


def test_irreversible_insert():
    """Test INSERT is classified as irreversible."""
    sql = "INSERT INTO defaults (key, value) VALUES ('timeout', '30');"
    
    result = analyze_rollback_feasibility('V7__add_defaults.sql', sql)
    
    assert result.feasibility == 'irreversible'
    assert result.score == 0
    assert result.rollback_script is None
    assert any('Cannot undo INSERT' in w for w in result.warnings)


def test_irreversible_truncate():
    """Test TRUNCATE is classified as irreversible."""
    sql = "TRUNCATE TABLE staging_data;"
    
    result = analyze_rollback_feasibility('V8__truncate.sql', sql)
    
    assert result.feasibility == 'irreversible'
    assert result.score == 0
    assert result.rollback_script is None
    assert any('Cannot undo TRUNCATE' in w for w in result.warnings)


# ─────────────────────────────────────────────
# Complex Scenarios
# ─────────────────────────────────────────────

def test_multiple_operations_mixed():
    """Test migration with multiple operations of different reversibility."""
    sql = """
    CREATE TABLE orders (
        id NUMBER PRIMARY KEY,
        user_id NUMBER
    );
    
    DELETE FROM old_orders WHERE created_at < '2024-01-01';
    """
    
    result = analyze_rollback_feasibility('V9__mixed.sql', sql)
    
    # DELETE makes it irreversible
    assert result.feasibility == 'irreversible'
    assert result.score == 0
    assert result.rollback_script is None  # Cannot rollback due to DELETE


def test_create_view_reversible():
    """Test CREATE VIEW is reversible."""
    sql = """
    CREATE VIEW active_users AS
    SELECT * FROM users WHERE status = 'active';
    """
    
    result = analyze_rollback_feasibility('V10__create_view.sql', sql)
    
    assert result.feasibility == 'reversible'
    assert result.score >= 90
    assert result.rollback_script is not None
    assert 'DROP VIEW' in result.rollback_script


def test_create_index_partial():
    """Test CREATE INDEX is partially reversible."""
    sql = "CREATE INDEX idx_users_email ON users(email);"
    
    result = analyze_rollback_feasibility('V11__add_index.sql', sql)
    
    assert result.feasibility in ['reversible', 'partial']
    assert result.score >= 70
    assert result.rollback_script is not None
    assert 'DROP INDEX' in result.rollback_script.upper()


def test_create_sequence_partial():
    """Test CREATE SEQUENCE is partially reversible."""
    sql = "CREATE SEQUENCE seq_users START WITH 1;"
    
    result = analyze_rollback_feasibility('V12__add_sequence.sql', sql)
    
    assert result.feasibility in ['reversible', 'partial']
    assert result.score >= 70
    assert result.rollback_script is not None
    assert 'DROP SEQUENCE' in result.rollback_script.upper()


def test_add_foreign_key_reversible():
    """Test ADD FOREIGN KEY is reversible."""
    sql = """
    ALTER TABLE orders
    ADD CONSTRAINT fk_user
    FOREIGN KEY (user_id) REFERENCES users(id);
    """
    
    result = analyze_rollback_feasibility('V13__add_fk.sql', sql)
    
    # FKs are safe to add/remove
    assert result.feasibility in ['reversible', 'partial']
    assert result.score >= 80


def test_modify_column_irreversible():
    """Test MODIFY column is irreversible."""
    sql = "ALTER TABLE users MODIFY (email VARCHAR2(500));"
    
    result = analyze_rollback_feasibility('V14__modify_email.sql', sql)
    
    # MODIFY is irreversible (can't restore original definition)
    assert result.feasibility == 'irreversible'
    assert result.score == 0
    assert any('MODIFY' in w for w in result.warnings)


# ─────────────────────────────────────────────
# Batch Analysis Tests
# ─────────────────────────────────────────────

def test_analyze_multiple_migrations():
    """Test analyzing multiple migrations in batch."""
    files = [
        {'filename': 'V1__create.sql', 'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
        {'filename': 'V2__alter.sql', 'sql': 'ALTER TABLE users ADD COLUMN email VARCHAR2(255);'},
        {'filename': 'V3__delete.sql', 'sql': 'DELETE FROM users WHERE id = 0;'},
    ]
    
    results = analyze_migrations(files)
    
    assert len(results) == 3
    assert results[0].feasibility == 'partial'  # CREATE TABLE
    assert results[1].feasibility == 'partial'  # ADD COLUMN
    assert results[2].feasibility == 'irreversible'  # DELETE


# ─────────────────────────────────────────────
# Format Tests
# ─────────────────────────────────────────────

def test_format_text_output():
    """Test text format output."""
    files = [
        {'filename': 'V1__create.sql', 'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
        {'filename': 'V2__delete.sql', 'sql': 'DELETE FROM old_data;'},
    ]
    
    results = analyze_migrations(files)
    output = format_rollback_text(results)
    
    assert 'Rollback Feasibility Analysis' in output
    assert 'V1__create.sql' in output
    assert 'V2__delete.sql' in output
    assert 'PARTIAL' in output or 'REVERSIBLE' in output
    assert 'IRREVERSIBLE' in output
    assert 'Total migrations: 2' in output


def test_format_json_output():
    """Test JSON format output."""
    files = [
        {'filename': 'V1__create.sql', 'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
        {'filename': 'V2__delete.sql', 'sql': 'DELETE FROM old_data;'},
    ]
    
    results = analyze_migrations(files)
    output = format_rollback_json(results)
    data = json.loads(output)
    
    assert 'summary' in data
    assert 'migrations' in data
    assert data['summary']['total'] == 2
    assert len(data['migrations']) == 2
    assert data['migrations'][0]['migration'] == 'V1__create.sql'
    assert data['migrations'][1]['feasibility'] == 'irreversible'


# ─────────────────────────────────────────────
# RollbackAnalysis Model Tests
# ─────────────────────────────────────────────

def test_rollback_analysis_to_dict():
    """Test RollbackAnalysis.to_dict() serialization."""
    analysis = RollbackAnalysis(
        migration='V1__test.sql',
        feasibility='reversible',
        score=95,
        rollback_script='DROP TABLE test;',
        warnings=['Test warning'],
        recommendations=['Test recommendation'],
        operations=['CREATE TABLE test'],
    )
    
    data = analysis.to_dict()
    
    assert data['migration'] == 'V1__test.sql'
    assert data['feasibility'] == 'reversible'
    assert data['score'] == 95
    assert data['rollback_script'] == 'DROP TABLE test;'
    assert len(data['warnings']) == 1
    assert len(data['recommendations']) == 1
    assert len(data['operations']) == 1


# ─────────────────────────────────────────────
# Edge Cases
# ─────────────────────────────────────────────

def test_empty_sql():
    """Test empty SQL content."""
    result = analyze_rollback_feasibility('V1__empty.sql', '')
    
    assert result.feasibility == 'reversible'
    assert result.score == 95
    assert result.rollback_script is None or result.rollback_script == ''


def test_comments_only():
    """Test SQL with only comments."""
    sql = """
    -- This is a comment
    /* Multi-line
       comment */
    """
    
    result = analyze_rollback_feasibility('V1__comments.sql', sql)
    
    assert result.feasibility == 'reversible'
    assert result.score == 95


def test_malformed_sql():
    """Test malformed SQL falls back gracefully."""
    sql = "CREATE TABEL users (id NUMBER);"  # Typo: TABEL
    
    result = analyze_rollback_feasibility('V1__malformed.sql', sql)
    
    # Should not crash, should return some result
    assert result.migration == 'V1__malformed.sql'
    assert result.feasibility in ['reversible', 'partial', 'irreversible']


def test_case_insensitive():
    """Test SQL keywords are case-insensitive."""
    sql_upper = "CREATE TABLE USERS (ID NUMBER);"
    sql_lower = "create table users (id number);"
    sql_mixed = "CrEaTe TaBlE uSeRs (Id NuMbEr);"
    
    result_upper = analyze_rollback_feasibility('V1.sql', sql_upper)
    result_lower = analyze_rollback_feasibility('V1.sql', sql_lower)
    result_mixed = analyze_rollback_feasibility('V1.sql', sql_mixed)
    
    assert result_upper.feasibility == result_lower.feasibility == result_mixed.feasibility
    assert result_upper.score == result_lower.score == result_mixed.score


def test_multiple_statements_in_one_file():
    """Test file with multiple SQL statements."""
    sql = """
    CREATE TABLE users (id NUMBER PRIMARY KEY);
    CREATE TABLE orders (id NUMBER PRIMARY KEY);
    CREATE INDEX idx_orders ON orders(id);
    """
    
    result = analyze_rollback_feasibility('V1__multi.sql', sql)
    
    assert result.feasibility in ['reversible', 'partial']
    assert result.rollback_script is not None
    assert result.rollback_script.count('DROP') >= 3  # Should drop all 3 objects


def test_drop_view_irreversible():
    """Test DROP VIEW is irreversible."""
    sql = "DROP VIEW active_users;"
    
    result = analyze_rollback_feasibility('V1__drop_view.sql', sql)
    
    assert result.feasibility == 'irreversible'
    assert result.score == 0


def test_drop_index_irreversible():
    """Test DROP INDEX is irreversible."""
    sql = "DROP INDEX idx_users_email;"
    
    result = analyze_rollback_feasibility('V1__drop_index.sql', sql)
    
    assert result.feasibility == 'irreversible'
    assert result.score == 0


def test_drop_sequence_irreversible():
    """Test DROP SEQUENCE is irreversible."""
    sql = "DROP SEQUENCE seq_users;"
    
    result = analyze_rollback_feasibility('V1__drop_seq.sql', sql)
    
    assert result.feasibility == 'irreversible'
    assert result.score == 0
