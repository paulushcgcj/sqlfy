"""
test_migration_graph.py
=======================
Tests for migration graph visualization module (Feature #21).
"""

from sqlfy.migration_graph import (
    parse_migration_filename,
    extract_table_operations,
    build_migration_graph,
    format_dot,
    format_html,
    format_timeline,
    format_json,
    MigrationNode,
    MigrationGraph,
)
from datetime import datetime
import json


# ─────────────────────────────────────────────
# Filename Parsing Tests
# ─────────────────────────────────────────────

def test_parse_migration_filename_simple():
    """Test parsing simple Flyway-style filename."""
    version, description, timestamp = parse_migration_filename('V1__create_users.sql')
    
    assert version == 'V1'
    assert description == 'create users'
    assert timestamp is None


def test_parse_migration_filename_with_decimal():
    """Test parsing versioned filename with decimal."""
    version, description, timestamp = parse_migration_filename('V2.1__add_email.sql')
    
    assert version == 'V2.1'
    assert description == 'add email'
    assert timestamp is None


def test_parse_migration_filename_with_timestamp():
    """Test parsing timestamp-based filename."""
    version, description, timestamp = parse_migration_filename('V20260525120000__add_index.sql')
    
    assert version == 'V20260525120000'
    assert description == 'add index'
    assert timestamp == datetime(2026, 5, 25, 12, 0, 0)


def test_parse_migration_filename_invalid():
    """Test parsing invalid filename falls back to original name."""
    version, description, timestamp = parse_migration_filename('invalid.sql')
    
    assert version == 'invalid.sql'
    assert description == 'invalid.sql'
    assert timestamp is None


# ─────────────────────────────────────────────
# Table Operation Extraction Tests
# ─────────────────────────────────────────────

def test_extract_table_operations_create_table():
    """Test extracting CREATE TABLE statements."""
    sql = """
    CREATE TABLE users (
        id NUMBER PRIMARY KEY,
        email VARCHAR2(255)
    );
    """
    
    creates, alters, references = extract_table_operations(sql)
    
    assert 'USERS' in creates
    assert len(alters) == 0
    assert len(references) == 0


def test_extract_table_operations_alter_table():
    """Test extracting ALTER TABLE statements."""
    sql = """
    ALTER TABLE users ADD COLUMN status VARCHAR2(50);
    """
    
    creates, alters, references = extract_table_operations(sql)
    
    assert len(creates) == 0
    assert 'USERS' in alters
    assert len(references) == 0


def test_extract_table_operations_create_view():
    """Test extracting CREATE VIEW with table references."""
    sql = """
    CREATE VIEW user_orders AS
    SELECT u.id, u.email, o.total
    FROM users u
    JOIN orders o ON u.id = o.user_id;
    """
    
    creates, alters, references = extract_table_operations(sql)
    
    assert 'USER_ORDERS' in creates
    assert 'USERS' in references
    assert 'ORDERS' in references


def test_extract_table_operations_foreign_key():
    """Test extracting foreign key references."""
    sql = """
    ALTER TABLE orders
    ADD CONSTRAINT fk_user
    FOREIGN KEY (user_id) REFERENCES users(id);
    """
    
    creates, alters, references = extract_table_operations(sql)
    
    assert 'ORDERS' in alters
    assert 'USERS' in references


def test_extract_table_operations_drop_table():
    """Test extracting DROP TABLE statements."""
    sql = """
    DROP TABLE temp_data;
    """
    
    creates, alters, references = extract_table_operations(sql)
    
    assert len(creates) == 0
    assert 'TEMP_DATA' in alters
    assert len(references) == 0


def test_extract_table_operations_multiple_statements():
    """Test extracting from multiple SQL statements."""
    sql = """
    CREATE TABLE products (id NUMBER PRIMARY KEY);
    ALTER TABLE orders ADD COLUMN product_id NUMBER;
    ALTER TABLE orders ADD CONSTRAINT fk_product FOREIGN KEY (product_id) REFERENCES products(id);
    """
    
    creates, alters, references = extract_table_operations(sql)
    
    assert 'PRODUCTS' in creates
    assert 'ORDERS' in alters
    assert 'PRODUCTS' in references


