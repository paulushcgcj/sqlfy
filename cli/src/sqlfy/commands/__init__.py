"""sqlfy CLI command handlers."""
from __future__ import annotations

from .ai import _QUERY_TYPES, cmd_ask, cmd_chat, cmd_query
from .analysis import cmd_domains, cmd_health, cmd_insights, cmd_stability
from .build_graph import cmd_build_graph
from .devtools import (
    cmd_cache,
    cmd_classify,
    cmd_cost,
    cmd_deps,
    cmd_lineage,
    cmd_lint,
    cmd_naming,
    cmd_pii_scan,
    cmd_safety,
    cmd_validate,
)
from .evolution import (
    cmd_diff,
    cmd_diff_versions,
    cmd_drift,
    cmd_integrity,
    cmd_rollback_analysis,
    cmd_simulate,
)
from .graph import cmd_graph, cmd_graph_migrations
from .impact import cmd_impact
from .provenance import cmd_provenance
from .schema import cmd_chunks, cmd_dump, cmd_export, cmd_manifest, legacy_main

__all__ = [
    "cmd_dump", "cmd_manifest", "cmd_chunks", "cmd_export", "legacy_main",
    "cmd_graph", "cmd_graph_migrations", "cmd_build_graph",
    "cmd_diff", "cmd_rollback_analysis", "cmd_simulate", "cmd_integrity", "cmd_drift",
    "cmd_insights", "cmd_health", "cmd_domains", "cmd_stability",
    "cmd_ask", "cmd_chat", "cmd_query", "_QUERY_TYPES",
    "cmd_impact",
    "cmd_lint", "cmd_validate", "cmd_deps", "cmd_lineage", "cmd_cache", "cmd_classify", "cmd_safety",
    "cmd_cost",
    "cmd_naming",
    "cmd_provenance",
    "cmd_pii_scan",
]
