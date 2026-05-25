"""
Tests for sqlfy.core — validates apply_migrations and build_chunks
using the shared SQL samples from <repo-root>/samples/.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sqlfy.core import apply_migrations, build_chunks

# Resolve samples directory: cli/tests/ → cli/ → repo root → samples/
SAMPLES_DIR = Path(__file__).parent.parent.parent / 'samples'


def _load(*filenames: str) -> list[dict]:
    """Load named SQL files from the samples directory."""
    return [
        {'filename': name, 'sql': (SAMPLES_DIR / name).read_text(encoding='utf-8')}
        for name in filenames
    ]


# ─────────────────────────────────────────────
# V1 only
# ─────────────────────────────────────────────

class TestV1:
    @pytest.fixture(scope='class')
    def graph(self):
        return apply_migrations(_load('V1__create_core_tables.sql'))

    def test_tables_created(self, graph):
        assert set(graph.tables) == {'APP.USERS', 'APP.PRODUCTS'}

    def test_sequences_created(self, graph):
        assert set(graph.seqs) == {'APP.SEQ_USERS', 'APP.SEQ_PRODUCTS'}

    def test_no_fk_edges(self, graph):
        assert graph.edges == []

    def test_migration_history(self, graph):
        assert len(graph.mig_hist) == 1
        assert graph.mig_hist[0].version == '1'

    def test_users_columns(self, graph):
        col_names = [c.name for c in graph.tables['APP.USERS'].columns]
        assert 'USER_ID' in col_names
        assert 'EMAIL' in col_names
        assert 'STATUS' in col_names

    def test_users_pk(self, graph):
        pks = [c for c in graph.tables['APP.USERS'].constraints if c.type == 'primary_key']
        assert len(pks) == 1
        assert 'USER_ID' in pks[0].columns

    def test_table_comment(self, graph):
        assert graph.tables['APP.USERS'].comments.get('__table__') == 'Core user accounts'

    def test_column_comment(self, graph):
        assert graph.tables['APP.USERS'].comments.get('STATUS') == 'Account lifecycle status'

    def test_seq_start_with(self, graph):
        assert graph.seqs['APP.SEQ_USERS'].start_with == 1
        assert graph.seqs['APP.SEQ_PRODUCTS'].start_with == 1

    def test_users_check_constraint(self, graph):
        checks = [c for c in graph.tables['APP.USERS'].constraints if c.type == 'check']
        assert any('status' in (c.check_expr or '').lower() for c in checks)


# ─────────────────────────────────────────────
# All three migrations
# ─────────────────────────────────────────────

class TestAllMigrations:
    @pytest.fixture(scope='class')
    def graph(self):
        return apply_migrations(_load(
            'V1__create_core_tables.sql',
            'V2__create_orders.sql',
            'V3__add_audit.sql',
        ))

    def test_table_count(self, graph):
        assert len(graph.tables) == 5

    def test_all_tables_present(self, graph):
        assert set(graph.tables) == {
            'APP.USERS', 'APP.PRODUCTS', 'APP.ORDERS',
            'APP.ORDER_ITEMS', 'APP.AUDIT_LOG',
        }

    def test_sequence_count(self, graph):
        assert len(graph.seqs) == 4

    def test_fk_edge_count(self, graph):
        assert len(graph.edges) == 4

    def test_fk_orders_to_users_cascade(self, graph):
        edge = next(
            e for e in graph.edges
            if e.from_table == 'APP.ORDERS' and e.to_table == 'APP.USERS'
        )
        assert edge.on_delete == 'CASCADE'

    def test_fk_items_to_orders_cascade(self, graph):
        edge = next(
            e for e in graph.edges
            if e.from_table == 'APP.ORDER_ITEMS' and e.to_table == 'APP.ORDERS'
        )
        assert edge.on_delete == 'CASCADE'

    def test_fk_items_to_products(self, graph):
        assert any(
            e.from_table == 'APP.ORDER_ITEMS' and e.to_table == 'APP.PRODUCTS'
            for e in graph.edges
        )

    def test_fk_audit_to_users(self, graph):
        assert any(
            e.from_table == 'APP.AUDIT_LOG' and e.to_table == 'APP.USERS'
            for e in graph.edges
        )

    def test_migration_history_versions(self, graph):
        versions = [m.version for m in graph.mig_hist]
        assert versions == ['1', '2', '3']

    def test_alter_table_adds_columns(self, graph):
        col_names = [c.name for c in graph.tables['APP.USERS'].columns]
        assert 'LAST_LOGIN' in col_names
        assert 'LOGIN_COUNT' in col_names

    def test_alter_table_recorded_in_modified(self, graph):
        assert '3' in graph.tables['APP.USERS'].modified_in

    def test_orders_seq_start_with(self, graph):
        assert graph.seqs['APP.SEQ_ORDERS'].start_with == 1000

    def test_orders_indexes(self, graph):
        idx_names = [i.name for i in graph.tables['APP.ORDERS'].indexes]
        assert 'IDX_ORDERS_USER' in idx_names
        assert 'IDX_ORDERS_STATUS' in idx_names

    def test_out_of_order_input_still_sorted(self):
        # Files provided in reverse order must produce the same graph
        graph_fwd = apply_migrations(_load(
            'V1__create_core_tables.sql',
            'V2__create_orders.sql',
            'V3__add_audit.sql',
        ))
        graph_rev = apply_migrations(_load(
            'V3__add_audit.sql',
            'V2__create_orders.sql',
            'V1__create_core_tables.sql',
        ))
        assert set(graph_fwd.tables) == set(graph_rev.tables)
        assert len(graph_fwd.edges) == len(graph_rev.edges)


# ─────────────────────────────────────────────
# Chunk builder
# ─────────────────────────────────────────────

class TestBuildChunks:
    @pytest.fixture(scope='class')
    def chunks(self):
        graph = apply_migrations(_load(
            'V1__create_core_tables.sql',
            'V2__create_orders.sql',
            'V3__add_audit.sql',
        ))
        return build_chunks(graph)

    def test_total_chunk_count(self, chunks):
        # 5 table chunks + 1 schema_summary + 1 relationship_map
        assert len(chunks) == 7

    def test_schema_summary_is_first(self, chunks):
        assert chunks[0].type == 'schema_summary'
        assert chunks[0].id == 'schema:summary'

    def test_relationship_map_is_last(self, chunks):
        assert chunks[-1].type == 'relationship_map'

    def test_table_chunks_present(self, chunks):
        table_chunks = [c for c in chunks if c.type == 'table']
        names = {c.meta['table_name'] for c in table_chunks}
        assert names == {'USERS', 'PRODUCTS', 'ORDERS', 'ORDER_ITEMS', 'AUDIT_LOG'}

    def test_schema_summary_meta(self, chunks):
        meta = chunks[0].meta
        assert meta['table_count'] == 5
        assert meta['edge_count'] == 4
        assert meta['seq_count'] == 4

    def test_users_chunk_content(self, chunks):
        users_chunk = next(c for c in chunks if c.meta.get('table_name') == 'USERS')
        assert 'USER_ID' in users_chunk.content
        assert 'EMAIL' in users_chunk.content
        assert 'PK' in users_chunk.content

    def test_chunk_ids_are_unique(self, chunks):
        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids))

    def test_relationship_map_content(self, chunks):
        rel_chunk = chunks[-1]
        assert 'APP.ORDERS' in rel_chunk.content
        assert 'APP.USERS' in rel_chunk.content
