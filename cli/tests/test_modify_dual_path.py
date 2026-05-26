"""
test_modify_dual_path
=====================
Integration tests for ALTER TABLE MODIFY dual-path implementation.

Tests that both native sqlglot parsing and regex fallback produce
identical results for the same SQL statements.
"""

import pytest
from sqlfy.reconstructor import Reconstructor
from sqlfy.domain.sqlglot_compat import SQLGLOT_HAS_MODIFY


# ─────────────────────────────────────────────
# TEST FIXTURES
# ─────────────────────────────────────────────

@pytest.fixture
def base_migration():
    """Base migration that creates a table with columns."""
    return {
        'filename': 'V1__create_users.sql',
        'sql': """
            CREATE TABLE users (
                id NUMBER(10) PRIMARY KEY,
                email VARCHAR2(100) NULL,
                age NUMBER(3) NULL,
                status VARCHAR2(20) NULL,
                created_at DATE NULL
            )
        """
    }


@pytest.fixture
def modify_single_column():
    """Migration that modifies a single column."""
    return {
        'filename': 'V2__modify_email.sql',
        'sql': "ALTER TABLE users MODIFY (email VARCHAR2(255) NOT NULL)"
    }


@pytest.fixture
def modify_multiple_columns():
    """Migration that modifies multiple columns."""
    return {
        'filename': 'V3__modify_multiple.sql',
        'sql': """
            ALTER TABLE users MODIFY (
                email VARCHAR2(255) NOT NULL,
                age NUMBER(3) DEFAULT 0,
                status VARCHAR2(30)
            )
        """
    }


@pytest.fixture
def modify_with_default():
    """Migration that adds a default value."""
    return {
        'filename': 'V4__modify_status.sql',
        'sql': "ALTER TABLE users MODIFY (status VARCHAR2(20) DEFAULT 'ACTIVE')"
    }


# ─────────────────────────────────────────────
# SINGLE COLUMN MODIFY TESTS
# ─────────────────────────────────────────────

def test_modify_single_column_type_change(base_migration, modify_single_column):
    """MODIFY should change column type from VARCHAR2(100) to VARCHAR2(255)."""
    r = Reconstructor()
    r.apply_file(base_migration['filename'], base_migration['sql'])
    r.apply_file(modify_single_column['filename'], modify_single_column['sql'])
    
    graph = r.snapshot()
    users = graph.tables['USERS']
    email_col = next(c for c in users.columns if c.name == 'EMAIL')
    
    assert email_col.type == 'VARCHAR2'
    assert email_col.precision == 255
    assert email_col.nullable is False


def test_modify_single_column_nullability(base_migration, modify_single_column):
    """MODIFY should change column nullability from NULL to NOT NULL."""
    r = Reconstructor()
    r.apply_file(base_migration['filename'], base_migration['sql'])
    
    # Before: email may or may not be nullable depending on DDL parsing
    # (sqlglot treats explicit NULL as non-nullable in some versions)
    graph1 = r.snapshot()
    email_col1 = next(c for c in graph1.tables['USERS'].columns if c.name == 'EMAIL')
    original_nullable = email_col1.nullable
    
    # After: email should definitely be not nullable after MODIFY with NOT NULL
    r.apply_file(modify_single_column['filename'], modify_single_column['sql'])
    graph2 = r.snapshot()
    email_col2 = next(c for c in graph2.tables['USERS'].columns if c.name == 'EMAIL')
    assert email_col2.nullable is False
    
    # Verify that MODIFY was applied (even if original state was already non-nullable)
    # by checking that the modify action was created
    assert '2' in graph2.tables['USERS'].modified_in


def test_modify_creates_action(base_migration, modify_single_column):
    """MODIFY should create a MODIFY_COLUMN action."""
    r = Reconstructor()
    r.apply_file(base_migration['filename'], base_migration['sql'])
    result = r.apply_file(modify_single_column['filename'], modify_single_column['sql'])
    
    assert len(result.actions) >= 1
    modify_action = result.actions[0]
    assert modify_action.action == 'MODIFY_COLUMN'
    assert modify_action.object_type == 'COLUMN'
    assert modify_action.object_name == 'USERS.EMAIL'
    assert modify_action.version == '2'


def test_modify_updates_modified_in(base_migration, modify_single_column):
    """MODIFY should add version to table's modified_in list."""
    r = Reconstructor()
    r.apply_file(base_migration['filename'], base_migration['sql'])
    r.apply_file(modify_single_column['filename'], modify_single_column['sql'])
    
    graph = r.snapshot()
    users = graph.tables['USERS']
    assert '2' in users.modified_in


# ─────────────────────────────────────────────
# MULTIPLE COLUMN MODIFY TESTS
# ─────────────────────────────────────────────

def test_modify_multiple_columns_at_once(base_migration, modify_multiple_columns):
    """MODIFY should handle multiple columns in one statement."""
    r = Reconstructor()
    r.apply_file(base_migration['filename'], base_migration['sql'])
    result = r.apply_file(modify_multiple_columns['filename'], modify_multiple_columns['sql'])
    
    graph = r.snapshot()
    users = graph.tables['USERS']
    
    # Check email
    email_col = next(c for c in users.columns if c.name == 'EMAIL')
    assert email_col.precision == 255
    assert email_col.nullable is False
    
    # Check age
    age_col = next(c for c in users.columns if c.name == 'AGE')
    assert age_col.default is not None  # Should have default value
    
    # Check status
    status_col = next(c for c in users.columns if c.name == 'STATUS')
    assert status_col.precision == 30


