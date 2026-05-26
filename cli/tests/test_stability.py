"""
test_stability.py
=================
Tests for schema stability metrics (Feature #29).
"""

import pytest
from sqlfy.analysis.stability import (
    calculate_stability,
    format_text,
    format_json,
    _calculate_volatility,
    _get_stability_grade,
)
from sqlfy.domain.schema_state import SchemaStateBuilder
from sqlfy.reconstructor import reconstruct


def test_calculate_stability_empty_state():
    """Test stability calculation with no migrations."""
    files = []
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph)
    
    report = calculate_stability(state)
    
    assert report.total_migrations == 0
    assert report.overall_stability_score == 100
    assert report.num_high_churn_tables == 0
    assert report.num_stable_tables == 0


def test_calculate_stability_single_migration():
    """Test stability with a single migration."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY)'},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    report = calculate_stability(state)
    
    assert report.total_migrations == 1
    assert len(report.all_table_metrics) == 1
    
    # Single creation should be stable
    metrics = report.all_table_metrics[0]
    assert metrics.table_name == 'APP.USERS'
    assert metrics.modification_count == 1
    assert metrics.churn_rate == 100.0  # 1/1 * 100


def test_calculate_stability_multiple_migrations():
    """Test stability with multiple migrations."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V2__create_orders.sql', 'sql': 'CREATE TABLE APP.ORDERS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V3__modify_users.sql', 'sql': 'ALTER TABLE APP.USERS ADD COLUMN EMAIL VARCHAR2(255)'},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    report = calculate_stability(state)
    
    assert report.total_migrations == 3
    assert len(report.all_table_metrics) == 2
    
    # USERS should have higher churn (2 modifications)
    users_metrics = next(m for m in report.all_table_metrics if m.table_name == 'APP.USERS')
    orders_metrics = next(m for m in report.all_table_metrics if m.table_name == 'APP.ORDERS')
    
    assert users_metrics.modification_count == 2  # Created + Modified
    assert orders_metrics.modification_count == 1  # Created only
    assert users_metrics.churn_rate > orders_metrics.churn_rate


def test_calculate_stability_high_churn_detection():
    """Test detection of high-churn tables."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V2__modify_users.sql', 'sql': 'ALTER TABLE APP.USERS ADD COLUMN EMAIL VARCHAR2(255)'},
        {'filename': 'V3__modify_users_again.sql', 'sql': 'ALTER TABLE APP.USERS ADD COLUMN NAME VARCHAR2(100)'},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    # Default threshold is 20% for high churn
    report = calculate_stability(state)
    
    assert report.num_high_churn_tables >= 1
    
    # USERS should be in high churn (3 modifications / 3 migrations = 100%)
    assert any(m.table_name == 'APP.USERS' for m in report.high_churn_tables)


def test_calculate_stability_stable_tables():
    """Test detection of stable tables."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V2__create_orders.sql', 'sql': 'CREATE TABLE APP.ORDERS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V3__create_products.sql', 'sql': 'CREATE TABLE APP.PRODUCTS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V4__create_audit.sql', 'sql': 'CREATE TABLE APP.AUDIT (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V5__create_sessions.sql', 'sql': 'CREATE TABLE APP.SESSIONS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V6__create_logs.sql', 'sql': 'CREATE TABLE APP.LOGS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V7__create_cache.sql', 'sql': 'CREATE TABLE APP.CACHE (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V8__create_config.sql', 'sql': 'CREATE TABLE APP.CONFIG (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V9__create_metrics.sql', 'sql': 'CREATE TABLE APP.METRICS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V10__create_alerts.sql', 'sql': 'CREATE TABLE APP.ALERTS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V11__modify_users.sql', 'sql': 'ALTER TABLE APP.USERS ADD COLUMN EMAIL VARCHAR2(255)'},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    # Default threshold is 10% for stable
    report = calculate_stability(state)
    
    # Most tables should be stable (only 1 modification each)
    assert report.num_stable_tables >= 9
    
    # USERS should not be stable (2 modifications / 11 = 18.18%)
    assert not any(m.table_name == 'APP.USERS' for m in report.stable_tables)


