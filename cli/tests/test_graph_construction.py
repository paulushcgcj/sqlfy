"""
Tests for NetworkX graph construction (Feature #1)
"""

import networkx as nx
import pytest

from sqlfy.core import (
    SchemaGraph,
    Table,
    Column,
    Edge,
    Sequence,
    MigrationHistory,
    MigrationAction,
    build_networkx_graph,
)
from sqlfy.analysis.validator import (
    validate_graph_structure,
    validate_node_types,
    validate_edge_relations,
)


def test_empty_schema_to_networkx():
    """Test conversion of empty SchemaGraph to NetworkX."""
    schema = SchemaGraph(
        tables={},
        edges=[],
        seqs={},
        mig_hist=[],
    )
    
    G = build_networkx_graph(schema)
    
    assert isinstance(G, nx.Graph)
    assert G.number_of_nodes() == 0
    assert G.number_of_edges() == 0


def test_single_table_to_networkx():
    """Test conversion of single table to NetworkX."""
    schema = SchemaGraph(
        tables={
            "users": Table(
                id="users",
                name="users",
                schema=None,
                full="users",
                columns=[
                    Column(
                        name="id",
                        type="NUMBER",
                        precision=None,
                        scale=None,
                        nullable=False,
                        default=None,
                        primary_key=True,
                        unique=False,
                        references=None,
                    ),
                    Column(
                        name="email",
                        type="VARCHAR2(255)",
                        precision=None,
                        scale=None,
                        nullable=False,
                        default=None,
                        primary_key=False,
                        unique=True,
                        references=None,
                    ),
                ],
                created_in="V1",
            ),
        },
        edges=[],
        seqs={},
        mig_hist=[],
    )
    
    G = build_networkx_graph(schema)
    
    # Check table node
    assert "users" in G.nodes
    assert G.nodes["users"]["type"] == "table"
    assert G.nodes["users"]["label"] == "users"
    assert G.nodes["users"]["created_in"] == "V1"
    assert G.nodes["users"]["column_count"] == 2
    
    # Check column nodes
    assert "users.id" in G.nodes
    assert G.nodes["users.id"]["type"] == "column"
    assert G.nodes["users.id"]["label"] == "id"
    assert G.nodes["users.id"]["primary_key"] is True
    
    assert "users.email" in G.nodes
    assert G.nodes["users.email"]["type"] == "column"
    assert G.nodes["users.email"]["unique"] is True
    
    # Check containment edges
    assert G.has_edge("users", "users.id")
    assert G.edges["users", "users.id"]["relation"] == "contains"
    assert G.edges["users", "users.id"]["confidence"] == "EXTRACTED"
    
    assert G.has_edge("users", "users.email")
    assert G.edges["users", "users.email"]["relation"] == "contains"


def test_foreign_key_edges():
    """Test FK relationships become edges."""
    schema = SchemaGraph(
        tables={
            "users": Table(
                id="users",
                name="users",
                schema=None,
                full="users",
                columns=[],
            ),
            "orders": Table(
                id="orders",
                name="orders",
                schema=None,
                full="orders",
                columns=[],
            ),
        },
        edges=[
            Edge(
                id="fk_orders_user_id",
                from_table="orders",
                from_cols=["user_id"],
                to_table="users",
                to_cols=["id"],
                constraint_name="fk_orders_user_id",
                on_delete="CASCADE",
            ),
        ],
        seqs={},
        mig_hist=[],
    )
    
    G = build_networkx_graph(schema)
    
    # Check FK edge
    assert G.has_edge("orders", "users")
    edge_data = G.edges["orders", "users"]
    assert edge_data["relation"] == "foreign_key"
    assert edge_data["confidence"] == "EXTRACTED"
    assert edge_data["from_cols"] == ["user_id"]
    assert edge_data["to_cols"] == ["id"]
    assert edge_data["on_delete"] == "CASCADE"


def test_sequence_nodes():
    """Test sequences become nodes."""
    schema = SchemaGraph(
        tables={},
        edges=[],
        seqs={
            "user_id_seq": Sequence(
                name="user_id_seq",
                schema=None,
                full="user_id_seq",
                start_with=1,
                increment_by=1,
                created_in="V1",
            ),
        },
        mig_hist=[],
    )
    
    G = build_networkx_graph(schema)
    
    assert "user_id_seq" in G.nodes
    assert G.nodes["user_id_seq"]["type"] == "sequence"
    assert G.nodes["user_id_seq"]["start_with"] == 1
    assert G.nodes["user_id_seq"]["increment_by"] == 1


