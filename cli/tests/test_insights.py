"""
Tests for sqlfy.insights — InsightsEngine, InsightsReport, Finding.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sqlfy.core import apply_migrations
from sqlfy.domain.schema_state import (
    SchemaStateBuilder, SchemaState, TableState, ColumnState,
    ConstraintState, IndexState, RelationshipState, SequenceState,
    MigrationStep,
)
from sqlfy.analysis.insights import (
    InsightsEngine, InsightsReport, Finding,
    _detect_god_tables, _detect_surprising_joins,
    GodTableFinding, SurprisingJoinFinding,
)

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


# ─────────────────────────────────────────────
# God-table and surprising-join detection
# ─────────────────────────────────────────────

def _build_multicommunity_state() -> SchemaState:
    """Build a synthetic SchemaState with 3 communities + a central god table."""

    ts: dict[str, TableState] = {}
    rels: list[RelationshipState] = []

    def _table(full: str, schema: str, name: str, has_pk: bool = True) -> str:
        ts[full] = TableState(
            schema=schema, name=name, full_name=full,
            columns=[ColumnState(
                name='ID', data_type='NUMBER', raw_type='NUMBER',
                precision=None, scale=None, nullable=False,
                default=None, is_pk=True, is_fk=False,
                is_unique=False, comment=None,
            )],
            constraints=[], indexes=[],
            comment=None, created_in='V1', modified_in=[],
            column_count=1, has_pk=True,
            pk_columns=['ID'],
        )
        return full

    def _fk(from_tbl: str, to_tbl: str, col: str = 'ID', name: str | None = None) -> None:
        rels.append(RelationshipState(
            id=name or f'fk_{from_tbl}_{to_tbl}',
            from_table=from_tbl, from_columns=[col],
            to_table=to_tbl, to_columns=['ID'],
            constraint_name=name, on_delete=None,
            cardinality='many_to_one',
        ))

    # Communities
    comm_1 = [_table('ORD.ORDER',         'ORD', 'ORDER'),
              _table('ORD.ORDER_LINE',    'ORD', 'ORDER_LINE'),
              _table('ORD.INVOICE',       'ORD', 'INVOICE'),
              _table('ORD.SHIPMENT',      'ORD', 'SHIPMENT'),
              _table('ORD.PAYMENT',       'ORD', 'PAYMENT')]

    comm_2 = [_table('CUST.CUSTOMER',     'CUST', 'CUSTOMER'),
              _table('CUST.ADDRESS',      'CUST', 'ADDRESS'),
              _table('CUST.CONTACT',      'CUST', 'CONTACT'),
              _table('CUST.PREFERENCE',   'CUST', 'PREFERENCE'),
              _table('CUST.LOYALTY',      'CUST', 'LOYALTY')]

    comm_3 = [_table('HR.EMPLOYEE',       'HR', 'EMPLOYEE'),
              _table('HR.DEPARTMENT',     'HR', 'DEPARTMENT'),
              _table('HR.ROLE',           'HR', 'ROLE'),
              _table('HR.SALARY_GRADE',   'HR', 'SALARY_GRADE'),
              _table('HR.LEAVE',          'HR', 'LEAVE')]

    # God table connected to ALL other tables
    god = _table('HUB.CENTRAL', 'HUB', 'CENTRAL')
    for tbl in comm_1 + comm_2 + comm_3:
        _fk(god, tbl, name=f'fk_central_{tbl.replace(".", "_")}')

    # Intra-community FKs (so communities have internal structure)
    _fk(comm_1[1], comm_1[0])  # ORDER_LINE → ORDER
    _fk(comm_1[2], comm_1[0])  # INVOICE → ORDER
    _fk(comm_2[1], comm_2[0])  # ADDRESS → CUSTOMER
    _fk(comm_2[2], comm_2[0])  # CONTACT → CUSTOMER
    _fk(comm_3[1], comm_3[0])  # DEPARTMENT → EMPLOYEE (actually EMPLOYEE belongs to dept but FK wise let's say EMPLOYEE references DEPARTMENT)
    _fk(comm_3[0], comm_3[1])  # EMPLOYEE → DEPARTMENT
    _fk(comm_3[2], comm_3[1])  # ROLE → DEPARTMENT

    # Cross-community surprising joins
    _fk(comm_1[0], comm_2[0], col='CUSTOMER_ID', name='fk_order_customer')        # ORDER → CUSTOMER (expected)
    _fk(comm_1[3], comm_3[0], col='APPROVED_BY', name='fk_shipment_approver')     # SHIPMENT → EMPLOYEE (surprising)

    return SchemaState(
        version='1',
        generated_at='2026-01-01T00:00:00',
        fingerprint='test1234567890ab',
        dialect='oracle',
        tables=ts,
        sequences={},
        relationships=rels,
        migration_history=[MigrationStep(version='1', description='init')],
        stats={},
    )


COMMUNITIES_3: dict[int, list[str]] = {
    1: ['ORD.ORDER', 'ORD.ORDER_LINE', 'ORD.INVOICE', 'ORD.SHIPMENT', 'ORD.PAYMENT'],
    2: ['CUST.CUSTOMER', 'CUST.ADDRESS', 'CUST.CONTACT', 'CUST.PREFERENCE', 'CUST.LOYALTY'],
    3: ['HR.EMPLOYEE', 'HR.DEPARTMENT', 'HR.ROLE', 'HR.SALARY_GRADE', 'HR.LEAVE'],
}


class TestGodTableDetection:
    def test_detects_god_table(self):
        state = _build_multicommunity_state()
        result = _detect_god_tables(state, communities=COMMUNITIES_3)
        names = [g.table_name for g in result]
        assert 'HUB.CENTRAL' in names
        assert names[0] == 'HUB.CENTRAL'  # top rank

    def test_god_table_degree_counts(self):
        state = _build_multicommunity_state()
        result = _detect_god_tables(state)
        # HUB.CENTRAL has FK outgoing to 15 tables
        god = next(g for g in result if g.table_name == 'HUB.CENTRAL')
        assert god.degree == 15
        assert god.out_degree == 15
        assert god.in_degree == 0

    def test_god_table_community_label(self):
        state = _build_multicommunity_state()
        result = _detect_god_tables(state, communities=COMMUNITIES_3)
        god = next(g for g in result if g.table_name == 'HUB.CENTRAL')
        # HUB.CENTRAL is not in any community in our dict
        assert god.community_id is None

    def test_empty_state_returns_empty(self):
        state = SchemaState(
            version='0', generated_at='', fingerprint='', dialect='oracle',
            tables={}, sequences={}, relationships=[],
            migration_history=[], stats={},
        )
        assert _detect_god_tables(state) == []

    def test_few_tables_no_god(self):
        state = _build_multicommunity_state()
        # Remove HUB.CENTRAL from tables for this test
        del state.tables['HUB.CENTRAL']
        result = _detect_god_tables(state)
        assert len(result) == 0


class TestSurprisingJoinDetection:
    def test_detects_cross_community_joins(self):
        state = _build_multicommunity_state()
        result = _detect_surprising_joins(state, communities=COMMUNITIES_3)
        assert len(result) >= 1

    def test_shipment_to_employee_is_surprising(self):
        state = _build_multicommunity_state()
        result = _detect_surprising_joins(state, communities=COMMUNITIES_3)
        findings = [s for s in result if s.from_table == 'ORD.SHIPMENT']
        assert len(findings) >= 1
        assert 'HR.EMPLOYEE' in findings[0].to_table

    def test_intra_community_not_flagged(self):
        state = _build_multicommunity_state()
        result = _detect_surprising_joins(state, communities=COMMUNITIES_3)
        for s in result:
            assert s.from_community != s.to_community

    def test_none_communities_returns_empty(self):
        state = _build_multicommunity_state()
        result = _detect_surprising_joins(state, communities=None)
        assert result == []

    def test_empty_relationships_returns_empty(self):
        state = SchemaState(
            version='0', generated_at='', fingerprint='', dialect='oracle',
            tables={}, sequences={}, relationships=[],
            migration_history=[], stats={},
        )
        assert _detect_surprising_joins(state, communities=COMMUNITIES_3) == []


class TestInsightsReportNewFields:
    def test_report_includes_god_tables(self):
        state = _build_multicommunity_state()
        report = InsightsEngine.analyse(state, communities=COMMUNITIES_3)
        assert len(report.god_tables) > 0
        codes = {f.code for f in report.findings}
        assert 'GOD_TABLE' in codes

    def test_report_includes_surprising_joins(self):
        state = _build_multicommunity_state()
        report = InsightsEngine.analyse(state, communities=COMMUNITIES_3)
        assert len(report.surprising_joins) > 0
        codes = {f.code for f in report.findings}
        assert 'SURPRISING_JOIN' in codes

    def test_to_json_includes_new_fields(self):
        state = _build_multicommunity_state()
        report = InsightsEngine.analyse(state, communities=COMMUNITIES_3)
        data = json.loads(report.to_json())
        assert 'godTables' in data
        assert 'surprisingJoins' in data
        assert len(data['godTables']) > 0
        assert len(data['surprisingJoins']) > 0

    def test_to_dict_includes_new_fields(self):
        state = _build_multicommunity_state()
        report = InsightsEngine.analyse(state, communities=COMMUNITIES_3)
        d = report.to_dict()
        assert 'godTables' in d
        assert 'surprisingJoins' in d

    def test_to_text_includes_new_sections(self):
        state = _build_multicommunity_state()
        report = InsightsEngine.analyse(state, communities=COMMUNITIES_3)
        text = report.to_text()
        assert 'GOD TABLES' in text
        assert 'SURPRISING CROSS-DOMAIN JOINS' in text

    def test_without_communities_new_fields_still_populated(self):
        report = InsightsEngine.analyse(_build_multicommunity_state())
        assert len(report.god_tables) > 0  # god tables detected regardless of communities
        assert report.surprising_joins == []  # surprising joins need communities
        codes = {f.code for f in report.findings}
        assert 'GOD_TABLE' in codes
        assert 'SURPRISING_JOIN' not in codes

    def test_json_new_fields_have_correct_shape(self):
        state = _build_multicommunity_state()
        report = InsightsEngine.analyse(state, communities=COMMUNITIES_3)
        data = json.loads(report.to_json())
        gt = data['godTables'][0]
        assert 'tableName' in gt
        assert 'degree' in gt
        assert 'inDegree' in gt
        assert 'outDegree' in gt
        sj = data['surprisingJoins'][0]
        assert 'fromTable' in sj
        assert 'toTable' in sj
        assert 'viaColumn' in sj
        assert 'surpriseScore' in sj
