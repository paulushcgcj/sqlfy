"""
Tests for sqlfy.reconstructor — Reconstructor class, reconstruct(), reconstruct_at().
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sqlfy.core import apply_migrations
from sqlfy.reconstructor import (
    Reconstructor,
    MigrationResult,
    reconstruct,
    reconstruct_at,
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


# ─────────────────────────────────────────────
# reconstruct() — convenience wrapper
# ─────────────────────────────────────────────

class TestReconstruct:
    def test_returns_five_tables(self):
        graph = reconstruct(_load(*ALL_FILES))
        assert len(graph.tables) == 5

    def test_returns_four_fk_edges(self):
        graph = reconstruct(_load(*ALL_FILES))
        assert len(graph.edges) == 4

    def test_same_tables_as_apply_migrations(self):
        g1 = apply_migrations(_load(*ALL_FILES))
        g2 = reconstruct(_load(*ALL_FILES))
        assert set(g1.tables) == set(g2.tables)

    def test_same_edge_count_as_apply_migrations(self):
        g1 = apply_migrations(_load(*ALL_FILES))
        g2 = reconstruct(_load(*ALL_FILES))
        assert len(g1.edges) == len(g2.edges)

    def test_same_action_count_as_apply_migrations(self):
        g1 = apply_migrations(_load(*ALL_FILES))
        g2 = reconstruct(_load(*ALL_FILES))
        assert len(g1.actions) == len(g2.actions)


# ─────────────────────────────────────────────
# reconstruct_at() — point-in-time snapshots
# ─────────────────────────────────────────────

class TestReconstructAt:
    def test_at_v1_has_only_two_tables(self):
        graph = reconstruct_at(_load(*ALL_FILES), version='1')
        assert set(graph.tables) == {'APP.USERS', 'APP.PRODUCTS'}

    def test_at_v1_no_fk_edges(self):
        graph = reconstruct_at(_load(*ALL_FILES), version='1')
        assert graph.edges == []

    def test_at_v2_includes_order_tables(self):
        graph = reconstruct_at(_load(*ALL_FILES), version='2')
        assert 'APP.ORDERS' in graph.tables
        assert 'APP.ORDER_ITEMS' in graph.tables

    def test_at_v2_excludes_audit_log(self):
        graph = reconstruct_at(_load(*ALL_FILES), version='2')
        assert 'APP.AUDIT_LOG' not in graph.tables

    def test_at_v2_has_fk_edges(self):
        graph = reconstruct_at(_load(*ALL_FILES), version='2')
        assert len(graph.edges) > 0

    def test_at_v3_is_full_schema(self):
        graph = reconstruct_at(_load(*ALL_FILES), version='3')
        assert len(graph.tables) == 5

    def test_at_v1_users_has_no_last_login(self):
        # LAST_LOGIN is added in V3
        graph = reconstruct_at(_load(*ALL_FILES), version='1')
        col_names = [c.name for c in graph.tables['APP.USERS'].columns]
        assert 'LAST_LOGIN' not in col_names

    def test_at_v3_users_has_last_login(self):
        graph = reconstruct_at(_load(*ALL_FILES), version='3')
        col_names = [c.name for c in graph.tables['APP.USERS'].columns]
        assert 'LAST_LOGIN' in col_names

    def test_at_v1_only_v1_in_history(self):
        graph = reconstruct_at(_load(*ALL_FILES), version='1')
        versions = [m.version for m in graph.mig_hist]
        assert versions == ['1']

    def test_out_of_order_input_point_in_time(self):
        # Files provided in reverse order — at-version should still be correct
        fwd = reconstruct_at(_load(*ALL_FILES), version='2')
        rev = reconstruct_at(_load(
            'V3__add_audit.sql',
            'V2__create_orders.sql',
            'V1__create_core_tables.sql',
        ), version='2')
        assert set(fwd.tables) == set(rev.tables)


# ─────────────────────────────────────────────
# Reconstructor class — direct API
# ─────────────────────────────────────────────

class TestReconstructorClass:
    def test_apply_all_returns_schema_graph(self):
        r = Reconstructor()
        graph = r.apply_all(_load(*ALL_FILES))
        assert len(graph.tables) == 5

    def test_snapshot_returns_graph(self):
        r = Reconstructor()
        r.apply_all(_load('V1__create_core_tables.sql'))
        graph = r.snapshot()
        assert len(graph.tables) == 2

    def test_snapshot_is_independent(self):
        """Modifying a snapshot dict must not affect the reconstructor state."""
        r = Reconstructor()
        r.apply_all(_load('V1__create_core_tables.sql'))
        snap1 = r.snapshot()
        snap1.tables.clear()
        # The reconstructor still has the tables
        snap2 = r.snapshot()
        assert len(snap2.tables) == 2

    def test_reset_clears_all_state(self):
        r = Reconstructor()
        r.apply_all(_load('V1__create_core_tables.sql'))
        r.reset()
        graph = r.snapshot()
        assert len(graph.tables) == 0
        assert len(graph.seqs) == 0
        assert len(graph.actions) == 0
        assert len(graph.mig_hist) == 0

    def test_apply_file_returns_migration_result(self):
        r = Reconstructor()
        result = r.apply_file(
            'V1__create_core_tables.sql',
            (SAMPLES_DIR / 'V1__create_core_tables.sql').read_text(encoding='utf-8'),
        )
        assert isinstance(result, MigrationResult)
        assert result.version == '1'
        assert result.filename == 'V1__create_core_tables.sql'
        assert result.skipped is False

    def test_apply_file_records_actions(self):
        r = Reconstructor()
        result = r.apply_file(
            'V1__create_core_tables.sql',
            (SAMPLES_DIR / 'V1__create_core_tables.sql').read_text(encoding='utf-8'),
        )
        assert any(a.action == 'CREATE' and a.object_type == 'TABLE' for a in result.actions)

    def test_incremental_matches_batch(self):
        """Incremental per-file application must equal a single apply_all call."""
        files = _load(*ALL_FILES)

        r_batch = Reconstructor()
        g_batch = r_batch.apply_all(files)

        r_incr = Reconstructor()
        for f in files:
            r_incr.apply_file(f['filename'], f['sql'])
        g_incr = r_incr.snapshot()

        assert set(g_batch.tables) == set(g_incr.tables)
        assert len(g_batch.edges) == len(g_incr.edges)
        assert len(g_batch.actions) == len(g_incr.actions)

    def test_apply_up_to_stops_at_version(self):
        r = Reconstructor()
        graph = r.apply_up_to(_load(*ALL_FILES), version='2')
        assert 'APP.AUDIT_LOG' not in graph.tables
        assert 'APP.ORDERS' in graph.tables


# ─────────────────────────────────────────────
# MigrationResult idempotency
# ─────────────────────────────────────────────

class TestMigrationResultIdempotency:
    def test_skip_already_applied_version(self):
        r = Reconstructor()
        sql = (SAMPLES_DIR / 'V1__create_core_tables.sql').read_text(encoding='utf-8')
        r.apply_file('V1__create_core_tables.sql', sql)
        result2 = r.apply_file('V1__create_core_tables.sql', sql)
        assert result2.skipped is True

    def test_no_duplicate_tables_after_double_apply(self):
        r = Reconstructor()
        sql = (SAMPLES_DIR / 'V1__create_core_tables.sql').read_text(encoding='utf-8')
        r.apply_file('V1__create_core_tables.sql', sql)
        r.apply_file('V1__create_core_tables.sql', sql)
        graph = r.snapshot()
        assert len(graph.tables) == 2  # not 4

    def test_no_duplicate_actions_after_double_apply(self):
        r = Reconstructor()
        sql = (SAMPLES_DIR / 'V1__create_core_tables.sql').read_text(encoding='utf-8')
        result1 = r.apply_file('V1__create_core_tables.sql', sql)
        result2 = r.apply_file('V1__create_core_tables.sql', sql)
        assert len(result2.actions) == 0


# ─────────────────────────────────────────────
# Inline SQL via Reconstructor
# ─────────────────────────────────────────────

class TestReconstructorInlineSQL:
    def test_rename_column_via_regex_fallback(self):
        r = Reconstructor()
        r.apply_file('V1__base.sql', '''
            CREATE TABLE app.people (
                id    NUMBER(10) NOT NULL,
                fname VARCHAR2(50),
                CONSTRAINT pk_people PRIMARY KEY (id)
            );
        ''')
        r.apply_file('V2__rename.sql',
                     'ALTER TABLE app.people RENAME COLUMN fname TO first_name;')
        graph = r.snapshot()
        col_names = [c.name for c in graph.tables['APP.PEOPLE'].columns]
        assert 'FIRST_NAME' in col_names
        assert 'FNAME' not in col_names

    def test_rename_column_action_recorded(self):
        r = Reconstructor()
        r.apply_file('V1__base.sql', '''
            CREATE TABLE app.people (
                id    NUMBER(10) NOT NULL,
                fname VARCHAR2(50),
                CONSTRAINT pk_people PRIMARY KEY (id)
            );
        ''')
        r.apply_file('V2__rename.sql',
                     'ALTER TABLE app.people RENAME COLUMN fname TO first_name;')
        graph = r.snapshot()
        assert any(a.action == 'RENAME_COLUMN' for a in graph.actions)

    def test_create_index_via_reconstructor(self):
        r = Reconstructor()
        r.apply_file('V1__base.sql', '''
            CREATE TABLE app.items (
                id   NUMBER(10) NOT NULL,
                code VARCHAR2(20),
                CONSTRAINT pk_items PRIMARY KEY (id)
            );
        ''')
        r.apply_file('V2__idx.sql',
                     'CREATE INDEX idx_items_code ON app.items (code);')
        graph = r.snapshot()
        idx_names = [i.name for i in graph.tables['APP.ITEMS'].indexes]
        assert 'IDX_ITEMS_CODE' in idx_names

    def test_drop_table_via_reconstructor(self):
        r = Reconstructor()
        r.apply_file('V1__base.sql', '''
            CREATE TABLE app.tmp (
                id NUMBER(10) NOT NULL,
                CONSTRAINT pk_tmp PRIMARY KEY (id)
            );
        ''')
        r.apply_file('V2__drop.sql', 'DROP TABLE app.tmp;')
        graph = r.snapshot()
        assert 'APP.TMP' not in graph.tables
