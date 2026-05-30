#!/usr/bin/env python3
"""sqlfy CLI entry point — subcommand and legacy modes."""

import sys
import argparse

from .commands import (
    cmd_dump, cmd_manifest, cmd_chunks, cmd_export, legacy_main,
    cmd_graph, cmd_graph_migrations, cmd_build_graph,
    cmd_diff, cmd_diff_versions, cmd_rollback_analysis, cmd_simulate, cmd_integrity, cmd_drift,
    cmd_insights, cmd_health, cmd_domains, cmd_stability,
    cmd_ask, cmd_chat, cmd_query, _QUERY_TYPES,
    cmd_impact,
    cmd_lint, cmd_validate, cmd_deps, cmd_lineage, cmd_cache, cmd_classify, cmd_safety,
    cmd_cost, cmd_provenance, cmd_naming,
)

KNOWN_SUBCOMMANDS = {
    "dump", "manifest", "chunks", "diff", "diff-versions", "graph", "graph-migrations", "build-graph",
    "rollback-analysis", "insights", "health", "simulate", "integrity",
    "cache", "ask", "chat", "export", "query", "impact", "lint",
    "provenance", "cost",
    "naming",
    "domains", "stability", "validate", "deps", "lineage", "drift",
    "classify", "safety",
}


def _subcommand_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sqlfy")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    def shared(p):
        p.add_argument("migrations_dir", nargs="?")
        p.add_argument("--json-input", metavar="FILE")
        p.add_argument("--at", metavar="VERSION")
        p.add_argument("--out", metavar="FILE")
        p.add_argument("--dialect", default="oracle",
                       help="SQL dialect: oracle, postgres, mysql, sqlite (default: oracle)")

    def rag_shared(p):
        shared(p)
        p.add_argument("--embed", action="store_true")
        p.add_argument("--api-key", metavar="KEY")
        p.add_argument("-k", type=int, default=6)

    # dump
    p = sub.add_parser("dump", help="Output the Schema State Dictionary")
    shared(p)
    p.add_argument("--format", choices=["json", "yaml", "summary"], default="json")
    p.set_defaults(func=cmd_dump)

    # manifest
    p = sub.add_parser("manifest", help="Output graph manifest/metadata summary")
    shared(p)
    p.add_argument("--format", choices=["json", "text"], default="json")
    p.set_defaults(func=cmd_manifest)

    # chunks
    p = sub.add_parser("chunks", help="Output LLM vector chunks")
    shared(p)
    p.add_argument("--format", choices=["json", "text"], default="json")
    p.set_defaults(func=cmd_chunks)

    # diff
    p = sub.add_parser("diff", help="Compare two Schema State Dictionaries or dirs")
    p.add_argument("state_a")
    p.add_argument("state_b")
    p.add_argument("--format", choices=["json", "text"], default="text")
    p.add_argument("--out", metavar="FILE")
    p.set_defaults(func=cmd_diff)

    # diff-versions
    p = sub.add_parser("diff-versions", help="Compare two version snapshots from one migration set")
    shared(p)
    p.add_argument("--from", dest="from_version", metavar="VERSION", help="Base version (default: latest)")
    p.add_argument("--to", dest="to_version", metavar="VERSION", help="Target version (default: latest)")
    p.add_argument("--format", choices=["json", "text"], default="json")
    p.set_defaults(func=cmd_diff_versions)

    # graph
    p = sub.add_parser("graph", help="Output schema graph (DOT, Mermaid, Excalidraw, Draw.io, JSON, HTML, report)")
    shared(p)
    p.add_argument("--format", choices=["dot", "mermaid", "excalidraw", "drawio", "summary", "json", "html", "report", "all"], default="dot")
    p.add_argument("--title", metavar="TEXT")
    p.add_argument("--output-dir", metavar="PATH", help="Output directory for json/html/report (default: sqlfy-out)")
    p.add_argument("--resolution", type=float, default=1.0, metavar="FLOAT",
                   help="Community detection resolution (default: 1.0)")
    p.add_argument("--min-cohesion", type=float, default=0.1, metavar="FLOAT",
                   help="Minimum cohesion score to keep a community (default: 0.1)")
    p.add_argument("--no-split", action="store_true", help="Disable oversized community splitting")
    p.set_defaults(func=cmd_graph)

    # build-graph (unified knowledge graph builder)
    p = sub.add_parser("build-graph", help="Build complete schema knowledge graph (unified graphify-style output)")
    shared(p)
    p.add_argument("--output-dir", metavar="PATH", help="Output directory (default: graphify-out)")
    p.add_argument("--resolution", type=float, default=1.0, metavar="FLOAT",
                   help="Community detection resolution (default: 1.0)")
    p.add_argument("--min-cohesion", type=float, default=0.5, metavar="FLOAT",
                   help="Minimum cohesion score to keep a community (default: 0.5)")
    p.add_argument("--no-split", action="store_true", help="Disable oversized community splitting")
    p.add_argument("--min-refs", type=int, default=20, metavar="N",
                   help="Minimum references to classify as god node (default: 20)")
    p.add_argument("--no-queries", action="store_true", help="Skip pre-computed query results")
    p.add_argument("--no-viz", action="store_true", help="Skip visualization formats (mermaid/dot/excalidraw/drawio)")
    p.set_defaults(func=cmd_build_graph)

    # insights
    p = sub.add_parser("insights", help="Analyse schema and report insights")
    shared(p)
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--severity", choices=["error", "warning", "info"])
    p.add_argument("--strict", action="store_true")
    p.set_defaults(func=cmd_insights)

    # health
    p = sub.add_parser("health", help="Generate migration folder health report")
    shared(p)
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--strict", action="store_true",
                   help="Exit with error code if health score is critical")
    p.set_defaults(func=cmd_health)

    # simulate
    p = sub.add_parser("simulate", help="Simulate schema evolution with hypothetical SQL")
    shared(p)
    p.add_argument("--sql", metavar="SQL", help="Inline SQL to simulate")
    p.add_argument("--file", metavar="PATH", help="Path to SQL file to simulate")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--diff", action="store_true", help="Show diff between base and simulated state")
    p.add_argument("--strict", action="store_true", help="Exit with error if simulation is unsafe")
    p.set_defaults(func=cmd_simulate)

    # integrity
    p = sub.add_parser("integrity", help="Check migration file integrity using SHA256 hashes")
    p.add_argument("migrations_dir", help="Path to migrations directory")
    p.add_argument("--strict", action="store_true",
                   help="Exit with error if modified migrations detected")
    p.add_argument("--update-manifest", action="store_true",
                   help="Accept modifications and update manifest")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.set_defaults(func=cmd_integrity)

    # provenance
    p = sub.add_parser("provenance", help="Collect git provenance for migrations (author, commit, branches, PR)")
    p.add_argument("migrations_dir", help="Path to migrations directory")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--record", action="store_true", help="Write provenance manifest to disk (defaults to <migrations_dir>/provenance.json)")
    p.add_argument("--out", metavar="FILE", help="Write output to file (JSON when --format=json)")
    p.add_argument("--verify", metavar="MANIFEST", help="Verify current provenance against existing manifest JSON file")
    p.add_argument("--no-recursive", action="store_true", help="Do not recurse into subdirectories")
    p.add_argument("--include-untracked", action="store_true", help="Include untracked files when collecting provenance (default: only tracked files)")
    p.set_defaults(func=cmd_provenance)

    # cost
    p = sub.add_parser("cost", help="Estimate migration execution cost (heuristic)")
    p.add_argument("migrations_dir", help="Path to migrations directory")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--dialect", default="oracle")
    p.add_argument("--no-recursive", action="store_true", help="Do not recurse into subdirectories")
    p.add_argument("--verbose", action="store_true", help="Show per-statement operation weights")
    p.add_argument("--out", metavar="FILE", help="Write output to file (JSON when --format=json)")
    p.add_argument("--table-stats", metavar="FILE", help="Path to JSON file with table stats (table -> {rows:int, avg_row_size:int})")
    p.add_argument("--throughput", type=float, metavar="MBPS", help="Assumed IO throughput in MB/s (default: 100)")
    p.add_argument("--weight-profile", choices=["default", "plsql", "data-migration"], default="default",
                   help="Scoring profile: 'default' (conservative), 'plsql' (reduce PL/SQL noise), 'data-migration' (amplify bulk DML)")
    p.set_defaults(func=cmd_cost)

    # cache
    p = sub.add_parser("cache", help="Manage file-based caching system")
    p.add_argument("cache_action", choices=["clear", "info"],
                   help="Action: clear (delete all) or info (show stats)")
    p.set_defaults(func=cmd_cache)

    # ask
    p = sub.add_parser("ask", help="Ask a natural language question (RAG)")
    rag_shared(p)
    p.add_argument("question", nargs="+")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--no-sources", action="store_true")
    p.add_argument("--no-cache", action="store_true",
                   help="Skip chunk cache (rebuild chunks from scratch)")
    p.set_defaults(func=cmd_ask)

    # chat
    p = sub.add_parser("chat", help="Interactive multi-turn schema chat")
    rag_shared(p)
    p.set_defaults(func=cmd_chat)

    # export
    p = sub.add_parser("export", help="Export schema as self-contained HTML docs")
    shared(p)
    p.add_argument("--title", metavar="TEXT")
    p.add_argument("--insights", action="store_true")
    p.set_defaults(func=cmd_export)

    # query
    p = sub.add_parser("query", help="Deterministic graph queries (no LLM)")
    shared(p)
    p.add_argument("query_type", choices=_QUERY_TYPES, metavar="TYPE",
                   help="Query type: " + " | ".join(_QUERY_TYPES))
    p.add_argument("--format", choices=["text", "json", "csv"], default="text")
    p.add_argument("--pattern",    metavar="REGEX",  help="Name regex filter")
    p.add_argument("--schema",     metavar="NAME",   help="Schema filter")
    p.add_argument("--table",      metavar="TABLE",  help="Table name (full)")
    p.add_argument("--type-like",  metavar="TYPE",   help="Column type substring")
    p.add_argument("--from-table", metavar="TABLE",  help="fk-path: source table")
    p.add_argument("--to-table",   metavar="TABLE",  help="fk-path: target table")
    p.add_argument("--direction",  choices=["in", "out", "both"], default="both")
    p.add_argument("--has-pk",     metavar="BOOL",   help="Filter by PK presence (true/false)")
    p.add_argument("--is-orphan",  metavar="BOOL")
    p.add_argument("--is-pk",      metavar="BOOL")
    p.add_argument("--is-fk",      metavar="BOOL")
    p.add_argument("--is-unique",  metavar="BOOL")
    p.add_argument("--nullable",   metavar="BOOL")
    p.add_argument("--has-default", metavar="BOOL")
    p.add_argument("--min-cols",   type=int)
    p.add_argument("--max-cols",   type=int)
    p.add_argument("--created-in", metavar="VER")
    p.add_argument("--unique-only", action="store_true")
    p.set_defaults(func=cmd_query)

    # impact
    p = sub.add_parser("impact", help="Analyze impact of schema object changes")
    shared(p)
    p.add_argument("object", metavar="OBJECT_ID",
                   help="Schema object to analyze (e.g., APP.USERS, APP.USERS.EMAIL)")
    p.add_argument("--depth", type=int, default=5, metavar="N")
    p.add_argument("--direction", choices=["in", "out"], default="out")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.set_defaults(func=cmd_impact)

    # graph-migrations
    p = sub.add_parser("graph-migrations", help="Visualize migration timeline and dependencies")
    shared(p)
    p.add_argument("--format", choices=["dot", "html", "timeline", "json"], default="timeline")
    p.set_defaults(func=cmd_graph_migrations)

    # rollback-analysis
    p = sub.add_parser("rollback-analysis", help="Analyze migration rollback feasibility")
    shared(p)
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--generate", action="store_true",
                   help="Generate rollback scripts for reversible migrations")
    p.set_defaults(func=cmd_rollback_analysis)

    # lint
    p = sub.add_parser("lint", help="Lint migration SQL files for quality and style (sqlfluff)")
    p.add_argument("path", metavar="PATH", help="Path to SQL file or directory")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--min-score", type=int, default=0, metavar="N",
                   help="Fail if score < N (default: 0)")
    p.add_argument("--config", metavar="FILE", help="Path to .sqlfluff config file")
    p.add_argument("--fix", action="store_true", help="Apply automatic fixes (in-place). BACKUPs created as .bak files")
    p.add_argument("--dialect", default="oracle")
    p.add_argument("--no-recursive", action="store_true")
    p.add_argument("--out", metavar="FILE")
    p.set_defaults(func=cmd_lint)

    # drift
    p = sub.add_parser("drift", help="Detect schema drift and generate repair SQL")
    p.add_argument("base_migrations", metavar="BASE_MIGRATIONS")
    p.add_argument("target_migrations", metavar="TARGET_MIGRATIONS")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--generate-migration", action="store_true")
    p.add_argument("--next-version", metavar="N")
    p.add_argument("--description", default="catch_up_drift")
    p.add_argument("--dialect", default="oracle")
    p.add_argument("--out", metavar="FILE")
    p.set_defaults(func=cmd_drift)

    # domains
    p = sub.add_parser("domains", help="Detect semantic business domains in the schema")
    shared(p)
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--resolution", type=float, default=1.0, metavar="FLOAT")
    p.add_argument("--min-cohesion", type=float, default=0.1, metavar="FLOAT")
    p.add_argument("--no-split", action="store_true")
    p.set_defaults(func=cmd_domains)

    # stability
    p = sub.add_parser("stability", help="Calculate schema stability metrics and churn rates")
    shared(p)
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--show-all", action="store_true")
    p.add_argument("--high-churn-threshold", type=float, default=20.0, metavar="FLOAT")
    p.add_argument("--stable-threshold", type=float, default=10.0, metavar="FLOAT")
    p.set_defaults(func=cmd_stability)

    # validate
    p = sub.add_parser("validate", help="Validate migration ordering and detect issues")
    p.add_argument("migrations_dir", help="Path to directory containing migration files")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--fix-numbering", action="store_true")
    p.add_argument("--out", metavar="FILE")
    p.set_defaults(func=cmd_validate)

    # naming
    p = sub.add_parser("naming", help="Enforce migration naming conventions")
    p.add_argument("migrations_dir", help="Path to directory containing migration files")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--pattern", metavar="REGEX", default=r"^[a-z0-9_]+$",
                   help="Regex for description (default: lower-case, digits, underscores)")
    p.add_argument("--max-len", type=int, default=120, help="Maximum allowed filename length")
    p.add_argument("--strict", action="store_true", help="Exit 1 if any warnings are found")
    p.add_argument("--out", metavar="FILE")
    p.set_defaults(func=cmd_naming)

    # deps
    p = sub.add_parser("deps", help="Analyze migration dependencies and detect issues")
    p.add_argument("migrations_dir", help="Path to directory containing migration files")
    p.add_argument("--format", choices=["text", "json", "dot"], default="text")
    p.add_argument("--validate", action="store_true")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--critical-path", action="store_true")
    p.add_argument("--summary-only", action="store_true")
    p.add_argument("--out", metavar="FILE")
    p.set_defaults(func=cmd_deps)

    # lineage
    p = sub.add_parser("lineage", help="Column-level lineage and data flow analysis")
    shared(p)
    p.add_argument("column", nargs="?", metavar="TABLE.COLUMN")
    p.add_argument("--downstream", action="store_true", default=True)
    p.add_argument("--upstream", action="store_true")
    p.add_argument("--unused-columns", action="store_true")
    p.add_argument("--god-columns", action="store_true")
    p.add_argument("--min-refs", type=int, default=20, metavar="N")
    p.add_argument("--format", choices=["text", "json", "mermaid"], default="text")
    p.add_argument("--max-depth", type=int, default=3, metavar="N")
    p.set_defaults(func=cmd_lineage)

    # classify
    p = sub.add_parser(
        "classify",
        help="Classify migrations by semantic category "
             "(table_creation, data_migration, cleanup, …)",
    )
    shared(p)
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument(
        "--category",
        metavar="CAT",
        choices=[
            "table_creation", "column_addition", "column_removal",
            "constraint_modification", "index_management", "data_migration",
            "cleanup", "refactor", "view_trigger_procedure", "mixed",
        ],
        help="Filter by primary category",
    )
    p.add_argument(
        "--risk",
        choices=["low", "medium", "high"],
        help="Filter by risk level",
    )
    p.add_argument(
        "--group-by-category",
        dest="group_by",
        action="store_true",
        help="Group output by category instead of file order",
    )
    p.set_defaults(func=cmd_classify)

    # safety
    p = sub.add_parser(
        "safety",
        help="Score migrations by safety level "
             "(SAFE / MEDIUM_RISK / HIGH_RISK / DANGEROUS)",
    )
    shared(p)
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument(
        "--threshold",
        choices=["safe", "medium", "high", "dangerous"],
        metavar="LEVEL",
        help="Exit 1 if any migration is at or above this level",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show per-statement breakdown for each migration",
    )
    p.set_defaults(func=cmd_safety)

    return parser


