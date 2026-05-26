"""
sqlfy.analysis
==============
Schema analysis tools: diff, insights, validation, querying, vector retrieval, impact analysis.
"""

from .differ import SchemaDiffer, DiffResult
from .insights import InsightsEngine
from .validator import validate_graph_structure, validate_node_types, validate_edge_relations
from .asker import Asker, ChatSession
from .query import QueryEngine
from .retriever import KeywordRetriever, EmbeddingRetriever, make_retriever
from .impact import analyze_impact, ImpactResult, format_impact_text, format_impact_json

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
    # Impact
    'analyze_impact', 'ImpactResult', 'format_impact_text', 'format_impact_json',
]
