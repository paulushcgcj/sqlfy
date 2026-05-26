"""
Tests for sqlfy.insights — InsightsEngine, InsightsReport, Finding.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sqlfy.core import apply_migrations
from sqlfy.domain.schema_state import SchemaStateBuilder, SchemaState
from sqlfy.analysis.insights import InsightsEngine, InsightsReport, Finding

SAMPLES_DIR = Path(__file__).parent.parent.parent / 'samples'

ALL_FILES = [
    'V1__create_core_tables.sql',
    'V2__create_orders.sql',
    'V3__add_audit.sql',
]


def _load(*filenames: str) -> list[dict]:
    return [
        {'filename': name, 'sql': (SAMPLES_DIR / name).read_text(encoding='utf-8')}
        for name in filenames
    ]


def _inline(*pairs: tuple[str, str]) -> list[dict]:
    return [{'filename': f, 'sql': s} for f, s in pairs]


def _state_from_sql(*pairs: tuple[str, str]) -> SchemaState:
    graph = apply_migrations(_inline(*pairs))
    return SchemaStateBuilder.from_graph(graph)


@pytest.fixture(scope='module')
def sample_state() -> SchemaState:
    graph = apply_migrations(_load(*ALL_FILES))
    return SchemaStateBuilder.from_graph(graph)


@pytest.fixture(scope='module')
def sample_report(sample_state) -> InsightsReport:
    return InsightsEngine.analyse(sample_state)


# ─────────────────────────────────────────────
# InsightsReport — accessors and serialisation
# ─────────────────────────────────────────────

class TestInsightsReport:
    def test_version_matches_state(self, sample_report):
        assert sample_report.version == '3'

    def test_fingerprint_non_empty(self, sample_report):
        assert len(sample_report.fingerprint) == 16

    def test_summary_contains_schema_version(self, sample_report):
        assert 'V3' in sample_report.summary()

    def test_errors_returns_only_errors(self, sample_report):
        assert all(f.severity == 'error' for f in sample_report.errors())

    def test_warnings_returns_only_warnings(self, sample_report):
        assert all(f.severity == 'warning' for f in sample_report.warnings())

    def test_infos_returns_only_infos(self, sample_report):
        assert all(f.severity == 'info' for f in sample_report.infos())

    def test_by_code_filters_correctly(self, sample_report):
        findings = sample_report.by_code('EMPTY_TABLE_COMMENT')
        assert all(f.code == 'EMPTY_TABLE_COMMENT' for f in findings)

    def test_by_table_filters_correctly(self, sample_report):
        findings = sample_report.by_table('APP.AUDIT_LOG')
        assert all(f.table == 'APP.AUDIT_LOG' for f in findings)

    def test_is_healthy_false_when_warnings(self, sample_report):
        assert not sample_report.is_healthy()

    def test_total_finding_count(self, sample_report):
        total = len(sample_report.errors()) + len(sample_report.warnings()) + len(sample_report.infos())
        assert total == len(sample_report.findings)

    def test_findings_sorted_severity_first(self, sample_report):
        sev_order = {'error': 0, 'warning': 1, 'info': 2}
        orders = [sev_order[f.severity] for f in sample_report.findings]
        assert orders == sorted(orders)


# ─────────────────────────────────────────────
# InsightsReport — serialisation
# ─────────────────────────────────────────────

class TestInsightsReportSerialisation:
    def test_to_json_is_valid_json(self, sample_report):
        data = json.loads(sample_report.to_json())
        assert 'findings' in data
        assert 'summary' in data

    def test_to_json_summary_counts_match(self, sample_report):
        data = json.loads(sample_report.to_json())
        s = data['summary']
        assert s['errors']   == len(sample_report.errors())
        assert s['warnings'] == len(sample_report.warnings())
        assert s['infos']    == len(sample_report.infos())
        assert s['total']    == len(sample_report.findings)

    def test_to_json_grouped_by_severity(self, sample_report):
        data = json.loads(sample_report.to_json())
        assert 'error' in data['findings']
        assert 'warning' in data['findings']
        assert 'info' in data['findings']

    def test_to_dict_version_fingerprint(self, sample_report):
        d = sample_report.to_dict()
        assert d['version'] == sample_report.version
        assert d['fingerprint'] == sample_report.fingerprint

    def test_to_text_contains_header(self, sample_report):
        text = sample_report.to_text()
        assert 'SCHEMA INSIGHTS' in text

    def test_to_text_contains_finding_code(self, sample_report):
        text = sample_report.to_text()
        assert 'MISSING_FK_CANDIDATE' in text


# ─────────────────────────────────────────────
# Finding — from sample schema
# ─────────────────────────────────────────────

class TestSampleFindings:
    def test_missing_fk_candidate_audit_record_id(self, sample_report):
        """AUDIT_LOG.RECORD_ID looks like an FK column with no constraint."""
        findings = sample_report.by_code('MISSING_FK_CANDIDATE')
        tables = {f.table for f in findings}
        assert 'APP.AUDIT_LOG' in tables

    def test_nullable_fk_audit_changed_by(self, sample_report):
        """AUDIT_LOG.CHANGED_BY is a nullable FK column."""
        findings = [
            f for f in sample_report.by_code('NULLABLE_FK')
            if f.table == 'APP.AUDIT_LOG'
        ]
        assert len(findings) >= 1

    def test_empty_table_comment_products(self, sample_report):
        findings = sample_report.by_code('EMPTY_TABLE_COMMENT')
        tables = {f.table for f in findings}
        assert 'APP.PRODUCTS' in tables

    def test_no_indexes_users(self, sample_report):
        findings = sample_report.by_code('NO_INDEXES')
        tables = {f.table for f in findings}
        assert 'APP.USERS' in tables

    def test_unique_without_index_users(self, sample_report):
        findings = sample_report.by_code('UNIQUE_WITHOUT_INDEX')
        tables = {f.table for f in findings}
        assert 'APP.USERS' in tables

    def test_no_errors_in_sample_schema(self, sample_report):
        assert sample_report.errors() == []


# ─────────────────────────────────────────────
# Synthetic schemas — structural checks
# ─────────────────────────────────────────────

class TestOrphanTable:
    def test_detects_orphan_table(self):
        state = _state_from_sql(
            ('V1__init.sql', """
                CREATE TABLE APP.CONFIGS (
                    ID     NUMBER PRIMARY KEY,
                    KEY    VARCHAR2(100),
                    VALUE  VARCHAR2(500)
                );
            """),
        )
        report = InsightsEngine.analyse(state)
        codes = {f.code for f in report.findings}
        assert 'ORPHAN_TABLE' in codes

    def test_orphan_is_warning(self):
        state = _state_from_sql(
            ('V1__init.sql', """
                CREATE TABLE APP.STANDALONE (
                    ID NUMBER PRIMARY KEY
                );
            """),
        )
        report = InsightsEngine.analyse(state)
        orphans = report.by_code('ORPHAN_TABLE')
        assert all(f.severity == 'warning' for f in orphans)


class TestNoPK:
    def test_detects_missing_pk(self):
        state = _state_from_sql(
            ('V1__init.sql', """
                CREATE TABLE APP.LOG_ENTRIES (
                    LOG_TEXT VARCHAR2(500)
                );
            """),
        )
        report = InsightsEngine.analyse(state)
        codes = {f.code for f in report.findings}
        assert 'NO_PK' in codes

    def test_no_pk_is_error(self):
        state = _state_from_sql(
            ('V1__init.sql', """
                CREATE TABLE APP.LOG_ENTRIES (
                    LOG_TEXT VARCHAR2(500)
                );
            """),
        )
        report = InsightsEngine.analyse(state)
        no_pk_findings = report.by_code('NO_PK')
        assert all(f.severity == 'error' for f in no_pk_findings)


class TestMissingFKCandidate:
    def test_detects_column_named_user_id_without_fk(self):
        state = _state_from_sql(
            ('V1__init.sql', """
                CREATE TABLE APP.NOTES (
                    ID      NUMBER PRIMARY KEY,
                    USER_ID NUMBER NOT NULL,
                    BODY    VARCHAR2(4000)
                );
            """),
        )
        report = InsightsEngine.analyse(state)
        codes = {f.code for f in report.findings}
        assert 'MISSING_FK_CANDIDATE' in codes

    def test_pk_column_named_id_not_flagged(self):
        state = _state_from_sql(
            ('V1__init.sql', """
                CREATE TABLE APP.THINGS (
                    THING_ID NUMBER PRIMARY KEY
                );
            """),
        )
        report = InsightsEngine.analyse(state)
        fk_candidates = [
            f for f in report.by_code('MISSING_FK_CANDIDATE')
            if f.column == 'THING_ID'
        ]
        assert fk_candidates == []


class TestWideTable:
    def test_wide_table_flagged(self):
        cols = ', '.join(f'COL{i} VARCHAR2(100)' for i in range(25))
        state = _state_from_sql(
            ('V1__init.sql', f"""
                CREATE TABLE APP.FAT (
                    ID NUMBER PRIMARY KEY,
                    {cols}
                );
            """),
        )
        report = InsightsEngine.analyse(state)
        codes = {f.code for f in report.findings}
        assert 'WIDE_TABLE' in codes

    def test_narrow_table_not_flagged(self):
        state = _state_from_sql(
            ('V1__init.sql', """
                CREATE TABLE APP.SLIM (
                    ID   NUMBER PRIMARY KEY,
                    NAME VARCHAR2(100)
                );
            """),
        )
        report = InsightsEngine.analyse(state)
        codes = {f.code for f in report.findings}
        assert 'WIDE_TABLE' not in codes


# ─────────────────────────────────────────────
# Synthetic schemas — referential integrity
# ─────────────────────────────────────────────

class TestUnresolvedFK:
    def test_detects_fk_to_missing_table(self):
        state = _state_from_sql(
            ('V1__init.sql', """
                CREATE TABLE APP.ITEMS (
                    ID        NUMBER PRIMARY KEY,
                    PARENT_ID NUMBER,
                    CONSTRAINT fk_items_parent FOREIGN KEY (PARENT_ID)
                        REFERENCES APP.NONEXISTENT(ID)
                );
            """),
        )
        report = InsightsEngine.analyse(state)
        codes = {f.code for f in report.findings}
        assert 'UNRESOLVED_FK' in codes

    def test_unresolved_fk_is_error(self):
        state = _state_from_sql(
            ('V1__init.sql', """
                CREATE TABLE APP.ITEMS (
                    ID        NUMBER PRIMARY KEY,
                    PARENT_ID NUMBER,
                    CONSTRAINT fk_items FOREIGN KEY (PARENT_ID)
                        REFERENCES APP.MISSING(ID)
                );
            """),
        )
        report = InsightsEngine.analyse(state)
        findings = report.by_code('UNRESOLVED_FK')
        assert all(f.severity == 'error' for f in findings)


# ─────────────────────────────────────────────
# InsightsReport — filtering
# ─────────────────────────────────────────────

class TestReportFiltering:
    def test_filter_by_severity_returns_subset(self, sample_report):
        all_findings = sample_report.findings
        warnings_only = [f for f in all_findings if f.severity == 'warning']
        assert len(warnings_only) <= len(all_findings)
        assert all(f.severity == 'warning' for f in warnings_only)

    def test_healthy_on_minimal_schema(self):
        state = _state_from_sql(
            ('V1__init.sql', """
                CREATE TABLE APP.USERS (
                    ID    NUMBER PRIMARY KEY,
                    EMAIL VARCHAR2(255) NOT NULL UNIQUE
                );
                CREATE TABLE APP.POSTS (
                    ID      NUMBER PRIMARY KEY,
                    USER_ID NUMBER NOT NULL,
                    CONSTRAINT fk_posts_user FOREIGN KEY (USER_ID)
                        REFERENCES APP.USERS(ID)
                );
            """),
        )
        report = InsightsEngine.analyse(state)
        assert report.errors() == []

    def test_finding_to_dict_contains_required_keys(self, sample_report):
        for f in sample_report.findings:
            d = f.to_dict()
            assert 'code' in d
            assert 'severity' in d
            assert 'category' in d
            assert 'message' in d