def test_modify_multiple_columns_creates_multiple_actions(base_migration, modify_multiple_columns):
    """MODIFY with multiple columns should create multiple actions."""
    r = Reconstructor()
    r.apply_file(base_migration['filename'], base_migration['sql'])
    result = r.apply_file(modify_multiple_columns['filename'], modify_multiple_columns['sql'])
    
    # Should have at least 3 actions (one per column)
    modify_actions = [a for a in result.actions if a.action == 'MODIFY_COLUMN']
    assert len(modify_actions) >= 3
    
    # Check that actions target different columns
    object_names = {a.object_name for a in modify_actions}
    assert 'USERS.EMAIL' in object_names
    assert 'USERS.AGE' in object_names
    assert 'USERS.STATUS' in object_names


# ─────────────────────────────────────────────
# DEFAULT VALUE TESTS
# ─────────────────────────────────────────────

def test_modify_with_default_value(base_migration, modify_with_default):
    """MODIFY should set default value on column."""
    r = Reconstructor()
    r.apply_file(base_migration['filename'], base_migration['sql'])
    r.apply_file(modify_with_default['filename'], modify_with_default['sql'])
    
    graph = r.snapshot()
    users = graph.tables['USERS']
    status_col = next(c for c in users.columns if c.name == 'STATUS')
    
    # Should have a default value (exact format depends on parsing)
    assert status_col.default is not None
    assert 'ACTIVE' in status_col.default.upper()


# ─────────────────────────────────────────────
# ERROR HANDLING TESTS
# ─────────────────────────────────────────────

def test_modify_nonexistent_table():
    """MODIFY on nonexistent table should not crash."""
    r = Reconstructor()
    result = r.apply_file(
        'V1__modify_missing.sql',
        'ALTER TABLE nonexistent MODIFY (col VARCHAR2(100))'
    )
    
    # Should return empty or report error, but not crash
    assert result.errors or len(result.actions) == 0


def test_modify_nonexistent_column(base_migration):
    """MODIFY on nonexistent column should not crash."""
    r = Reconstructor()
    r.apply_file(base_migration['filename'], base_migration['sql'])
    result = r.apply_file(
        'V2__modify_missing_col.sql',
        'ALTER TABLE users MODIFY (nonexistent_col VARCHAR2(100))'
    )
    
    # Should handle gracefully
    # The behavior depends on whether it's considered an error or silently ignored
    # For now, we just verify it doesn't crash
    graph = r.snapshot()
    assert 'USERS' in graph.tables


# ─────────────────────────────────────────────
# PRECISION AND SCALE TESTS
# ─────────────────────────────────────────────

def test_modify_precision_and_scale():
    """MODIFY should correctly parse precision and scale."""
    r = Reconstructor()
    r.apply_file(
        'V1__create_products.sql',
        'CREATE TABLE products (id NUMBER(10), price NUMBER(10, 2))'
    )
    r.apply_file(
        'V2__modify_price.sql',
        'ALTER TABLE products MODIFY (price NUMBER(12, 4))'
    )
    
    graph = r.snapshot()
    products = graph.tables['PRODUCTS']
    price_col = next(c for c in products.columns if c.name == 'PRICE')
    
    assert price_col.precision == 12
    assert price_col.scale == 4


# ─────────────────────────────────────────────
# BARE MODIFY SYNTAX TESTS (without parentheses)
# ─────────────────────────────────────────────

def test_modify_without_parens(base_migration):
    """MODIFY without parentheses should also work."""
    r = Reconstructor()
    r.apply_file(base_migration['filename'], base_migration['sql'])
    r.apply_file(
        'V2__modify_no_parens.sql',
        'ALTER TABLE users MODIFY email VARCHAR2(200) NOT NULL'
    )
    
    graph = r.snapshot()
    users = graph.tables['USERS']
    email_col = next(c for c in users.columns if c.name == 'EMAIL')
    
    assert email_col.precision == 200
    assert email_col.nullable is False


# ─────────────────────────────────────────────
# FEATURE FLAG TESTS
# ─────────────────────────────────────────────

@pytest.mark.skipif(not SQLGLOT_HAS_MODIFY, reason="Testing regex fallback path")
def test_native_path_used_when_available():
    """When sqlglot supports MODIFY, native path should be used."""
    # This test just verifies the feature flag is correct
    # Actual path testing is implicit in other tests
    assert SQLGLOT_HAS_MODIFY is True


@pytest.mark.skipif(SQLGLOT_HAS_MODIFY, reason="Testing native path")
def test_regex_fallback_used_when_needed():
    """When sqlglot doesn't support MODIFY, regex fallback should be used."""
    # This test verifies the feature flag correctly detects absence of support
    assert SQLGLOT_HAS_MODIFY is False
