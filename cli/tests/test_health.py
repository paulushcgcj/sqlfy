"""
Tests for migration folder health analysis.
"""

import json

from sqlfy.analysis.health import HealthAnalyzer, MigrationStatus
from sqlfy.analysis.insights import InsightsEngine
from sqlfy.reconstructor import reconstruct
from sqlfy.domain.schema_state import SchemaStateBuilder


def test_health_analyzer_basic():
    """Health analyzer produces report."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY, name VARCHAR2(100));'},
        {'filename': 'V2__create_orders.sql', 'sql': 'CREATE TABLE orders (id NUMBER PRIMARY KEY, user_id NUMBER);'},
        {'filename': 'V3__add_audit.sql', 'sql': 'CREATE TABLE audit_log (id NUMBER PRIMARY KEY);'},
    ]
    
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    insights_report = InsightsEngine.analyse(state)
    
    health_report = HealthAnalyzer.analyze(state, insights_report, './samples')
    
    assert health_report.total_migrations == len(files)
    assert health_report.safe_migrations + health_report.unsafe_migrations + health_report.irreversible_migrations == health_report.total_migrations
    assert 0 <= health_report.health_score.score <= 100
    assert health_report.health_score.grade in ['excellent', 'good', 'warning', 'critical']


def test_health_score_calculation():
    """Health score decreases with errors and warnings."""
    # Create migrations with known issues
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
        {'filename': 'V2__add_column.sql', 'sql': 'ALTER TABLE users ADD (status VARCHAR2(20) NOT NULL);'},  # ERROR: no default
    ]
    
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    insights_report = InsightsEngine.analyse(state)
    
    health_report = HealthAnalyzer.analyze(state, insights_report, './migrations')
    
    # Score should be less than 100 if there are any findings
    if len(insights_report.findings) > 0:
        assert health_report.health_score.score < 100
    
    # Error penalty should be 20 per error
    error_count = len(insights_report.errors())
    expected_error_penalty = error_count * 20
    assert health_report.health_score.breakdown['error_penalty'] == -expected_error_penalty


def test_irreversible_migrations_detected():
    """DROP TABLE and DROP COLUMN marked as irreversible."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
        {'filename': 'V2__drop_users.sql', 'sql': 'DROP TABLE users;'},
    ]
    
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    insights_report = InsightsEngine.analyse(state)
    
    health_report = HealthAnalyzer.analyze(state, insights_report, './migrations')
    
    assert health_report.irreversible_migrations == 1
    drop_migration = [m for m in health_report.migration_statuses if 'drop' in m.filename.lower()][0]
    assert drop_migration.status == 'irreversible'
    assert drop_migration.has_drop_table is True


def test_drop_column_marked_irreversible():
    """DROP COLUMN also marked as irreversible."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY, old_col VARCHAR2(50));'},
        {'filename': 'V2__drop_column.sql', 'sql': 'ALTER TABLE users DROP COLUMN old_col;'},
    ]
    
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    insights_report = InsightsEngine.analyse(state)
    
    health_report = HealthAnalyzer.analyze(state, insights_report, './migrations')
    
    assert health_report.irreversible_migrations == 1
    drop_migration = [m for m in health_report.migration_statuses if 'drop' in m.filename.lower()][0]
    assert drop_migration.status == 'irreversible'
    assert drop_migration.has_drop_column is True


def test_health_report_text_format():
    """Text format report is human-readable."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
        {'filename': 'V2__create_orders.sql', 'sql': 'CREATE TABLE orders (id NUMBER PRIMARY KEY);'},
    ]
    
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    insights_report = InsightsEngine.analyse(state)
    
    health_report = HealthAnalyzer.analyze(state, insights_report, './samples')
    text = health_report.to_text()
    
    assert 'Migration Folder Health Report' in text
    assert 'SUMMARY STATISTICS' in text
    assert 'HEALTH SCORE' in text
    assert str(health_report.total_migrations) in text
    assert 'V1__create_users.sql' in text
    assert 'V2__create_orders.sql' in text