# ─────────────────────────────────────────────
# Migration Graph Building Tests
# ─────────────────────────────────────────────

def test_build_migration_graph_simple():
    """Test building graph from simple migrations."""
    files = [
        {
            'filename': 'V1__create_users.sql',
            'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'
        },
        {
            'filename': 'V2__create_orders.sql',
            'sql': 'CREATE TABLE orders (id NUMBER PRIMARY KEY, user_id NUMBER);'
        },
    ]
    
    graph = build_migration_graph(files)
    
    assert len(graph.nodes) == 2
    assert 'V1' in graph.nodes
    assert 'V2' in graph.nodes
    assert len(graph.edges) == 0  # No dependencies


def test_build_migration_graph_with_alter():
    """Test dependency resolution for ALTER TABLE."""
    files = [
        {
            'filename': 'V1__create_users.sql',
            'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'
        },
        {
            'filename': 'V2__add_email.sql',
            'sql': 'ALTER TABLE users ADD COLUMN email VARCHAR2(255);'
        },
    ]
    
    graph = build_migration_graph(files)
    
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert ('V1', 'V2') in graph.edges
    assert 'V1' in graph.nodes['V2'].dependencies


def test_build_migration_graph_with_foreign_key():
    """Test dependency resolution for foreign keys."""
    files = [
        {
            'filename': 'V1__create_users.sql',
            'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'
        },
        {
            'filename': 'V2__create_orders.sql',
            'sql': '''
                CREATE TABLE orders (
                    id NUMBER PRIMARY KEY,
                    user_id NUMBER,
                    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id)
                );
            '''
        },
    ]
    
    graph = build_migration_graph(files)
    
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert ('V1', 'V2') in graph.edges


def test_build_migration_graph_with_view():
    """Test dependency resolution for views."""
    files = [
        {
            'filename': 'V1__create_users.sql',
            'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'
        },
        {
            'filename': 'V2__create_orders.sql',
            'sql': 'CREATE TABLE orders (id NUMBER PRIMARY KEY);'
        },
        {
            'filename': 'V3__create_view.sql',
            'sql': 'CREATE VIEW user_orders AS SELECT * FROM users JOIN orders ON users.id = orders.user_id;'
        },
    ]
    
    graph = build_migration_graph(files)
    
    assert len(graph.nodes) == 3
    assert len(graph.edges) == 2
    assert ('V1', 'V3') in graph.edges
    assert ('V2', 'V3') in graph.edges


def test_build_migration_graph_transitive_dependencies():
    """Test transitive dependency chain (A → B → C)."""
    files = [
        {
            'filename': 'V1__create_users.sql',
            'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'
        },
        {
            'filename': 'V2__add_email.sql',
            'sql': 'ALTER TABLE users ADD COLUMN email VARCHAR2(255);'
        },
        {
            'filename': 'V3__add_index.sql',
            'sql': 'ALTER TABLE users ADD CONSTRAINT uk_email UNIQUE (email);'
        },
    ]
    
    graph = build_migration_graph(files)
    
    assert len(graph.nodes) == 3
    assert ('V1', 'V2') in graph.edges
    assert ('V1', 'V3') in graph.edges
    # V2 and V3 both depend on V1, but not on each other


# ─────────────────────────────────────────────
# Format Tests
# ─────────────────────────────────────────────

