"""
sqlfy.analysis
==============
Schema analysis tools: diff, insights, validation, querying, vector retrieval.
"""

from .differ import SchemaDiffer, DiffResult
from .insights import InsightsEngine
from .validator import validate_graph_structure, validate_node_types, validate_edge_relations
from .asker import Asker, ChatSession
from .query import QueryEngine
from .retriever import KeywordRetriever, EmbeddingRetriever, make_retriever

__all__ = [
    # Diff
    'SchemaDiffer', 'DiffResult',
    # Insights
    'InsightsEngine',
    # Validation
    'validate_graph_structure', 'validate_node_types', 'validate_edge_relations',
    # LLM
    'Asker', 'ChatSession',
    # Query
    'QueryEngine',
    # Retrieval
    'KeywordRetriever', 'EmbeddingRetriever', 'make_retriever',
]
