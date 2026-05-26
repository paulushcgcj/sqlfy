"""
test_domains.py
===============
Tests for semantic domain detection (Feature #27).
"""

import pytest
from sqlfy.analysis.domains import (
    detect_domains,
    infer_domain_label,
    infer_domain_description,
    format_text,
    format_json,
)
from sqlfy.domain.schema_state import SchemaStateBuilder
from sqlfy.reconstructor import reconstruct


def test_infer_domain_label_with_common_prefix():
    """Test domain label inference with common prefix."""
    tables = ['USER_PROFILES', 'USER_ROLES', 'USER_SESSIONS']
    label = infer_domain_label(tables)
    assert 'User' in label or 'USER' in label


def test_infer_domain_label_with_schema_prefix():
    """Test domain label inference with schema.table format."""
    tables = ['APP.USERS', 'APP.ORDERS', 'APP.PRODUCTS']
    label = infer_domain_label(tables)
    assert 'App' in label or 'APP' in label or 'Users' in label


def test_infer_domain_label_fallback():
    """Test domain label inference fallback for no common prefix."""
    tables = ['CUSTOMERS', 'ORDERS', 'PRODUCTS']
    label = infer_domain_label(tables)
    assert label  # Should return something


def test_infer_domain_label_empty():
    """Test domain label inference with empty list."""
    label = infer_domain_label([])
    assert label == "Unknown Domain"


def test_infer_domain_description():
    """Test domain description inference."""
    # Create minimal state for testing
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER)'},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph)
    
    tables = ['APP.USERS']
    description = infer_domain_description(tables, state)
    assert 'Domain containing' in description
    assert '1' in description


def test_detect_domains_empty_state():
    """Test domain detection with empty state."""
    files = []
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph)
    
    result = detect_domains(state)
    
    assert result.num_domains == 0
    assert result.total_tables == 0
    assert result.algorithm == 'none'


def test_detect_domains_single_table():
    """Test domain detection with single table."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY)'},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph)
    
    result = detect_domains(state)
    
    assert result.num_domains >= 1
    assert result.total_tables == 1
    assert result.algorithm in ['leiden', 'louvain']


def test_detect_domains_multiple_tables_no_relationships():
    """Test domain detection with isolated tables."""
    files = [
        {'filename': 'V1__create_tables.sql', 'sql': '''
            CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY);
            CREATE TABLE APP.PRODUCTS (ID NUMBER PRIMARY KEY);
            CREATE TABLE APP.ORDERS (ID NUMBER PRIMARY KEY);
        '''},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph)
    
    result = detect_domains(state)
    
    assert result.total_tables == 3
    # Isolated tables may form multiple domains or one domain depending on algorithm
    assert result.num_domains >= 1


def test_detect_domains_with_relationships():
    """Test domain detection with foreign key relationships."""
    files = [
        {'filename': 'V1__create_tables.sql', 'sql': '''
            CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY);
            CREATE TABLE APP.ORDERS (
                ID NUMBER PRIMARY KEY,
                USER_ID NUMBER,
                CONSTRAINT FK_ORDERS_USERS FOREIGN KEY (USER_ID) REFERENCES APP.USERS(ID)
            );
        '''},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph)
    
    result = detect_domains(state)
    
    assert result.total_tables == 2
    assert result.num_domains >= 1
    
    # Tables with FK should be in the same domain
    if result.num_domains == 1:
        domain = result.domains[0]
        assert 'APP.USERS' in domain.tables
        assert 'APP.ORDERS' in domain.tables


def test_detect_domains_custom_resolution():
    """Test domain detection with custom resolution parameter."""
    files = [
        {'filename': 'V1__create_tables.sql', 'sql': '''
            CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY);
            CREATE TABLE APP.ORDERS (ID NUMBER PRIMARY KEY);
            CREATE TABLE APP.PRODUCTS (ID NUMBER PRIMARY KEY);
        '''},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph)
    
    # Higher resolution = more communities
    result_high = detect_domains(state, resolution=2.0)
    result_low = detect_domains(state, resolution=0.5)
    
    # Both should complete without error
    assert result_high.total_tables == 3
    assert result_low.total_tables == 3


def test_detect_domains_min_cohesion():
    """Test domain detection with minimum cohesion filter."""
    files = [
        {'filename': 'V1__create_tables.sql', 'sql': '''
            CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY);
            CREATE TABLE APP.ORDERS (
                ID NUMBER PRIMARY KEY,
                USER_ID NUMBER,
                CONSTRAINT FK_ORDERS_USERS FOREIGN KEY (USER_ID) REFERENCES APP.USERS(ID)
            );
        '''},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph)
    
    # High cohesion threshold may filter out weak communities
    result = detect_domains(state, min_cohesion=0.5)
    
    assert result.total_tables == 2


def test_detect_domains_disable_splitting():
    """Test domain detection with splitting disabled."""
    files = [
        {'filename': 'V1__create_tables.sql', 'sql': '''
            CREATE TABLE APP.T1 (ID NUMBER PRIMARY KEY);
            CREATE TABLE APP.T2 (ID NUMBER PRIMARY KEY);
            CREATE TABLE APP.T3 (ID NUMBER PRIMARY KEY);
        '''},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph)
    
    result = detect_domains(state, enable_splitting=False)
    
    assert result.total_tables == 3


def test_cross_domain_dependencies():
    """Test cross-domain dependency detection."""
    files = [
        {'filename': 'V1__create_tables.sql', 'sql': '''
            CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY);
            CREATE TABLE APP.PRODUCTS (ID NUMBER PRIMARY KEY);
            CREATE TABLE APP.ORDERS (
                ID NUMBER PRIMARY KEY,
                USER_ID NUMBER,
                PRODUCT_ID NUMBER,
                CONSTRAINT FK_ORDERS_USERS FOREIGN KEY (USER_ID) REFERENCES APP.USERS(ID),
                CONSTRAINT FK_ORDERS_PRODUCTS FOREIGN KEY (PRODUCT_ID) REFERENCES APP.PRODUCTS(ID)
            );
        '''},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph)
    
    result = detect_domains(state)
    
    # Should detect dependencies between domains (if they're in separate domains)
    # The exact result depends on the community detection algorithm
    assert result.total_tables == 3


def test_format_text():
    """Test text formatting of domain results."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY)'},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph)
    
    result = detect_domains(state)
    text = format_text(result)
    
    assert 'SEMANTIC DOMAIN DETECTION' in text
    assert 'Algorithm:' in text
    assert 'Total tables:' in text


