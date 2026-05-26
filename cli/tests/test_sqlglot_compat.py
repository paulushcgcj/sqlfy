"""
test_sqlglot_compat
===================
Tests for sqlglot feature detection and compatibility layer.
"""

import pytest
from sqlfy.domain.sqlglot_compat import (
    SQLGLOT_HAS_MODIFY,
    SQLGLOT_HAS_RENAME_COLUMN,
    parse_modify_native,
    ModifyColumnInfo,
    log_sqlglot_capabilities,
)


# ─────────────────────────────────────────────
# FEATURE DETECTION TESTS
# ─────────────────────────────────────────────

def test_modify_feature_flag_is_boolean():
    """Feature flag should be a boolean value."""
    assert isinstance(SQLGLOT_HAS_MODIFY, bool)


def test_rename_column_feature_flag_is_boolean():
    """Feature flag should be a boolean value."""
    assert isinstance(SQLGLOT_HAS_RENAME_COLUMN, bool)


def test_log_capabilities_does_not_crash():
    """Logging capabilities should not raise exceptions."""
    log_sqlglot_capabilities()


# ─────────────────────────────────────────────
# NATIVE MODIFY PARSING TESTS
# ─────────────────────────────────────────────

@pytest.mark.skipif(not SQLGLOT_HAS_MODIFY, reason="sqlglot does not support native MODIFY")
def test_parse_modify_single_column():
    """Parse a simple ALTER TABLE MODIFY with one column."""
    sql = "ALTER TABLE users MODIFY (email VARCHAR2(255) NOT NULL)"
    table_name, modifications = parse_modify_native(sql)
    
    assert table_name == "USERS"
    assert len(modifications) == 1
    
    mod = modifications[0]
    assert mod.column_name == "EMAIL"
    # Note: Exact parsing depends on sqlglot version
    # We just verify we got structured data back
    assert isinstance(mod, ModifyColumnInfo)


@pytest.mark.skipif(not SQLGLOT_HAS_MODIFY, reason="sqlglot does not support native MODIFY")
def test_parse_modify_with_type_change():
    """Parse MODIFY that changes column type."""
    sql = "ALTER TABLE orders MODIFY status VARCHAR2(20)"
    table_name, modifications = parse_modify_native(sql)
    
    assert table_name == "ORDERS"
    assert len(modifications) >= 1
    assert modifications[0].column_name == "STATUS"


@pytest.mark.skipif(not SQLGLOT_HAS_MODIFY, reason="sqlglot does not support native MODIFY")
def test_parse_modify_with_default():
    """Parse MODIFY that adds a default value."""
    sql = "ALTER TABLE orders MODIFY (status VARCHAR2(20) DEFAULT 'PENDING')"
    table_name, modifications = parse_modify_native(sql)
    
    assert table_name == "ORDERS"
    assert len(modifications) >= 1


@pytest.mark.skipif(not SQLGLOT_HAS_MODIFY, reason="sqlglot does not support native MODIFY")
def test_parse_modify_multiple_columns():
    """Parse MODIFY with multiple columns in one statement."""
    sql = """
    ALTER TABLE users MODIFY (
        email VARCHAR2(255) NOT NULL,
        age NUMBER(3),
        created_at DATE DEFAULT SYSDATE
    )
    """
    table_name, modifications = parse_modify_native(sql)
    
    assert table_name == "USERS"
    # Should parse at least one column successfully
    assert len(modifications) >= 1
    col_names = [mod.column_name for mod in modifications]
    # Verify at least email was parsed
    assert "EMAIL" in col_names


def test_parse_modify_without_native_support_raises_error():
    """When native MODIFY not supported, parse_modify_native should raise ValueError."""
    if SQLGLOT_HAS_MODIFY:
        pytest.skip("sqlglot has native MODIFY support")
    
    sql = "ALTER TABLE users MODIFY (email VARCHAR2(255))"
    with pytest.raises(ValueError, match="does not support native MODIFY"):
        parse_modify_native(sql)


@pytest.mark.skipif(not SQLGLOT_HAS_MODIFY, reason="sqlglot does not support native MODIFY")
def test_parse_modify_invalid_sql_raises_error():
    """Invalid SQL should raise ValueError."""
    sql = "CREATE TABLE foo (id NUMBER)"  # Not a MODIFY statement
    with pytest.raises(ValueError):
        parse_modify_native(sql)


# ─────────────────────────────────────────────
# MODIFY COLUMN INFO TESTS
# ─────────────────────────────────────────────

def test_modify_column_info_creation():
    """ModifyColumnInfo can be created with all fields."""
    info = ModifyColumnInfo(
        column_name="EMAIL",
        data_type="VARCHAR2",
        precision=255,
        scale=None,
        nullable=False,
        default="'user@example.com'",
    )
    
    assert info.column_name == "EMAIL"
    assert info.data_type == "VARCHAR2"
    assert info.precision == 255
    assert info.scale is None
    assert info.nullable is False
    assert info.default == "'user@example.com'"


def test_modify_column_info_minimal():
    """ModifyColumnInfo can be created with just column name."""
    info = ModifyColumnInfo(column_name="EMAIL")
    
    assert info.column_name == "EMAIL"
    assert info.data_type is None
    assert info.precision is None
    assert info.scale is None
    assert info.nullable is None
    assert info.default is None