def test_health_report_json_format():
    """JSON format report is valid and complete."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
        {'filename': 'V2__create_orders.sql', 'sql': 'CREATE TABLE orders (id NUMBER PRIMARY KEY);'},
    ]
    
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    insights_report = InsightsEngine.analyse(state)
    
    health_report = HealthAnalyzer.analyze(state, insights_report, './samples')
    json_str = health_report.to_json()
    
    data = json.loads(json_str)
    
    assert data['summary']['total_migrations'] == health_report.total_migrations
    assert data['health_score']['score'] == health_report.health_score.score
    assert 'migrations' in data
    assert len(data['migrations']) == health_report.total_migrations
    assert data['migrations'][0]['filename'] == 'V1__create_users.sql'


def test_grade_excellent():
    """Health grade is excellent for clean migrations."""
    files = [
        {'filename': 'V1__create_users.sql', 'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY, name VARCHAR2(100) NOT NULL);'},
    ]
    
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    insights_report = InsightsEngine.analyse(state)
    
    health_report = HealthAnalyzer.analyze(state, insights_report, './migrations')
    
    # Should have high score with no errors/warnings
    assert health_report.health_score.score >= 90
    assert health_report.health_score.grade == 'excellent'


def test_grade_critical_with_many_errors():
    """Health grade is critical with many errors."""
    files = [
        {'filename': 'V1__bad1.sql', 'sql': 'CREATE TABLE t1 (id NUMBER); ALTER TABLE t1 ADD (c1 VARCHAR2(20) NOT NULL);'},
        {'filename': 'V2__bad2.sql', 'sql': 'CREATE TABLE t2 (id NUMBER); ALTER TABLE t2 ADD (c2 VARCHAR2(20) NOT NULL);'},
        {'filename': 'V3__bad3.sql', 'sql': 'CREATE TABLE t3 (id NUMBER); ALTER TABLE t3 ADD (c3 VARCHAR2(20) NOT NULL);'},
    ]
    
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    insights_report = InsightsEngine.analyse(state)
    
    health_report = HealthAnalyzer.analyze(state, insights_report, './migrations')
    
    # With 3 ADD NOT NULL errors (3 × 20 = -60), score should be low
    assert health_report.health_score.score <= 50
    assert health_report.health_score.grade in ['warning', 'critical']


def test_safe_vs_unsafe_counts():
    """Safe and unsafe migration counts are correct."""
    files = [
        {'filename': 'V1__safe.sql', 'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
        {'filename': 'V2__unsafe.sql', 'sql': 'CREATE TABLE orders (id NUMBER); ALTER TABLE orders ADD (status VARCHAR2(20) NOT NULL);'},
        {'filename': 'V3__safe.sql', 'sql': 'CREATE TABLE products (id NUMBER PRIMARY KEY);'},
    ]
    
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    insights_report = InsightsEngine.analyse(state)
    
    health_report = HealthAnalyzer.analyze(state, insights_report, './migrations')
    
    assert health_report.total_migrations == 3
    # V2 should be unsafe due to ADD NOT NULL error
    assert health_report.unsafe_migrations >= 1
    assert health_report.safe_migrations >= 2


def test_findings_by_code_aggregation():
    """Findings are aggregated by code."""
    files = [
        {'filename': 'V1__users.sql', 'sql': 'CREATE TABLE users (id NUMBER); ALTER TABLE users ADD (c1 VARCHAR2(20) NOT NULL);'},
        {'filename': 'V2__orders.sql', 'sql': 'CREATE TABLE orders (id NUMBER); ALTER TABLE orders ADD (c2 VARCHAR2(20) NOT NULL);'},
    ]
    
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    insights_report = InsightsEngine.analyse(state)
    
    health_report = HealthAnalyzer.analyze(state, insights_report, './migrations')
    
    # Should have ADD_NOT_NULL_NO_DEFAULT findings
    assert 'ADD_NOT_NULL_NO_DEFAULT' in health_report.findings_by_code
    assert health_report.findings_by_code['ADD_NOT_NULL_NO_DEFAULT'] >= 2


def test_recommendation_for_errors():
    """Recommendation prioritizes errors."""
    files = [
        {'filename': 'V1__bad.sql', 'sql': 'CREATE TABLE t (id NUMBER); ALTER TABLE t ADD (c VARCHAR2(20) NOT NULL);'},
    ]
    
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    insights_report = InsightsEngine.analyse(state)
    
    health_report = HealthAnalyzer.analyze(state, insights_report, './migrations')
    
    # Should recommend fixing errors
    assert 'error' in health_report.health_score.recommendation.lower()
    assert 'production' in health_report.health_score.recommendation.lower()


def test_recommendation_for_warnings():
    """Recommendation mentions warnings when no errors."""
    files = [
        {'filename': 'V1__view.sql', 'sql': 'CREATE TABLE t (id NUMBER PRIMARY KEY); CREATE VIEW v AS SELECT * FROM t;'},
    ]
    
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    insights_report = InsightsEngine.analyse(state)
    
    health_report = HealthAnalyzer.analyze(state, insights_report, './migrations')
    
    # Should recommend reviewing warnings
    if len(insights_report.warnings()) > 0:
        assert 'warning' in health_report.health_score.recommendation.lower()


def test_safe_percentage_calculation():
    """Safe percentage is calculated correctly."""
    files = [
        {'filename': 'V1__safe.sql', 'sql': 'CREATE TABLE users (id NUMBER PRIMARY KEY);'},
        {'filename': 'V2__safe.sql', 'sql': 'CREATE TABLE orders (id NUMBER PRIMARY KEY);'},
        {'filename': 'V3__unsafe.sql', 'sql': 'CREATE TABLE t (id NUMBER); ALTER TABLE t ADD (c VARCHAR2(20) NOT NULL);'},
        {'filename': 'V4__safe.sql', 'sql': 'CREATE TABLE products (id NUMBER PRIMARY KEY);'},
    ]
    
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    insights_report = InsightsEngine.analyse(state)
    
    health_report = HealthAnalyzer.analyze(state, insights_report, './migrations')
    
    # 3 safe out of 4 = 75%
    assert health_report.safe_percentage == 75


def test_empty_folder():
    """Health report handles empty migration folder."""
    files = []
    
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    insights_report = InsightsEngine.analyse(state)
    
    health_report = HealthAnalyzer.analyze(state, insights_report, './migrations')
    
    assert health_report.total_migrations == 0
    assert health_report.safe_migrations == 0
    assert health_report.unsafe_migrations == 0
    assert health_report.irreversible_migrations == 0
    assert health_report.safe_percentage == 0