def test_migration_nodes_and_edges():
    """Test migration history becomes nodes and action edges."""
    schema = SchemaGraph(
        tables={
            "users": Table(
                id="users",
                name="users",
                schema=None,
                full="users",
                columns=[],
                created_in="V1",
            ),
        },
        edges=[],
        seqs={},
        mig_hist=[
            MigrationHistory(version="V1", description="create_users"),
        ],
        actions=[
            MigrationAction(
                action="CREATE",
                object_type="TABLE",
                object_name="users",
                version="V1",
            ),
        ],
    )
    
    G = build_networkx_graph(schema)
    
    # Check migration node
    assert "migration:V1" in G.nodes
    assert G.nodes["migration:V1"]["type"] == "migration"
    assert G.nodes["migration:V1"]["label"] == "V1"
    
    # Check action edge
    assert G.has_edge("migration:V1", "users")
    edge_data = G.edges["migration:V1", "users"]
    assert edge_data["relation"] == "creates"
    assert edge_data["action_type"] == "CREATE"
    assert edge_data["object_type"] == "TABLE"


def test_directed_vs_undirected():
    """Test directed flag creates correct graph type."""
    schema = SchemaGraph(
        tables={
            "users": Table(
                id="users",
                name="users",
                schema=None,
                full="users",
                columns=[],
            ),
        },
        edges=[],
        seqs={},
        mig_hist=[],
    )
    
    # Undirected (default)
    G_undirected = build_networkx_graph(schema, directed=False)
    assert isinstance(G_undirected, nx.Graph)
    assert not isinstance(G_undirected, nx.DiGraph)
    
    # Directed
    G_directed = build_networkx_graph(schema, directed=True)
    assert isinstance(G_directed, nx.DiGraph)


def test_validate_graph_structure_valid():
    """Test validation passes for well-formed graph."""
    schema = SchemaGraph(
        tables={
            "users": Table(
                id="users",
                name="users",
                schema=None,
                full="users",
                columns=[
                    Column(
                        name="id",
                        type="NUMBER",
                        precision=None,
                        scale=None,
                        nullable=False,
                        default=None,
                        primary_key=True,
                        unique=False,
                        references=None,
                    ),
                ],
            ),
        },
        edges=[],
        seqs={},
        mig_hist=[],
    )
    
    G = build_networkx_graph(schema)
    warnings = validate_graph_structure(G)
    
    # Should have no warnings for a well-formed graph with columns
    assert len(warnings) == 0


def test_validate_graph_structure_missing_attributes():
    """Test validation catches missing node attributes."""
    G = nx.Graph()
    G.add_node("bad_node")  # No attributes
    
    warnings = validate_graph_structure(G)
    
    assert len(warnings) >= 2
    assert any("missing 'type'" in w for w in warnings)
    assert any("missing 'label'" in w for w in warnings)


def test_validate_graph_structure_missing_edge_attributes():
    """Test validation catches missing edge attributes."""
    G = nx.Graph()
    G.add_node("a", type="table", label="a")
    G.add_node("b", type="table", label="b")
    G.add_edge("a", "b")  # No relation or confidence
    
    warnings = validate_graph_structure(G)
    
    assert len(warnings) >= 2
    assert any("missing 'relation'" in w for w in warnings)
    assert any("missing 'confidence'" in w for w in warnings)


def test_validate_node_types():
    """Test node type counting."""
    schema = SchemaGraph(
        tables={
            "users": Table(
                id="users",
                name="users",
                schema=None,
                full="users",
                columns=[
                    Column(
                        name="id",
                        type="NUMBER",
                        precision=None,
                        scale=None,
                        nullable=False,
                        default=None,
                        primary_key=True,
                        unique=False,
                        references=None,
                    ),
                ],
            ),
        },
        edges=[],
        seqs={},
        mig_hist=[],
    )
    
    G = build_networkx_graph(schema)
    type_counts = validate_node_types(G)
    
    assert type_counts["table"] == 1
    assert type_counts["column"] == 1


def test_validate_edge_relations():
    """Test edge relation counting."""
    schema = SchemaGraph(
        tables={
            "users": Table(
                id="users",
                name="users",
                schema=None,
                full="users",
                columns=[
                    Column(
                        name="id",
                        type="NUMBER",
                        precision=None,
                        scale=None,
                        nullable=False,
                        default=None,
                        primary_key=True,
                        unique=False,
                        references=None,
                    ),
                ],
            ),
            "orders": Table(
                id="orders",
                name="orders",
                schema=None,
                full="orders",
                columns=[],
            ),
        },
        edges=[
            Edge(
                id="fk_orders_user_id",
                from_table="orders",
                from_cols=["user_id"],
                to_table="users",
                to_cols=["id"],
                constraint_name="fk_orders_user_id",
                on_delete=None,
            ),
        ],
        seqs={},
        mig_hist=[],
    )
    
    G = build_networkx_graph(schema)
    relation_counts = validate_edge_relations(G)
    
    assert relation_counts["contains"] == 1  # users contains id
    assert relation_counts["foreign_key"] == 1  # orders -> users
