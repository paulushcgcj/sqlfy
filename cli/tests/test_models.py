"""
test_models.py
==============
Tests for data models in sqlfy.models module.
"""

from sqlfy.domain.models import (
    Column, Constraint, Index, MigrationAction,
    Table, Sequence, Edge, MigrationHistory,
    SchemaGraph, VectorChunk, GraphNode, GraphEdge,
    EdgeRelation, Confidence,
)


def test_column_creation():
    """Test Column dataclass instantiation."""
    col = Column(
        name='user_id',
        type='NUMBER',
        precision=10,
        scale=None,
        nullable=False,
        default=None,
        primary_key=True,
        unique=False,
        references=None,
    )
    assert col.name == 'user_id'
    assert col.type == 'NUMBER'
    assert col.primary_key is True
    assert col.nullable is False


def test_column_with_fk_reference():
    """Test Column with foreign key reference."""
    col = Column(
        name='organization_id',
        type='NUMBER',
        precision=10,
        scale=None,
        nullable=False,
        default=None,
        primary_key=False,
        unique=False,
        references={'table': 'organizations', 'column': 'id'},
    )
    assert col.references is not None
    assert col.references['table'] == 'organizations'
    assert col.references['column'] == 'id'


def test_constraint_primary_key():
    """Test primary key constraint."""
    pk = Constraint(
        name='users_pk',
        type='primary_key',
        columns=['user_id'],
    )
    assert pk.type == 'primary_key'
    assert pk.columns == ['user_id']
    assert pk.references is None


def test_constraint_foreign_key():
    """Test foreign key constraint."""
    fk = Constraint(
        name='orders_user_fk',
        type='foreign_key',
        columns=['user_id'],
        references={
            'table': 'users',
            'columns': ['id'],
            'on_delete': 'CASCADE',
        },
    )
    assert fk.type == 'foreign_key'
    assert fk.references is not None
    assert fk.references['on_delete'] == 'CASCADE'


def test_index_creation():
    """Test Index dataclass instantiation."""
    idx = Index(
        name='users_email_idx',
        columns=['email'],
        unique=True,
        created_in='V1',
    )
    assert idx.name == 'users_email_idx'
    assert idx.unique is True
    assert 'email' in idx.columns


def test_migration_action_create():
    """Test MigrationAction for CREATE TABLE."""
    action = MigrationAction(
        action='CREATE',
        object_type='TABLE',
        object_name='users',
        version='V1',
    )
    assert action.action == 'CREATE'
    assert action.object_type == 'TABLE'
    assert action.version == 'V1'


def test_migration_action_add_column():
    """Test MigrationAction for ADD_COLUMN."""
    action = MigrationAction(
        action='ADD_COLUMN',
        object_type='COLUMN',
        object_name='users.middle_name',
        version='V3',
    )
    assert action.action == 'ADD_COLUMN'
    assert action.object_name == 'users.middle_name'


def test_table_minimal():
    """Test Table with minimal fields."""
    table = Table(
        id='users',
        schema=None,
        name='users',
        full='users',
    )
    assert table.name == 'users'
    assert len(table.columns) == 0
    assert len(table.constraints) == 0
    assert table.created_in == ''


def test_table_with_columns():
    """Test Table with columns."""
    col1 = Column('id', 'NUMBER', 10, None, False, None, True, False, None)
    col2 = Column('email', 'VARCHAR2', 255, None, False, None, False, True, None)
    table = Table(
        id='users',
        schema='app',
        name='users',
        full='app.users',
        columns=[col1, col2],
        created_in='V1',
    )
    assert len(table.columns) == 2
    assert table.schema == 'app'
    assert table.columns[0].name == 'id'


def test_sequence_creation():
    """Test Sequence dataclass instantiation."""
    seq = Sequence(
        name='order_seq',
        schema='app',
        full='app.order_seq',
        start_with=1000,
        increment_by=1,
        created_in='V2',
    )
    assert seq.name == 'order_seq'
    assert seq.start_with == 1000
    assert seq.increment_by == 1