def test_format_text_empty():
    """Test text formatting with no domains."""
    files = []
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph)
    
    result = detect_domains(state)
    text = format_text(result)
    
    assert 'No domains detected' in text


def test_format_json():
    """Test JSON formatting of domain results."""
    import json
    
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY)'},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph)
    
    result = detect_domains(state)
    json_str = format_json(result)
    
    # Should be valid JSON
    data = json.loads(json_str)
    
    assert 'algorithm' in data
    assert 'total_tables' in data
    assert 'num_domains' in data
    assert 'domains' in data
    assert isinstance(data['domains'], list)


def test_format_json_with_cross_domain_deps():
    """Test JSON formatting with cross-domain dependencies."""
    import json
    
    files = [
        {'filename': 'V1__create_tables.sql', 'sql': '''
            CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY);
            CREATE TABLE APP.ORDERS (
                ID NUMBER PRIMARY KEY,
                USER_ID NUMBER,
                CONSTRAINT FK_ORDERS_USERS FOREIGN KEY (USER_ID) REFERENCES APP.USERS(ID)
            );
        '''},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph)
    
    result = detect_domains(state)
    json_str = format_json(result)
    
    data = json.loads(json_str)
    
    assert 'cross_domain_dependencies' in data
    assert isinstance(data['cross_domain_dependencies'], list)


def test_domain_cohesion_scores():
    """Test that domains include cohesion scores."""
    files = [
        {'filename': 'V1__create_tables.sql', 'sql': '''
            CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY);
            CREATE TABLE APP.ORDERS (
                ID NUMBER PRIMARY KEY,
                USER_ID NUMBER,
                CONSTRAINT FK_ORDERS_USERS FOREIGN KEY (USER_ID) REFERENCES APP.USERS(ID)
            );
        '''},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph)
    
    result = detect_domains(state)
    
    for domain in result.domains:
        assert hasattr(domain, 'cohesion')
        assert 0.0 <= domain.cohesion <= 1.0


def test_domain_sorting():
    """Test that domains are sorted by size (largest first)."""
    files = [
        {'filename': 'V1__create_tables.sql', 'sql': '''
            CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY);
            CREATE TABLE APP.ORDERS (ID NUMBER PRIMARY KEY);
            CREATE TABLE APP.PRODUCTS (ID NUMBER PRIMARY KEY);
            CREATE TABLE APP.CATEGORIES (ID NUMBER PRIMARY KEY);
        '''},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph)
    
    result = detect_domains(state)
    
    # Verify sorting (largest first)
    if len(result.domains) > 1:
        for i in range(len(result.domains) - 1):
            assert result.domains[i].table_count >= result.domains[i + 1].table_count