def test_calculate_stability_custom_thresholds():
    """Test stability with custom churn thresholds."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V2__create_orders.sql', 'sql': 'CREATE TABLE APP.ORDERS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V3__modify_users.sql', 'sql': 'ALTER TABLE APP.USERS ADD COLUMN EMAIL VARCHAR2(255)'},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    # Very high threshold for high churn
    report = calculate_stability(state, high_churn_threshold=80.0, stable_threshold=30.0)
    
    # USERS has 66.67% churn, should not be in high_churn with 80% threshold
    assert report.num_high_churn_tables == 0


def test_calculate_stability_churn_rate_calculation():
    """Test churn rate calculation accuracy."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V2__create_orders.sql', 'sql': 'CREATE TABLE APP.ORDERS (ID NUMBER PRIMARY KEY)'},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    report = calculate_stability(state)
    
    # Each table: 1 modification / 2 migrations = 50%
    for metrics in report.all_table_metrics:
        assert metrics.churn_rate == 50.0


def test_calculate_stability_score_calculation():
    """Test stability score calculation."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY)'},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    report = calculate_stability(state)
    
    metrics = report.all_table_metrics[0]
    
    # Churn rate = 100%, Stability score = max(0, 100 - 100*2) = 0
    assert metrics.stability_score == 0


def test_calculate_stability_sorting():
    """Test that metrics are sorted by churn rate (highest first)."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V2__create_orders.sql', 'sql': 'CREATE TABLE APP.ORDERS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V3__create_products.sql', 'sql': 'CREATE TABLE APP.PRODUCTS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V4__modify_users.sql', 'sql': 'ALTER TABLE APP.USERS ADD COLUMN EMAIL VARCHAR2(255)'},
        {'filename': 'V5__modify_users_again.sql', 'sql': 'ALTER TABLE APP.USERS ADD COLUMN NAME VARCHAR2(100)'},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    report = calculate_stability(state)
    
    # Verify sorting
    for i in range(len(report.all_table_metrics) - 1):
        assert report.all_table_metrics[i].churn_rate >= report.all_table_metrics[i + 1].churn_rate


def test_calculate_volatility_empty():
    """Test volatility calculation with empty list."""
    result = _calculate_volatility([])
    assert result is None


def test_calculate_volatility_single_value():
    """Test volatility calculation with single value."""
    result = _calculate_volatility([5])
    assert result is None


def test_calculate_volatility_multiple_values():
    """Test volatility calculation with multiple values."""
    result = _calculate_volatility([1, 2, 3, 4, 5])
    assert result is not None
    assert result > 0


def test_calculate_volatility_uniform():
    """Test volatility calculation with uniform values."""
    result = _calculate_volatility([5, 5, 5, 5, 5])
    assert result == 0.0


def test_get_stability_grade_excellent():
    """Test stability grade for excellent scores."""
    assert 'A' in _get_stability_grade(95)
    assert 'Excellent' in _get_stability_grade(95)


def test_get_stability_grade_good():
    """Test stability grade for good scores."""
    assert 'B' in _get_stability_grade(80)
    assert 'Good' in _get_stability_grade(80)


def test_get_stability_grade_fair():
    """Test stability grade for fair scores."""
    assert 'C' in _get_stability_grade(65)
    assert 'Fair' in _get_stability_grade(65)


def test_get_stability_grade_poor():
    """Test stability grade for poor scores."""
    assert 'D' in _get_stability_grade(55)
    assert 'Poor' in _get_stability_grade(55)


def test_get_stability_grade_critical():
    """Test stability grade for critical scores."""
    assert 'F' in _get_stability_grade(30)
    assert 'Critical' in _get_stability_grade(30)


def test_format_text():
    """Test text formatting of stability report."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY)'},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    report = calculate_stability(state)
    text = format_text(report)
    
    assert 'SCHEMA STABILITY METRICS' in text
    assert 'Total migrations:' in text
    assert 'Stability score:' in text
    assert 'Grade:' in text


def test_format_text_with_high_churn():
    """Test text formatting with high-churn tables."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V2__modify_users.sql', 'sql': 'ALTER TABLE APP.USERS ADD COLUMN EMAIL VARCHAR2(255)'},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    report = calculate_stability(state)
    text = format_text(report)
    
    assert 'High Churn Tables' in text
    assert 'APP.USERS' in text


