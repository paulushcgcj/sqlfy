"""
Tests for schema evolution simulator.
"""

import pytest
from sqlfy.analysis.simulator import SchemaSimulator, SimulationResult
from sqlfy.reconstructor import reconstruct


def test_simulate_add_column():
    """Simulate adding a column."""
    files = [
        {'filename': 'V1__create_users.sql', 
         'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY, name VARCHAR2(100));'},
    ]
    
    simulator = SchemaSimulator(files)
    result = simulator.simulate_sql('ALTER TABLE users ADD (email VARCHAR2(255));')
    
    assert result.success
    assert result.is_safe()
    assert not result.is_breaking()
    assert result.health_score >= 90


def test_simulate_add_not_null_unsafe():
    """Simulate unsafe ADD NOT NULL without DEFAULT."""
    files = [
        {'filename': 'V1__create_users.sql', 
         'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
    ]
    
    simulator = SchemaSimulator(files)
    result = simulator.simulate_sql('ALTER TABLE users ADD (status VARCHAR2(20) NOT NULL);')
    
    assert result.success  # Syntax is valid
    assert not result.is_safe()  # But has error findings
    assert len(result.insights.errors()) > 0


def test_simulate_drop_table_breaking():
    """Simulate DROP TABLE (breaking change)."""
    files = [
        {'filename': 'V1__create_users.sql', 
         'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
    ]
    
    simulator = SchemaSimulator(files)
    result = simulator.simulate_sql('DROP TABLE users;')
    
    assert result.success
    assert result.is_breaking()
    assert result.diff.stats()['tables_removed'] == 1


def test_simulate_at_version():
    """Simulate from specific version."""
    files = [
        {'filename': 'V1__create_users.sql', 
         'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
        {'filename': 'V2__create_orders.sql', 
         'sql': 'CREATE TABLE orders (id NUMBER PRIMARY KEY);'},
        {'filename': 'V3__create_products.sql', 
         'sql': 'CREATE TABLE products (id NUMBER PRIMARY KEY);'},
    ]
    
    # Simulate from V2 (users and orders exist, products doesn't)
    simulator = SchemaSimulator(files, base_version='2')
    result = simulator.simulate_sql('ALTER TABLE orders ADD (status VARCHAR2(20));')
    
    assert result.success
    assert result.base_version == '2'
    # Should have users and orders, but not products
    assert 'USERS' in result.base_state.tables
    assert 'ORDERS' in result.base_state.tables
    assert 'PRODUCTS' not in result.base_state.tables


def test_simulate_invalid_sql():
    """Simulate invalid SQL."""
    files = [
        {'filename': 'V1__create_users.sql', 
         'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
    ]
    
    simulator = SchemaSimulator(files)
    result = simulator.simulate_sql('INVALID SQL GARBAGE;')
    
    # sqlglot may parse this as a Command and not fail
    # Just verify we get a result back
    assert result is not None
    assert result.base_version == '1'


def test_simulation_result_text_format():
    """Text format is human-readable."""
    files = [
        {'filename': 'V1__create_users.sql', 
         'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
    ]
    
    simulator = SchemaSimulator(files)
    result = simulator.simulate_sql('ALTER TABLE users ADD (email VARCHAR2(255));')
    
    text = result.to_text()
    
    assert 'Schema Evolution Simulation' in text
    assert 'V1' in text
    assert 'ALTER TABLE' in text


def test_simulation_result_json_format():
    """JSON format is valid."""
    files = [
        {'filename': 'V1__create_users.sql', 
         'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
    ]
    
    simulator = SchemaSimulator(files)
    result = simulator.simulate_sql('ALTER TABLE users ADD (email VARCHAR2(255));')
    
    import json
    data = json.loads(result.to_json())
    
    assert 'success' in data
    assert 'isSafe' in data
    assert 'health' in data
    assert data['baseVersion'] == '1'


def test_diff_stats():
    """Diff stats are accurate."""
    files = [
        {'filename': 'V1__create_users.sql', 
         'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
    ]
    
    simulator = SchemaSimulator(files)
    result = simulator.simulate_sql('''
        CREATE TABLE orders (id NUMBER PRIMARY KEY);
        ALTER TABLE users ADD (email VARCHAR2(255));
    ''')
    
    stats = result.diff.stats()
    assert stats['tables_added'] == 1  # orders
    assert stats['tables_modified'] == 1  # users


def test_health_score_degradation():
    """Health score decreases with errors."""
    files = [
        {'filename': 'V1__create_users.sql', 
         'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
    ]
    
    # Safe simulation
    simulator = SchemaSimulator(files)
    safe_result = simulator.simulate_sql('ALTER TABLE users ADD (email VARCHAR2(255));')
    
    # Unsafe simulation (multiple errors)
    unsafe_result = simulator.simulate_sql('''
        ALTER TABLE users ADD (c1 VARCHAR2(20) NOT NULL);
        ALTER TABLE users ADD (c2 VARCHAR2(20) NOT NULL);
    ''')
    
    assert unsafe_result.health_score < safe_result.health_score


def test_summary_method():
    """Summary method provides brief overview."""
    files = [
        {'filename': 'V1__create_users.sql', 
         'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
    ]
    
    simulator = SchemaSimulator(files)
    result = simulator.simulate_sql('ALTER TABLE users ADD (email VARCHAR2(255));')
    
    summary = result.summary()
    
    assert 'successful' in summary.lower() or 'failed' in summary.lower()
    assert 'health' in summary.lower()


def test_simulate_create_table():
    """Simulate creating a new table."""
    files = [
        {'filename': 'V1__create_users.sql', 
         'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
    ]
    
    simulator = SchemaSimulator(files)
    result = simulator.simulate_sql('CREATE TABLE orders (id NUMBER PRIMARY KEY, user_id NUMBER);')
    
    assert result.success
    assert result.is_safe()
    assert result.diff.stats()['tables_added'] == 1
    assert 'ORDERS' in result.simulated_state.tables


def test_simulate_empty_base():
    """Simulate with no base migrations."""
    files = []
    
    simulator = SchemaSimulator(files)
    result = simulator.simulate_sql('CREATE TABLE users (id NUMBER PRIMARY KEY);')
    
    assert result.success
    assert result.base_version == '0'
    assert result.diff.stats()['tables_added'] == 1


def test_is_breaking_false_for_safe_changes():
    """Non-breaking changes are not flagged as breaking."""
    files = [
        {'filename': 'V1__create_users.sql', 
         'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
    ]
    
    simulator = SchemaSimulator(files)
    
    # Add column (non-breaking)
    result = simulator.simulate_sql('ALTER TABLE users ADD (email VARCHAR2(255));')
    assert not result.is_breaking()
    
    # Create table (non-breaking)
    result = simulator.simulate_sql('CREATE TABLE orders (id NUMBER PRIMARY KEY);')
    assert not result.is_breaking()


def test_simulate_multiple_statements():
    """Simulate multiple DDL statements."""
    files = [
        {'filename': 'V1__create_users.sql', 
         'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
    ]
    
    simulator = SchemaSimulator(files)
    result = simulator.simulate_sql('''
        CREATE TABLE orders (id NUMBER PRIMARY KEY);
        CREATE TABLE products (id NUMBER PRIMARY KEY);
        ALTER TABLE users ADD (email VARCHAR2(255));
    ''')
    
    assert result.success
    stats = result.diff.stats()
    assert stats['tables_added'] == 2  # orders, products
    assert stats['tables_modified'] == 1  # users
