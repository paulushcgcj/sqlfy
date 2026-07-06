"""
sqlfy.analysis
==============
Schema analysis tools: diff, insights, validation, querying, vector retrieval, impact analysis.
"""
from __future__ import annotations

from .asker import Asker, ChatSession
from .differ import DiffResult, SchemaDiffer
from .impact import (
    ImpactResult,
    analyze_impact,
    format_impact_from_diff_json,
    format_impact_from_diff_text,
    format_impact_json,
    format_impact_text,
    merge_impact_results,
)
from .insights import InsightsEngine
from .query import QueryEngine
from .retriever import EmbeddingRetriever, KeywordRetriever, make_retriever
from .validator import (
    validate_edge_relations,
    validate_graph_structure,
    validate_node_types,
)

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
    'format_impact_from_diff_text', 'format_impact_from_diff_json', 'merge_impact_results',
]
