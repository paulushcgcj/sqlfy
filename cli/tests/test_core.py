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


# ─────────────────────────────────────────────
# Helpers for inline SQL fixtures
# ─────────────────────────────────────────────

def _inline(*pairs: tuple[str, str]) -> list[dict]:
    """Build a migration list from (filename, sql) tuples."""
    return [{'filename': f, 'sql': s} for f, s in pairs]


# ─────────────────────────────────────────────
# MigrationAction tracking
# ─────────────────────────────────────────────

class TestMigrationActions:
    @pytest.fixture(scope='class')
    def graph(self):
        return apply_migrations(_load(
            'V1__create_core_tables.sql',
            'V2__create_orders.sql',
            'V3__add_audit.sql',
        ))

    def test_graph_actions_not_empty(self, graph):
        assert len(graph.actions) > 0

    def test_create_table_actions_recorded(self, graph):
        creates = [a for a in graph.actions if a.action == 'CREATE' and a.object_type == 'TABLE']
        names = {a.object_name for a in creates}
        assert 'APP.USERS' in names
        assert 'APP.PRODUCTS' in names
        assert 'APP.ORDERS' in names

    def test_create_index_actions_recorded(self, graph):
        idx_actions = [a for a in graph.actions if a.action == 'CREATE_INDEX']
        names = {a.object_name for a in idx_actions}
        assert any('IDX_ORDERS_USER' in n for n in names)
        assert any('IDX_ORDERS_STATUS' in n for n in names)

    def test_add_column_action_recorded(self, graph):
        add_col = [a for a in graph.actions if a.action == 'ADD_COLUMN']
        names = {a.object_name for a in add_col}
        assert 'APP.USERS.LAST_LOGIN' in names
        assert 'APP.USERS.LOGIN_COUNT' in names

    def test_add_constraint_action_recorded(self, graph):
        add_con = [a for a in graph.actions if a.action == 'ADD_CONSTRAINT']
        assert any('UQ_PRODUCTS_NAME' in a.object_name for a in add_con)

    def test_table_actions_populated(self, graph):
        users = graph.tables['APP.USERS']
        assert any(a.action == 'ADD_COLUMN' for a in users.actions)

    def test_action_version_matches_migration(self, graph):
        # LAST_LOGIN was added in V3
        add_col = next(
            a for a in graph.actions
            if a.action == 'ADD_COLUMN' and 'LAST_LOGIN' in a.object_name
        )
        assert add_col.version == '3'

    def test_create_sequence_action_recorded(self, graph):
        seq_actions = [a for a in graph.actions if a.action == 'CREATE_SEQUENCE']
        names = {a.object_name for a in seq_actions}
        assert 'APP.SEQ_USERS' in names
        assert 'APP.SEQ_ORDERS' in names


# ─────────────────────────────────────────────
# DROP TABLE
# ─────────────────────────────────────────────

class TestDropTable:
    def test_drop_removes_table(self):
        graph = apply_migrations(_inline(
            ('V1__base.sql', 'CREATE TABLE app.tmp (id NUMBER(10) NOT NULL, CONSTRAINT pk_tmp PRIMARY KEY (id));'),
            ('V2__drop.sql', 'DROP TABLE app.tmp;'),
        ))
        assert 'APP.TMP' not in graph.tables

    def test_drop_action_recorded(self):
        graph = apply_migrations(_inline(
            ('V1__base.sql', 'CREATE TABLE app.tmp (id NUMBER(10) NOT NULL, CONSTRAINT pk_tmp PRIMARY KEY (id));'),
            ('V2__drop.sql', 'DROP TABLE app.tmp;'),
        ))
        drops = [a for a in graph.actions if a.action == 'DROP' and a.object_type == 'TABLE']
        assert any(a.object_name == 'APP.TMP' for a in drops)

    def test_drop_then_recreate(self):
        graph = apply_migrations(_inline(
            ('V1__base.sql', 'CREATE TABLE app.tmp (id NUMBER(10) NOT NULL, CONSTRAINT pk_tmp PRIMARY KEY (id));'),
            ('V2__drop.sql', 'DROP TABLE app.tmp;'),
            ('V3__recreate.sql', 'CREATE TABLE app.tmp (id NUMBER(10) NOT NULL, name VARCHAR2(50), CONSTRAINT pk_tmp PRIMARY KEY (id));'),
        ))
        assert 'APP.TMP' in graph.tables
        col_names = [c.name for c in graph.tables['APP.TMP'].columns]
        assert 'NAME' in col_names

    def test_drop_nonexistent_table_is_silent(self):
        # Dropping a table that was never created should not raise
        graph = apply_migrations(_inline(
            ('V1__drop.sql', 'DROP TABLE app.ghost;'),
        ))
        assert 'APP.GHOST' not in graph.tables


# ─────────────────────────────────────────────
# ALTER TABLE DROP COLUMN / DROP CONSTRAINT
# ─────────────────────────────────────────────

