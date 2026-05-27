"""sqlfy CLI command handlers."""

from .schema import cmd_dump, cmd_manifest, cmd_chunks, cmd_export, legacy_main
from .graph import cmd_graph, cmd_graph_migrations
from .build_graph import cmd_build_graph
from .evolution import cmd_diff, cmd_rollback_analysis, cmd_simulate, cmd_integrity, cmd_drift
from .analysis import cmd_insights, cmd_health, cmd_domains, cmd_stability
from .ai import cmd_ask, cmd_chat, cmd_query, _QUERY_TYPES
from .impact import cmd_impact
from .devtools import cmd_lint, cmd_validate, cmd_deps, cmd_lineage, cmd_cache, cmd_classify, cmd_safety
from .provenance import cmd_provenance

__all__ = [
    "cmd_dump", "cmd_manifest", "cmd_chunks", "cmd_export", "legacy_main",
    "cmd_graph", "cmd_graph_migrations", "cmd_build_graph",
    "cmd_diff", "cmd_rollback_analysis", "cmd_simulate", "cmd_integrity", "cmd_drift",
    "cmd_insights", "cmd_health", "cmd_domains", "cmd_stability",
    "cmd_ask", "cmd_chat", "cmd_query", "_QUERY_TYPES",
    "cmd_impact",
    "cmd_lint", "cmd_validate", "cmd_deps", "cmd_lineage", "cmd_cache", "cmd_classify", "cmd_safety",
    "cmd_provenance",
]