def test_edge_creation():
    """Test Edge (FK relationship) dataclass."""
    edge = Edge(
        id='orders_users_fk',
        from_table='orders',
        from_cols=['user_id'],
        to_table='users',
        to_cols=['id'],
        constraint_name='orders_user_fk',
        on_delete='CASCADE',
    )
    assert edge.from_table == 'orders'
    assert edge.to_table == 'users'
    assert edge.on_delete == 'CASCADE'


def test_migration_history():
    """Test MigrationHistory dataclass."""
    mig = MigrationHistory(
        version='V1',
        description='create_core_tables',
    )
    assert mig.version == 'V1'
    assert mig.description == 'create_core_tables'


def test_schema_graph_empty():
    """Test SchemaGraph with no data."""
    graph = SchemaGraph(
        tables={},
        seqs={},
        edges=[],
        mig_hist=[],
    )
    assert len(graph.tables) == 0
    assert len(graph.edges) == 0
    assert len(graph.actions) == 0


def test_schema_graph_with_data():
    """Test SchemaGraph with tables and edges."""
    table = Table('users', None, 'users', 'users', created_in='V1')
    edge = Edge('e1', 'orders', ['user_id'], 'users', ['id'], 'fk_orders_users', None)
    graph = SchemaGraph(
        tables={'users': table},
        seqs={},
        edges=[edge],
        mig_hist=[MigrationHistory('V1', 'init')],
        actions=[MigrationAction('CREATE', 'TABLE', 'users', 'V1')],
    )
    assert 'users' in graph.tables
    assert len(graph.edges) == 1
    assert len(graph.actions) == 1


def test_vector_chunk_creation():
    """Test VectorChunk dataclass."""
    chunk = VectorChunk(
        id='table:users',
        type='table',
        title='Table: users',
        content='TABLE: users\nColumns: id, email',
        meta={'table_name': 'users', 'column_count': 2},
        hint='Use for queries about users table.',
    )
    assert chunk.id == 'table:users'
    assert chunk.type == 'table'
    assert chunk.meta['column_count'] == 2


def test_graph_node_table():
    """Test GraphNode for a table."""
    node = GraphNode(
        id='table:users',
        label='users',
        type='table',
        source_file='V1__create_core_tables.sql',
        created_in='V1',
    )
    assert node.type == 'table'
    assert node.label == 'users'
    assert node.source_file == 'V1__create_core_tables.sql'


def test_graph_node_column():
    """Test GraphNode for a column."""
    node = GraphNode(
        id='column:users.email',
        label='email',
        type='column',
        created_in='V1',
        modified_in=['V3'],
    )
    assert node.type == 'column'
    assert 'V3' in node.modified_in


def test_graph_edge_contains():
    """Test GraphEdge for contains relationship."""
    edge = GraphEdge(
        source='table:users',
        target='column:users.id',
        relation='contains',
        confidence='EXTRACTED',
        metadata={'nullable': False},
    )
    assert edge.relation == 'contains'
    assert edge.confidence == 'EXTRACTED'


def test_graph_edge_foreign_key():
    """Test GraphEdge for foreign_key relationship."""
    edge = GraphEdge(
        source='table:orders',
        target='table:users',
        relation='foreign_key',
        confidence='EXTRACTED',
        metadata={'columns': ['user_id'], 'on_delete': 'CASCADE'},
    )
    assert edge.relation == 'foreign_key'
    assert edge.metadata['on_delete'] == 'CASCADE'


def test_edge_relation_type():
    """Test EdgeRelation type values."""
    relations: list[EdgeRelation] = [
        'contains', 'foreign_key', 'creates', 'modifies',
        'uses', 'calls', 'imports', 'similar_to',
    ]
    for rel in relations:
        edge = GraphEdge('src', 'tgt', rel)
        assert edge.relation == rel


def test_confidence_type():
    """Test Confidence type values."""
    confidences: list[Confidence] = ['EXTRACTED', 'INFERRED', 'HEURISTIC']
    for conf in confidences:
        edge = GraphEdge('src', 'tgt', 'uses', conf)
        assert edge.confidence == conf
