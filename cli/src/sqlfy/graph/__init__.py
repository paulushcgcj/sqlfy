"""
sqlfy.graph
===========
Graph construction and analysis domain.

Submodules
----------
builder           SchemaGraph → NetworkX graph
clustering        Leiden/Louvain community detection
migration_graph   Migration timeline and dependency graph
"""

from .builder import build_networkx_graph
from .clustering import detect_communities, label_communities, CommunityResult
from .migration_graph import build_migration_graph

__all__ = [
    "build_networkx_graph",
    "detect_communities",
    "label_communities",
    "CommunityResult",
    "build_migration_graph",
]