def test_format_text_with_stable_tables():
    """Test text formatting with stable tables."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V2__create_orders.sql', 'sql': 'CREATE TABLE APP.ORDERS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V3__create_products.sql', 'sql': 'CREATE TABLE APP.PRODUCTS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V4__create_audit.sql', 'sql': 'CREATE TABLE APP.AUDIT (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V5__create_sessions.sql', 'sql': 'CREATE TABLE APP.SESSIONS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V6__create_logs.sql', 'sql': 'CREATE TABLE APP.LOGS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V7__create_cache.sql', 'sql': 'CREATE TABLE APP.CACHE (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V8__create_config.sql', 'sql': 'CREATE TABLE APP.CONFIG (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V9__create_metrics.sql', 'sql': 'CREATE TABLE APP.METRICS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V10__create_alerts.sql', 'sql': 'CREATE TABLE APP.ALERTS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V11__noop.sql', 'sql': 'COMMENT ON TABLE APP.USERS IS \'User records\''},  # No structural changes
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    report = calculate_stability(state)
    text = format_text(report)
    
    assert 'Stable Tables' in text


def test_format_text_show_all():
    """Test text formatting with show_all flag."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V2__create_orders.sql', 'sql': 'CREATE TABLE APP.ORDERS (ID NUMBER PRIMARY KEY)'},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    report = calculate_stability(state)
    text = format_text(report, show_all=True)
    
    assert 'All Tables (sorted by churn rate):' in text
    assert 'APP.USERS' in text
    assert 'APP.ORDERS' in text


def test_format_json():
    """Test JSON formatting of stability report."""
    import json
    
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY)'},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    report = calculate_stability(state)
    json_str = format_json(report)
    
    # Should be valid JSON
    data = json.loads(json_str)
    
    assert 'total_migrations' in data
    assert 'overall_stability_score' in data
    assert 'grade' in data
    assert 'summary' in data
    assert 'all_tables' in data


def test_format_json_structure():
    """Test JSON structure includes all expected fields."""
    import json
    
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V2__modify_users.sql', 'sql': 'ALTER TABLE APP.USERS ADD COLUMN EMAIL VARCHAR2(255)'},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    report = calculate_stability(state)
    json_str = format_json(report)
    
    data = json.loads(json_str)
    
    assert 'high_churn_tables' in data
    assert 'stable_tables' in data
    assert isinstance(data['all_tables'], list)
    
    # Verify table entry structure
    if data['all_tables']:
        table = data['all_tables'][0]
        assert 'table_name' in table
        assert 'modification_count' in table
        assert 'churn_rate' in table
        assert 'stability_score' in table
        assert 'created_in' in table
        assert 'modified_in' in table


def test_overall_stability_score():
    """Test overall stability score calculation."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V2__create_orders.sql', 'sql': 'CREATE TABLE APP.ORDERS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V3__create_products.sql', 'sql': 'CREATE TABLE APP.PRODUCTS (ID NUMBER PRIMARY KEY)'},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    report = calculate_stability(state)
    
    # Overall score should be between 0 and 100
    assert 0 <= report.overall_stability_score <= 100
    
    # Overall score should be average of individual scores
    avg_score = sum(m.stability_score for m in report.all_table_metrics) / len(report.all_table_metrics)
    assert report.overall_stability_score == int(avg_score)


def test_modified_in_tracking():
    """Test that modified_in versions are tracked correctly."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY)'},
        {'filename': 'V2__modify_users.sql', 'sql': 'ALTER TABLE APP.USERS ADD COLUMN EMAIL VARCHAR2(255)'},
        {'filename': 'V3__modify_users_again.sql', 'sql': 'ALTER TABLE APP.USERS ADD COLUMN NAME VARCHAR2(100)'},
    ]
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    report = calculate_stability(state)
    
    users_metrics = next(m for m in report.all_table_metrics if m.table_name == 'APP.USERS')
    
    # Should track modified versions
    assert users_metrics.created_in == '1'
    assert len(users_metrics.modified_in) >= 1