def _legacy_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sqlfy", add_help=False)
    parser.add_argument("migrations_dir", nargs="?")
    parser.add_argument("--json-input", metavar="FILE")
    parser.add_argument("--chunks", action="store_true")
    parser.add_argument("--all",    action="store_true")
    parser.add_argument("--json",   action="store_true")
    parser.add_argument("--out",    metavar="FILE")
    parser.add_argument("--at",     metavar="VERSION")
    parser.add_argument("--dialect", default="oracle")
    return parser


def main() -> None:
    argv = sys.argv[1:]
    first_positional = next((a for a in argv if not a.startswith("-")), None)

    if first_positional in KNOWN_SUBCOMMANDS or "--help" in argv or "-h" in argv:
        args = _subcommand_parser().parse_args(argv)
        _meta = frozenset({'func', 'subcommand'})
        kw = {k: v for k, v in vars(args).items() if k not in _meta}
        result = args.func(**kw)
        if isinstance(result, int):
            sys.exit(result)
    else:
        args = _legacy_parser().parse_args(argv)
        if args.all:
            args.json = True
        legacy_main(
            migrations_dir=args.migrations_dir,
            json_input=getattr(args, 'json_input', None),
            dialect=getattr(args, 'dialect', 'oracle'),
            all=args.all,
            chunks=args.chunks,
            as_json=args.json,
            out=args.out,
        )


if __name__ == "__main__":
    main()
