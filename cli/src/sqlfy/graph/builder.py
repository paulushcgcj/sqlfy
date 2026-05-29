"""
sqlfy.graph.builder
====================
Build a NetworkX graph from a domain SchemaGraph.

The resulting graph contains:
- Table nodes (type=table)
- Column nodes (type=column)
- Sequence nodes (type=sequence)
- Migration nodes (type=migration)
- Containment edges (table → column, relation=contains)
- FK edges (table → table, relation=foreign_key)
- Action edges (migration → object, relation=creates|modifies|drops)
"""

from __future__ import annotations

import networkx as nx

from ..domain.models import SchemaGraph, EdgeRelation


def build_networkx_graph(
    schema_graph: SchemaGraph,
    directed: bool = False,
) -> nx.Graph | nx.DiGraph:
    """Convert a SchemaGraph to a NetworkX graph.

    Args:
        schema_graph: The schema graph from reconstruct() or apply_migrations().
        directed: If True, return a DiGraph; otherwise an undirected Graph.

    Returns:
        NetworkX graph with typed nodes and relationship edges.
    """
    G: nx.Graph | nx.DiGraph = nx.DiGraph() if directed else nx.Graph()

    # ── Table and column nodes ────────────────────────────────────────────────
    for table_id, table in schema_graph.tables.items():
        G.add_node(
            table_id,
            label=table.name,
            type="table",
            created_in=table.created_in,
            modified_in=table.modified_in,
            column_count=len(table.columns),
            schema=table.schema,
        )
        for col in table.columns:
            col_id = f"{table_id}.{col.name}"
            G.add_node(
                col_id,
                label=col.name,
                type="column",
                data_type=col.type,
                nullable=col.nullable,
                primary_key=col.primary_key,
                unique=col.unique,
            )
            G.add_edge(table_id, col_id, relation="contains", confidence="EXTRACTED")

    # ── Sequence nodes ────────────────────────────────────────────────────────
    for seq_id, seq in schema_graph.seqs.items():
        G.add_node(
            seq_id,
            label=seq.name,
            type="sequence",
            created_in=seq.created_in,
            start_with=seq.start_with,
            increment_by=seq.increment_by,
            schema=seq.schema,
        )

    # ── FK edges ──────────────────────────────────────────────────────────────
    for edge in schema_graph.edges:
        G.add_edge(
            edge.from_table,
            edge.to_table,
            relation="foreign_key",
            confidence="EXTRACTED",
            from_cols=edge.from_cols,
            to_cols=edge.to_cols,
            on_delete=edge.on_delete,
            constraint_name=edge.constraint_name,
        )

    # ── Migration nodes and action edges ─────────────────────────────────────
    for mig in schema_graph.mig_hist:
        mig_id = f"migration:{mig.version}"
        G.add_node(
            mig_id,
            label=mig.version,
            type="migration",
            description=mig.description,
        )

    for action in schema_graph.actions:
        mig_id = f"migration:{action.version}"
        relation: EdgeRelation = "modifies"
        if action.action == "CREATE":
            relation = "creates"
        elif action.action == "DROP":
            relation = "drops"
        if mig_id in G.nodes and action.object_name in G.nodes:
            G.add_edge(
                mig_id,
                action.object_name,
                relation=relation,
                confidence="EXTRACTED",
                action_type=action.action,
                object_type=action.object_type,
            )

    return G


__all__ = ["build_networkx_graph"]