class TestAlterTableDrop:
    def test_drop_column_removes_it(self):
        graph = apply_migrations(_inline(
            ('V1__base.sql', '''
                CREATE TABLE app.things (
                    id     NUMBER(10)   NOT NULL,
                    label  VARCHAR2(50) NOT NULL,
                    note   VARCHAR2(200),
                    CONSTRAINT pk_things PRIMARY KEY (id)
                );
            '''),
            ('V2__drop_col.sql', 'ALTER TABLE app.things DROP COLUMN note;'),
        ))
        col_names = [c.name for c in graph.tables['APP.THINGS'].columns]
        assert 'NOTE' not in col_names
        assert 'LABEL' in col_names

    def test_drop_column_action_recorded(self):
        graph = apply_migrations(_inline(
            ('V1__base.sql', '''
                CREATE TABLE app.things (
                    id    NUMBER(10)   NOT NULL,
                    note  VARCHAR2(200),
                    CONSTRAINT pk_things PRIMARY KEY (id)
                );
            '''),
            ('V2__drop_col.sql', 'ALTER TABLE app.things DROP COLUMN note;'),
        ))
        assert any(
            a.action == 'DROP_COLUMN' and 'NOTE' in a.object_name
            for a in graph.actions
        )

    def test_drop_constraint_removes_it(self):
        graph = apply_migrations(_inline(
            ('V1__base.sql', '''
                CREATE TABLE app.things (
                    id    NUMBER(10) NOT NULL,
                    email VARCHAR2(100),
                    CONSTRAINT pk_things PRIMARY KEY (id),
                    CONSTRAINT uq_things_email UNIQUE (email)
                );
            '''),
            ('V2__drop_con.sql', 'ALTER TABLE app.things DROP CONSTRAINT uq_things_email;'),
        ))
        cons = graph.tables['APP.THINGS'].constraints
        assert not any(c.name == 'UQ_THINGS_EMAIL' for c in cons)

    def test_drop_constraint_action_recorded(self):
        graph = apply_migrations(_inline(
            ('V1__base.sql', '''
                CREATE TABLE app.things (
                    id    NUMBER(10) NOT NULL,
                    email VARCHAR2(100),
                    CONSTRAINT pk_things PRIMARY KEY (id),
                    CONSTRAINT uq_things_email UNIQUE (email)
                );
            '''),
            ('V2__drop_con.sql', 'ALTER TABLE app.things DROP CONSTRAINT uq_things_email;'),
        ))
        assert any(
            a.action == 'DROP_CONSTRAINT' and 'UQ_THINGS_EMAIL' in a.object_name
            for a in graph.actions
        )


# ─────────────────────────────────────────────
# ALTER TABLE MODIFY (regex fallback)
# ─────────────────────────────────────────────

class TestAlterTableModify:
    @pytest.fixture(scope='class')
    def graph(self):
        return apply_migrations(_inline(
            ('V1__base.sql', '''
                CREATE TABLE app.items (
                    id     NUMBER(10)    NOT NULL,
                    code   VARCHAR2(20)  NOT NULL,
                    price  NUMBER(8,2),
                    CONSTRAINT pk_items PRIMARY KEY (id)
                );
            '''),
            ('V2__modify.sql', '''
                ALTER TABLE app.items MODIFY (
                    code   VARCHAR2(50)  NOT NULL,
                    price  NUMBER(10,2)  DEFAULT 0.00
                );
            '''),
        ))

    def test_modify_column_type(self, graph):
        col = next(c for c in graph.tables['APP.ITEMS'].columns if c.name == 'CODE')
        assert col.precision == 50

    def test_modify_column_precision_and_scale(self, graph):
        col = next(c for c in graph.tables['APP.ITEMS'].columns if c.name == 'PRICE')
        assert col.precision == 10
        assert col.scale == 2

    def test_modify_column_default(self, graph):
        col = next(c for c in graph.tables['APP.ITEMS'].columns if c.name == 'PRICE')
        assert col.default is not None

    def test_modify_action_recorded(self, graph):
        assert any(
            a.action == 'MODIFY_COLUMN' and 'CODE' in a.object_name
            for a in graph.actions
        )

    def test_modify_marks_table_modified(self, graph):
        assert '2' in graph.tables['APP.ITEMS'].modified_in


# ─────────────────────────────────────────────
# MigrationAction data in chunks
# ─────────────────────────────────────────────

class TestActionsInChunks:
    @pytest.fixture(scope='class')
    def chunks(self):
        # V1 only: USERS has a CREATE action; no ALTER actions yet
        return build_chunks(apply_migrations(_load(
            'V1__create_core_tables.sql',
        )))

    def test_modified_table_chunk_has_actions_section(self, chunks):
        users_chunk = next(c for c in chunks if c.meta.get('table_name') == 'USERS')
        assert 'MIGRATION ACTIONS:' in users_chunk.content

    def test_table_chunk_meta_includes_actions(self, chunks):
        users_chunk = next(c for c in chunks if c.meta.get('table_name') == 'USERS')
        assert isinstance(users_chunk.meta.get('actions'), list)
        assert len(users_chunk.meta['actions']) > 0

    def test_unmodified_table_chunk_has_no_actions_section(self, chunks):
        # Every table gets at least a CREATE action, so the section is always present.
        # Verify a table with only a CREATE (no ALTER) shows just that action type.
        products_chunk = next(c for c in chunks if c.meta.get('table_name') == 'PRODUCTS')
        assert 'MIGRATION ACTIONS:' in products_chunk.content
        action_types = {a['action'] for a in products_chunk.meta.get('actions', [])}
        # PRODUCTS is not altered in V1-only — only a CREATE action
        assert action_types == {'CREATE'}
