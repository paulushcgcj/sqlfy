"""
test_chunker.py
===============
Tests for LLM chunk builder in sqlfy.chunker module.
"""

from sqlfy.output.chunker import build_chunks, _type_str
from sqlfy.domain.models import Column, Table, Sequence, Edge, MigrationHistory, SchemaGraph, Constraint


def test_type_str_simple():
    """Test _type_str with simple type."""
    col = Column('id', 'NUMBER', None, None, False, None, True, False, None)
    assert _type_str(col) == 'NUMBER'


def test_type_str_with_precision():
    """Test _type_str with precision."""
    col = Column('amount', 'NUMBER', 10, None, False, None, False, False, None)
    assert _type_str(col) == 'NUMBER(10)'


def test_type_str_with_precision_and_scale():
    """Test _type_str with precision and scale."""
    col = Column('price', 'NUMBER', 10, 2, False, None, False, False, None)
    assert _type_str(col) == 'NUMBER(10,2)'


def test_build_chunks_empty_schema():
    """Test build_chunks with empty schema."""
    graph = SchemaGraph(tables={}, seqs={}, edges=[], mig_hist=[])
    chunks = build_chunks(graph)
    
    # Should still have schema summary and relationship map
    assert len(chunks) >= 2
    assert chunks[0].id == 'schema:summary'
    assert chunks[0].type == 'schema_summary'
    assert chunks[-1].id == 'schema:relationships'


def test_build_chunks_single_table():
    """Test build_chunks with single table."""
    col1 = Column('id', 'NUMBER', 10, None, False, None, True, False, None)
    col2 = Column('name', 'VARCHAR2', 100, None, False, None, False, False, None)
    table = Table('users', None, 'users', 'users', columns=[col1, col2], created_in='V1')
    
    graph = SchemaGraph(
        tables={'users': table},
        seqs={},
        edges=[],
        mig_hist=[MigrationHistory('V1', 'init')],
    )
    chunks = build_chunks(graph)
    
    # Summary + users table + relationship map
    assert len(chunks) == 3
    assert chunks[0].id == 'schema:summary'
    assert chunks[1].id == 'table:users'
    assert chunks[2].id == 'schema:relationships'


def test_build_chunks_table_content():
    """Test table chunk content format."""
    col1 = Column('id', 'NUMBER', 10, None, False, None, True, False, None)
    col2 = Column('email', 'VARCHAR2', 255, None, False, None, False, True, None)
    pk = Constraint('users_pk', 'primary_key', ['id'])
    uq = Constraint('users_email_uq', 'unique', ['email'])
    table = Table('users', 'app', 'users', 'app.users', columns=[col1, col2], constraints=[pk, uq], created_in='V1')
    
    graph = SchemaGraph(
        tables={'app.users': table},
        seqs={},
        edges=[],
        mig_hist=[MigrationHistory('V1', 'init')],
    )
    chunks = build_chunks(graph)
    
    users_chunk = next(c for c in chunks if c.id == 'table:app.users')
    assert 'TABLE: app.users' in users_chunk.content
    assert 'id: NUMBER(10)' in users_chunk.content
    assert 'email: VARCHAR2(255)' in users_chunk.content
    assert 'PK' in users_chunk.content
    assert 'UNIQUE' in users_chunk.content


def test_build_chunks_with_foreign_key():
    """Test chunk content with foreign key relationships."""
    users_table = Table('users', None, 'users', 'users', created_in='V1')
    orders_table = Table('orders', None, 'orders', 'orders', created_in='V2')
    edge = Edge('fk1', 'orders', ['user_id'], 'users', ['id'], 'orders_user_fk', 'CASCADE')
    
    graph = SchemaGraph(
        tables={'users': users_table, 'orders': orders_table},
        seqs={},
        edges=[edge],
        mig_hist=[MigrationHistory('V1', 'init'), MigrationHistory('V2', 'add_orders')],
    )
    chunks = build_chunks(graph)
    
    orders_chunk = next(c for c in chunks if c.id == 'table:orders')
    assert 'REFERENCES (outgoing FK)' in orders_chunk.content
    assert 'users' in orders_chunk.content
    assert 'ON DELETE CASCADE' in orders_chunk.content


def test_build_chunks_schema_summary_meta():
    """Test schema summary chunk metadata."""
    table = Table('users', None, 'users', 'users', created_in='V1')
    graph = SchemaGraph(
        tables={'users': table},
        seqs={},
        edges=[],
        mig_hist=[MigrationHistory('V1', 'init')],
    )
    chunks = build_chunks(graph)
    
    summary = chunks[0]
    assert summary.meta['table_count'] == 1
    assert summary.meta['seq_count'] == 0
    assert summary.meta['edge_count'] == 0


def test_build_chunks_with_sequence():
    """Test chunks with sequence objects."""
    seq = Sequence('order_seq', 'app', 'app.order_seq', 1000, 1, 'V1')
    graph = SchemaGraph(
        tables={},
        seqs={'app.order_seq': seq},
        edges=[],
        mig_hist=[MigrationHistory('V1', 'init')],
    )
    chunks = build_chunks(graph)
    
    summary = chunks[0]
    assert 'order_seq' in summary.content
    assert summary.meta['seq_count'] == 1


def test_build_chunks_relationship_map():
    """Test relationship map chunk."""
    users_table = Table('users', None, 'users', 'users', created_in='V1')
    orders_table = Table('orders', None, 'orders', 'orders', created_in='V1')
    edge = Edge('fk1', 'orders', ['user_id'], 'users', ['id'], 'orders_user_fk', None)
    
    graph = SchemaGraph(
        tables={'users': users_table, 'orders': orders_table},
        seqs={},
        edges=[edge],
        mig_hist=[MigrationHistory('V1', 'init')],
    )
    chunks = build_chunks(graph)
    
    rel_chunk = chunks[-1]
    assert rel_chunk.id == 'schema:relationships'
    assert rel_chunk.type == 'relationship_map'
    assert 'orders' in rel_chunk.content
    assert 'users' in rel_chunk.content


def test_build_chunks_table_hint():
    """Test table chunk hint field."""
    table = Table('users', None, 'users', 'users', created_in='V1')
    graph = SchemaGraph(
        tables={'users': table},
        seqs={},
        edges=[],
        mig_hist=[MigrationHistory('V1', 'init')],
    )
    chunks = build_chunks(graph)
    
    users_chunk = next(c for c in chunks if c.id == 'table:users')
    assert 'Use for' in users_chunk.hint
    assert 'users table' in users_chunk.hint


def test_build_chunks_unique_ids():
    """Test all chunk IDs are unique."""
    table1 = Table('users', None, 'users', 'users', created_in='V1')
    table2 = Table('orders', None, 'orders', 'orders', created_in='V1')
    graph = SchemaGraph(
        tables={'users': table1, 'orders': table2},
        seqs={},
        edges=[],
        mig_hist=[MigrationHistory('V1', 'init')],
    )
    chunks = build_chunks(graph)
    
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids)), "Chunk IDs must be unique"
