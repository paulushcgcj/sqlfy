"""
test_layout.py
==============
Tests for ERD layout engine in sqlfy.layout module.
"""

from sqlfy.output.layout import compute_layout
from sqlfy.domain.models import Table, Edge


def test_compute_layout_empty():
    """Test compute_layout with no tables."""
    pos = compute_layout({}, [])
    assert pos == {}


def test_compute_layout_single_table():
    """Test compute_layout with single table."""
    table = Table('users', None, 'users', 'users')
    pos = compute_layout({'users': table}, [])
    
    assert 'users' in pos
    assert 'x' in pos['users']
    assert 'y' in pos['users']
    assert pos['users']['x'] > 0
    assert pos['users']['y'] > 0


def test_compute_layout_two_tables_no_edges():
    """Test layout with two unconnected tables."""
    table1 = Table('users', None, 'users', 'users')
    table2 = Table('orders', None, 'orders', 'orders')
    tables = {'users': table1, 'orders': table2}
    
    pos = compute_layout(tables, [])
    
    assert 'users' in pos
    assert 'orders' in pos
    # Both should be at same level (y coordinate)
    assert pos['users']['y'] == pos['orders']['y']


def test_compute_layout_with_edge():
    """Test layout with FK relationship."""
    users = Table('users', None, 'users', 'users')
    orders = Table('orders', None, 'orders', 'orders')
    tables = {'users': users, 'orders': orders}
    
    edge = Edge('fk1', 'orders', ['user_id'], 'users', ['id'], 'orders_user_fk', None)
    pos = compute_layout(tables, [edge])
    
    assert 'users' in pos
    assert 'orders' in pos
    # orders references users, so orders should be at a higher level (different y)
    # (FK source is positioned after FK target in hierarchy)
    assert pos['orders']['y'] != pos['users']['y']


def test_compute_layout_chain():
    """Test layout with chain: A -> B -> C."""
    a = Table('a', None, 'a', 'a')
    b = Table('b', None, 'b', 'b')
    c = Table('c', None, 'c', 'c')
    tables = {'a': a, 'b': b, 'c': c}
    
    # C references B, B references A
    edge1 = Edge('e1', 'c', ['b_id'], 'b', ['id'], 'c_b_fk', None)
    edge2 = Edge('e2', 'b', ['a_id'], 'a', ['id'], 'b_a_fk', None)
    
    pos = compute_layout(tables, [edge1, edge2])
    
    # Should form a hierarchy: A at bottom, B middle, C top
    # (or inverse depending on how levels map to y)
    assert pos['a']['y'] != pos['b']['y']
    assert pos['b']['y'] != pos['c']['y']
    assert pos['a']['y'] != pos['c']['y']


def test_compute_layout_custom_dimensions():
    """Test layout with custom width and height."""
    table = Table('users', None, 'users', 'users')
    pos = compute_layout({'users': table}, [], width=1000, height=500)
    
    assert pos['users']['x'] <= 1000
    assert pos['users']['y'] <= 500
    assert pos['users']['x'] > 0
    assert pos['users']['y'] > 0


def test_compute_layout_returns_dict_with_xy():
    """Test return structure has x and y keys."""
    table = Table('users', None, 'users', 'users')
    pos = compute_layout({'users': table}, [])
    
    assert isinstance(pos, dict)
    assert isinstance(pos['users'], dict)
    assert 'x' in pos['users']
    assert 'y' in pos['users']
    assert isinstance(pos['users']['x'], (int, float))
    assert isinstance(pos['users']['y'], (int, float))


def test_compute_layout_star_schema():
    """Test layout with star schema (one fact table, multiple dimension tables)."""
    fact = Table('sales', None, 'sales', 'sales')
    dim1 = Table('products', None, 'products', 'products')
    dim2 = Table('stores', None, 'stores', 'stores')
    dim3 = Table('time', None, 'time', 'time')
    
    tables = {'sales': fact, 'products': dim1, 'stores': dim2, 'time': dim3}
    
    # Fact table references all dimension tables
    edges = [
        Edge('e1', 'sales', ['product_id'], 'products', ['id'], None, None),
        Edge('e2', 'sales', ['store_id'], 'stores', ['id'], None, None),
        Edge('e3', 'sales', ['time_id'], 'time', ['id'], None, None),
    ]
    
    pos = compute_layout(tables, edges)
    
    # All dimension tables should be at a lower level than fact table
    # Fact table (sales) should be at highest level
    assert 'sales' in pos
    assert 'products' in pos
    assert 'stores' in pos
    assert 'time' in pos


def test_compute_layout_multiple_tables_same_level():
    """Test that multiple tables at same level get different x coordinates."""
    table1 = Table('users', None, 'users', 'users')
    table2 = Table('products', None, 'products', 'products')
    table3 = Table('categories', None, 'categories', 'categories')
    tables = {'users': table1, 'products': table2, 'categories': table3}
    
    pos = compute_layout(tables, [])
    
    # All at same level, so same y but different x
    assert pos['users']['y'] == pos['products']['y'] == pos['categories']['y']
    assert pos['users']['x'] != pos['products']['x']
    assert pos['products']['x'] != pos['categories']['x']


def test_compute_layout_respects_width_bounds():
    """Test that x coordinates stay within width."""
    tables = {f'table{i}': Table(f'table{i}', None, f'table{i}', f'table{i}') for i in range(10)}
    pos = compute_layout(tables, [], width=800, height=600)
    
    for tbl in tables:
        assert 0 < pos[tbl]['x'] <= 800


def test_compute_layout_respects_height_bounds():
    """Test that y coordinates stay within height."""
    # Create chain to force multiple levels
    tables = {f't{i}': Table(f't{i}', None, f't{i}', f't{i}') for i in range(5)}
    edges = [Edge(f'e{i}', f't{i+1}', ['ref'], f't{i}', ['id'], None, None) for i in range(4)]
    
    pos = compute_layout(tables, edges, width=600, height=400)
    
    for tbl in tables:
        assert 0 < pos[tbl]['y'] <= 400