def test_format_dot_simple():
    """Test DOT format generation."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
        {'filename': 'V2__add_email.sql', 'sql': 'ALTER TABLE users ADD COLUMN email VARCHAR2(255);'},
    ]
    
    graph = build_migration_graph(files)
    output = format_dot(graph)
    
    assert 'digraph MigrationGraph' in output
    assert '"V1"' in output
    assert '"V2"' in output
    assert '"V1" -> "V2"' in output
    assert 'lightgreen' in output  # V1 creates table


def test_format_html_simple():
    """Test HTML format generation."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
        {'filename': 'V2__add_email.sql', 'sql': 'ALTER TABLE users ADD COLUMN email VARCHAR2(255);'},
    ]
    
    graph = build_migration_graph(files)
    output = format_html(graph)
    
    assert '<!DOCTYPE html>' in output
    assert 'vis-network' in output
    assert 'V1' in output
    assert 'V2' in output
    assert '2 migrations' in output
    assert '1 dependencies' in output


def test_format_timeline_simple():
    """Test timeline format generation."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
        {'filename': 'V2__add_email.sql', 'sql': 'ALTER TABLE users ADD COLUMN email VARCHAR2(255);'},
    ]
    
    graph = build_migration_graph(files)
    output = format_timeline(graph)
    
    assert 'Migration Timeline' in output
    assert 'V1: create users' in output
    assert 'V2: add email' in output
    assert 'Creates: USERS' in output
    assert 'Alters: USERS' in output
    assert 'Depends on: V1' in output
    assert '2 migrations, 1 dependencies' in output


def test_format_json_simple():
    """Test JSON format generation."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
        {'filename': 'V2__add_email.sql', 'sql': 'ALTER TABLE users ADD COLUMN email VARCHAR2(255);'},
    ]
    
    graph = build_migration_graph(files)
    output = format_json(graph)
    data = json.loads(output)
    
    assert len(data['nodes']) == 2
    assert len(data['edges']) == 1
    assert data['stats']['migration_count'] == 2
    assert data['stats']['dependency_count'] == 1
    
    # Check node structure
    node_versions = [n['version'] for n in data['nodes']]
    assert 'V1' in node_versions
    assert 'V2' in node_versions
    
    # Check edge structure
    assert data['edges'][0] == {'from': 'V1', 'to': 'V2'}


def test_format_json_with_timestamp():
    """Test JSON format with timestamp in filename."""
    files = [
        {'filename': 'V20260525120000__create_users.sql', 'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
    ]
    
    graph = build_migration_graph(files)
    output = format_json(graph)
    data = json.loads(output)
    
    assert data['nodes'][0]['timestamp'] == '2026-05-25T12:00:00'


# ─────────────────────────────────────────────
# Edge Cases
# ─────────────────────────────────────────────

def test_build_migration_graph_empty():
    """Test building graph from empty file list."""
    graph = build_migration_graph([])
    
    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0


def test_build_migration_graph_circular_reference():
    """Test graph handles circular references gracefully."""
    # This is a theoretical test — in practice, circular table dependencies
    # are not possible in SQL DDL, but views could theoretically reference each other
    files = [
        {'filename': 'V1__create_a.sql', 'sql': 'CREATE TABLE a (id NUMBER);'},
        {'filename': 'V2__create_b.sql', 'sql': 'CREATE TABLE b (id NUMBER);'},
        {'filename': 'V3__alter_a.sql', 'sql': 'ALTER TABLE a ADD COLUMN b_id NUMBER REFERENCES b(id);'},
        {'filename': 'V4__alter_b.sql', 'sql': 'ALTER TABLE b ADD COLUMN a_id NUMBER REFERENCES a(id);'},
    ]
    
    graph = build_migration_graph(files)
    
    # Both V3 and V4 depend on V1 and V2
    assert ('V1', 'V3') in graph.edges
    assert ('V2', 'V4') in graph.edges
    # No circular edges at migration level (migrations are linearly ordered)


def test_build_migration_graph_no_dependencies():
    """Test migrations with no dependencies (all independent)."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE users (id NUMBER);'},
        {'filename': 'V2__create_orders.sql', 'sql': 'CREATE TABLE orders (id NUMBER);'},
        {'filename': 'V3__create_products.sql', 'sql': 'CREATE TABLE products (id NUMBER);'},
    ]
    
    graph = build_migration_graph(files)
    
    assert len(graph.nodes) == 3
    assert len(graph.edges) == 0  # All independent
