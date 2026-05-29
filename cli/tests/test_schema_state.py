"""
Tests for sqlfy.schema_state — SchemaStateBuilder and SchemaState.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sqlfy.core import apply_migrations
from sqlfy.domain.schema_state import (
    SchemaStateBuilder,
    SchemaState,
    TableState,
    ColumnState,
    RelationshipState,
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


@pytest.fixture(scope='module')
def state() -> SchemaState:
    graph = apply_migrations(_load(*ALL_FILES))
    return SchemaStateBuilder.from_graph(graph)


# ─────────────────────────────────────────────
# SchemaState top-level fields
# ─────────────────────────────────────────────

class TestSchemaStateTopLevel:
    def test_version_is_latest(self, state):
        assert state.version == '3'

    def test_dialect_default(self, state):
        assert state.dialect == 'oracle'

    def test_generated_at_ends_with_z(self, state):
        assert state.generated_at.endswith('Z')

    def test_fingerprint_is_16_hex_chars(self, state):
        assert len(state.fingerprint) == 16
        assert all(c in '0123456789abcdef' for c in state.fingerprint)

    def test_fingerprint_is_stable(self):
        # Same input → same fingerprint every time
        g1 = apply_migrations(_load(*ALL_FILES))
        g2 = apply_migrations(_load(*ALL_FILES))
        s1 = SchemaStateBuilder.from_graph(g1)
        s2 = SchemaStateBuilder.from_graph(g2)
        assert s1.fingerprint == s2.fingerprint

    def test_migration_history_versions(self, state):
        versions = [m.version for m in state.migration_history]
        assert versions == ['1', '2', '3']


# ─────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────

class TestSchemaStateStats:
    def test_table_count(self, state):
        assert state.stats['table_count'] == 5

    def test_sequence_count(self, state):
        assert state.stats['sequence_count'] == 4

    def test_relationship_count(self, state):
        assert state.stats['relationship_count'] == 4

    def test_migration_count(self, state):
        assert state.stats['migration_count'] == 3

    def test_tables_without_pk(self, state):
        assert state.stats['tables_without_pk'] == 0

    def test_column_count_is_positive(self, state):
        assert state.stats['column_count'] > 0


# ─────────────────────────────────────────────
# Tables / TableState
# ─────────────────────────────────────────────

class TestTableState:
    def test_all_tables_present(self, state):
        assert set(state.tables) == {
            'APP.USERS', 'APP.PRODUCTS', 'APP.ORDERS',
            'APP.ORDER_ITEMS', 'APP.AUDIT_LOG',
        }

    def test_users_has_pk(self, state):
        assert state.tables['APP.USERS'].has_pk is True

    def test_users_pk_columns(self, state):
        assert 'USER_ID' in state.tables['APP.USERS'].pk_columns

    def test_table_state_type(self, state):
        assert isinstance(state.tables['APP.USERS'], TableState)

    def test_table_comment(self, state):
        assert state.tables['APP.USERS'].comment == 'Core user accounts'

    def test_created_in(self, state):
        assert state.tables['APP.USERS'].created_in == '1'

    def test_modified_in_includes_v3(self, state):
        assert '3' in state.tables['APP.USERS'].modified_in

    def test_column_count_matches_columns_list(self, state):
        t = state.tables['APP.USERS']
        assert t.column_count == len(t.columns)

    def test_orders_has_fk_columns(self, state):
        fk_cols = state.tables['APP.ORDERS'].fk_columns
        assert len(fk_cols) > 0


# ─────────────────────────────────────────────
# ColumnState
# ─────────────────────────────────────────────

class TestColumnState:
    def test_column_type(self, state):
        users = state.tables['APP.USERS']
        col = next(c for c in users.columns if c.name == 'USER_ID')
        assert isinstance(col, ColumnState)

    def test_pk_column_is_marked(self, state):
        col = next(
            c for c in state.tables['APP.USERS'].columns if c.name == 'USER_ID'
        )
        assert col.is_pk is True

    def test_non_pk_column_not_marked(self, state):
        col = next(
            c for c in state.tables['APP.USERS'].columns if c.name == 'EMAIL'
        )
        assert col.is_pk is False

    def test_fk_column_is_marked(self, state):
        # USER_ID in ORDERS is an FK
        col = next(
            c for c in state.tables['APP.ORDERS'].columns if c.name == 'USER_ID'
        )
        assert col.is_fk is True

    def test_column_data_type_rendered(self, state):
        col = next(
            c for c in state.tables['APP.USERS'].columns if c.name == 'USER_ID'
        )
        assert '(' in col.data_type or col.raw_type in col.data_type

    def test_column_comment(self, state):
        col = next(
            c for c in state.tables['APP.USERS'].columns if c.name == 'STATUS'
        )
        assert col.comment == 'Account lifecycle status'


# ─────────────────────────────────────────────
# Sequences
# ─────────────────────────────────────────────

class TestSequenceState:
    def test_sequences_present(self, state):
        assert len(state.sequences) == 4

    def test_seq_users_present(self, state):
        assert 'APP.SEQ_USERS' in state.sequences

    def test_seq_orders_start_with(self, state):
        assert state.sequences['APP.SEQ_ORDERS'].start_with == 1000


# ─────────────────────────────────────────────
# Relationships
# ─────────────────────────────────────────────

class TestRelationshipState:
    def test_relationship_count(self, state):
        assert len(state.relationships) == 4

    def test_relationship_type(self, state):
        assert all(isinstance(r, RelationshipState) for r in state.relationships)

    def test_orders_to_users_exists(self, state):
        assert any(
            r.from_table == 'APP.ORDERS' and r.to_table == 'APP.USERS'
            for r in state.relationships
        )

    def test_cascade_on_delete(self, state):
        rel = next(
            r for r in state.relationships
            if r.from_table == 'APP.ORDERS' and r.to_table == 'APP.USERS'
        )
        assert rel.on_delete == 'CASCADE'

    def test_cardinality_assigned(self, state):
        for rel in state.relationships:
            assert rel.cardinality in ('many_to_one', 'one_to_one', 'unknown')


# ─────────────────────────────────────────────
# Accessors
# ─────────────────────────────────────────────

class TestSchemaStateAccessors:
    def test_get_table_by_full_name(self, state):
        t = state.get_table('APP.USERS')
        assert t is not None and t.name == 'USERS'

    def test_get_table_case_insensitive(self, state):
        t = state.get_table('app.users')
        assert t is not None

    def test_get_table_by_short_name(self, state):
        t = state.get_table('USERS')
        assert t is not None

    def test_get_table_missing_returns_none(self, state):
        assert state.get_table('NONEXISTENT') is None

    def test_tables_in_schema(self, state):
        tables = state.tables_in_schema('APP')
        assert len(tables) == 5

    def test_tables_without_pk_empty(self, state):
        assert state.tables_without_pk() == []

    def test_orphan_tables_does_not_include_orders(self, state):
        orphan_names = {t.full_name for t in state.orphan_tables()}
        assert 'APP.ORDERS' not in orphan_names

    def test_tables_referencing_users(self, state):
        refs = state.tables_referencing('APP.USERS')
        names = {t.full_name for t in refs}
        assert 'APP.ORDERS' in names

    def test_tables_referenced_by_orders(self, state):
        targets = state.tables_referenced_by('APP.ORDERS')
        names = {t.full_name for t in targets}
        assert 'APP.USERS' in names


# ─────────────────────────────────────────────
# Serialisation
# ─────────────────────────────────────────────

class TestSchemaStateSerialization:
    def test_to_dict_returns_dict(self, state):
        assert isinstance(state.to_dict(), dict)

    def test_to_dict_has_required_keys(self, state):
        d = state.to_dict()
        assert 'tables' in d
        assert 'sequences' in d
        assert 'relationships' in d
        assert 'migration_history' in d
        assert 'stats' in d

    def test_to_json_is_valid_json(self, state):
        j = state.to_json()
        parsed = json.loads(j)
        assert parsed['version'] == '3'

    def test_to_dict_preserves_int_values(self, state):
        # Verify _deep_asdict's missing return obj bug is fixed
        d = state.to_dict()
        users = d['tables']['APP.USERS']
        assert isinstance(users['column_count'], int)
        assert users['column_count'] > 0

    def test_to_dict_preserves_string_values(self, state):
        d = state.to_dict()
        users = d['tables']['APP.USERS']
        assert users['name'] == 'USERS'

    def test_to_dict_stats_are_ints(self, state):
        d = state.to_dict()
        assert isinstance(d['stats']['table_count'], int)
        assert d['stats']['table_count'] == 5

    def test_to_json_tables_are_serialisable(self, state):
        # All values inside tables should survive JSON round-trip intact
        j = state.to_json()
        d = json.loads(j)
        assert d['tables']['APP.USERS']['name'] == 'USERS'
        assert isinstance(d['tables']['APP.USERS']['columnCount'], int)
