#!/usr/bin/env python3
"""
sqlfy — cli/main.py

CLI entry point with subcommand architecture.

Subcommands
-----------
  dump     Output the Schema State Dictionary (JSON or YAML)
  chunks   Output LLM vector chunks
  graph    (coming in step 13)
  diff     (coming in step 12)

Legacy mode (no subcommand) is preserved for backward compatibility:
  sqlfy <dir> [--chunks] [--json] [--all] [--json-input FILE] [--out FILE]

Usage
-----
  # Subcommand style (preferred)
  sqlfy dump  <migrations-dir> [--format json|yaml] [--out FILE] [--at VERSION]
  sqlfy dump  --json-input FILE [--format json|yaml] [--out FILE]
  sqlfy chunks <migrations-dir> [--format json] [--out FILE] [--at VERSION]

  # Legacy style (still works)
  sqlfy <migrations-dir> --json
  sqlfy <migrations-dir> --chunks --json
  sqlfy --json-input FILE --all --json

Examples
--------
  sqlfy dump  ./migrations
  sqlfy dump  ./migrations --format yaml
  sqlfy dump  ./migrations --format json --out state.json
  sqlfy dump  ./migrations --at 3
  sqlfy dump  --json-input /tmp/sqlfy-input.json --format json
  sqlfy chunks ./migrations --format json --out chunks.json
"""

import sys
import json
import argparse
from pathlib import Path

from .core import apply_migrations
from .domain.models import SchemaGraph, VectorChunk
from .domain.schema_state import SchemaStateBuilder, type_str
from .reconstructor import reconstruct, reconstruct_at
from .output.chunker import build_chunks
from .output.grapher import Grapher
from .output.exporter import Exporter
from .analysis.differ import SchemaDiffer, diff_files
from .analysis.insights import InsightsEngine
from .analysis.asker import Asker, ChatSession
from .analysis.query import QueryEngine


# ─────────────────────────────────────────────
# FILE LOADING
# ─────────────────────────────────────────────

def load_files(
    migrations_dir: str | None, json_input: str | None, use_cache: bool = True
) -> list[dict]:
    """Load migration files from a directory or a JSON input file.
    
    Args:
        migrations_dir: Path to directory containing migration files.
        json_input: Path to JSON file with pre-loaded migrations.
        use_cache: Enable file-based caching (default: True).
    
    Returns:
        List of dicts with {filename, sql} for each migration.
    """
    if json_input:
        p = Path(json_input)
        if not p.is_file():
            print(f"Error: --json-input file not found: {p}", file=sys.stderr)
            sys.exit(1)
        files = json.loads(p.read_text(encoding="utf-8"))
        print(f"Loaded {len(files)} migration(s) from JSON input", file=sys.stderr)
        return files

    if migrations_dir:
        p = Path(migrations_dir)
        if not p.is_dir():
            print(f'Error: "{p}" is not a directory.', file=sys.stderr)
            sys.exit(1)
        sql_files = sorted(f for f in p.iterdir() if f.suffix.lower() == ".sql")
        if not sql_files:
            print(f"No .sql files found in {p}", file=sys.stderr)
            sys.exit(1)
        
        if use_cache:
            from .cache import load_cached, save_cached
            
            files = []
            cache_hits = 0
            for f in sql_files:
                cached = load_cached(f)
                if cached:
                    files.append(cached)
                    cache_hits += 1
                else:
                    # Cache miss — read and cache
                    sql_content = f.read_text(encoding="utf-8")
                    result = {"filename": f.name, "sql": sql_content}
                    save_cached(f, result)
                    files.append(result)
            
            if cache_hits > 0:
                print(
                    f"Cache: {cache_hits}/{len(sql_files)} hits",
                    file=sys.stderr
                )
        else:
            files = [
                {"filename": f.name, "sql": f.read_text(encoding="utf-8")}
                for f in sql_files
            ]
        
        print(f"Loaded {len(files)} migration file(s) from {p}", file=sys.stderr)
        return files

    print("Error: provide either migrations_dir or --json-input FILE", file=sys.stderr)
    sys.exit(1)


def write_output(content: str, out: str | None) -> None:
    if out:
        Path(out).write_text(content, encoding='utf-8')
        print(f'Output written to {out}', file=sys.stderr)
    else:
        print(content)


# ─────────────────────────────────────────────
# FORMATTERS  (used by legacy mode)
# ─────────────────────────────────────────────

def format_human_graph(graph: SchemaGraph) -> str:
    lines: list[str] = []
    a = lines.append
    a('\n╔══════════════════════════════════════════╗')
    a('║          SCHEMA GRAPH — SUMMARY          ║')
    a('╚══════════════════════════════════════════╝\n')
    a('Migration history:')
    for m in graph.mig_hist:
        a(f'  V{m.version}  {m.description}')
    a(f'\nTables ({len(graph.tables)}):')
    for t in graph.tables.values():
        pk    = next((c for c in t.constraints if c.type == 'primary_key'), None)
        out_e = [e for e in graph.edges if e.from_table == t.full]
        in_e  = [e for e in graph.edges if e.to_table   == t.full]
        mod   = f'  Modified: V{", ".join(t.modified_in)}' if t.modified_in else ''
        a(f'\n  ┌─ {t.full} {"─" * max(0, 42 - len(t.full))}')
        if t.comments.get('__table__'): a(f'  │  {t.comments["__table__"]}')
        a(f'  │  Created: V{t.created_in}{mod}')
        a(f'  │  Columns:')
        for col in t.columns:
            flags = []
            if pk and col.name in pk.columns: flags.append('PK')
            if not col.nullable:              flags.append('NN')
            if col.default:                   flags.append(f'DEFAULT {col.default}')
            a(f'  │    {col.name:<24} {type_str(col):<18}  {" ".join(flags)}')
        if out_e:
            a('  │  References:')
            for e in out_e:
                a(f'  │    {",".join(e.from_cols)} → {e.to_table}({",".join(e.to_cols)})')
        if in_e:
            a('  │  Referenced by:')
            for e in in_e: a(f'  │    {e.from_table}')
        a(f'  └{"─" * 44}')
    if graph.seqs:
        a(f'\nSequences ({len(graph.seqs)}):')
        for s in graph.seqs.values():
            a(f'  {s.full:<30} START {s.start_with}  INCREMENT {s.increment_by}')
    a(f'\nRelationships ({len(graph.edges)}):')
    for e in graph.edges:
        od = f'  [ON DELETE {e.on_delete}]' if e.on_delete else ''
        a(f'  {e.from_table}.{",".join(e.from_cols)}  →  {e.to_table}.{",".join(e.to_cols)}{od}')
    a('')
    return '\n'.join(lines)


def format_human_chunks(chunks: list[VectorChunk]) -> str:
    lines: list[str] = []
    a = lines.append
    a('\n╔══════════════════════════════════════════╗')
    a('║         LLM VECTOR CHUNKS                ║')
    a('╚══════════════════════════════════════════╝\n')
    for chunk in chunks:
        sep = '─' * max(0, 50 - len(chunk.title))
        a(f'━━━ [{chunk.type}] {chunk.title} {sep}')
        a(f'Hint: {chunk.hint}\n')
        a(chunk.content)
        a('\nMetadata:')
        a(json.dumps(chunk.meta, indent=2))
        a('')
    return '\n'.join(lines)


def graph_to_dict(graph: SchemaGraph) -> dict:
    def col_d(c):
        return {'name': c.name, 'type': c.type, 'precision': c.precision,
                'scale': c.scale, 'nullable': c.nullable, 'default': c.default,
                'primary_key': c.primary_key, 'unique': c.unique, 'references': c.references}
    def con_d(c):
        d = {'name': c.name, 'type': c.type, 'columns': c.columns}
        if c.references:  d['references'] = c.references
        if c.check_expr:  d['check_expr'] = c.check_expr
        return d
    return {
        'migration_history': [{'version': m.version, 'description': m.description} for m in graph.mig_hist],
        'tables': {k: {'id': t.id, 'schema': t.schema, 'name': t.name, 'full': t.full,
                       'columns': [col_d(c) for c in t.columns],
                       'constraints': [con_d(c) for c in t.constraints],
                       'indexes': [{'name': i.name, 'columns': i.columns,
                                    'unique': i.unique, 'created_in': i.created_in} for i in t.indexes],
                       'comments': t.comments, 'created_in': t.created_in, 'modified_in': t.modified_in}
                   for k, t in graph.tables.items()},
        'sequences': {k: {'name': s.name, 'schema': s.schema, 'full': s.full,
                          'start_with': s.start_with, 'increment_by': s.increment_by,
                          'created_in': s.created_in}
                      for k, s in graph.seqs.items()},
        'edges': [{'id': e.id, 'from_table': e.from_table, 'from_cols': e.from_cols,
                   'to_table': e.to_table, 'to_cols': e.to_cols,
                   'constraint_name': e.constraint_name, 'on_delete': e.on_delete}
                  for e in graph.edges],
    }


def chunks_to_list(chunks: list[VectorChunk]) -> list[dict]:
    return [{'id': c.id, 'type': c.type, 'title': c.title,
             'content': c.content, 'metadata': c.meta, 'hint': c.hint}
            for c in chunks]


# ─────────────────────────────────────────────
# SUBCOMMAND: dump
# ─────────────────────────────────────────────

def cmd_dump(args: argparse.Namespace) -> None:
    """
    Output the Schema State Dictionary.

    The Schema State Dictionary is a clean, versioned, serialisable
    snapshot of the final DB state — tables, columns, constraints,
    indexes, sequences, relationships, and migration history.
    """
    files = load_files(args.migrations_dir, args.json_input)

    graph = (
        reconstruct_at(files, version=args.at)
        if args.at
        else reconstruct(files)
    )

    state = SchemaStateBuilder.from_graph(graph)

    fmt = (args.format or 'json').lower()

    if fmt == 'yaml':
        output = state.to_yaml()
    elif fmt == 'json':
        output = state.to_json()
    elif fmt == 'summary':
        output = _format_state_summary(state)
    else:
        print(f'Error: unknown format "{fmt}". Choose json, yaml, or summary.', file=sys.stderr)
        sys.exit(1)

    write_output(output, args.out)


def cmd_manifest(args: argparse.Namespace) -> None:
    """
    Output graph manifest/metadata with high-level summary.
    
    Includes: schema version, fingerprint, node/edge counts, dialect,
    migration count, generation timestamp, and SQLFY version.
    """
    files = load_files(args.migrations_dir, args.json_input)
    
    graph = (
        reconstruct_at(files, version=args.at)
        if getattr(args, 'at', None)
        else reconstruct(files)
    )
    
    state = SchemaStateBuilder.from_graph(graph)
    manifest = state.to_manifest()
    
    output = json.dumps(manifest, indent=2, ensure_ascii=False)
    write_output(output, args.out)


def _format_state_summary(state) -> str:
    """Human-readable summary of the Schema State Dictionary."""
    lines: list[str] = []
    a = lines.append

    a('\n╔══════════════════════════════════════════╗')
    a('║        SCHEMA STATE DICTIONARY           ║')
    a('╚══════════════════════════════════════════╝\n')

    a(f'  Version     : {state.version}')
    a(f'  Fingerprint : {state.fingerprint}')
    a(f'  Generated   : {state.generated_at}')
    a(f'  Dialect     : {state.dialect}')
    a('')
    a('  Stats:')
    for k, v in state.stats.items():
        a(f'    {k:<25} {v}')

    a('\n  Migration history:')
    for m in state.migration_history:
        a(f'    V{m.version:<8} {m.description}')

    a(f'\n  Tables ({len(state.tables)}):')
    for t in state.tables.values():
        mod = f'  modified V{", ".join(t.modified_in)}' if t.modified_in else ''
        a(f'\n    ┌─ {t.full_name}  [created V{t.created_in}{mod}]')
        if t.comment:
            a(f'    │  "{t.comment}"')
        a(f'    │  PK: {t.pk_columns or "none"}')
        for col in t.columns:
            badges = []
            if col.is_pk:     badges.append('PK')
            if col.is_fk:     badges.append('FK')
            if col.is_unique: badges.append('UQ')
            if not col.nullable: badges.append('NN')
            if col.default:   badges.append(f'DEFAULT {col.default}')
            badge_str = f'  [{", ".join(badges)}]' if badges else ''
            cmt_str   = f'  -- {col.comment}' if col.comment else ''
            a(f'    │  {col.name:<22} {col.data_type:<20}{badge_str}{cmt_str}')
        if t.indexes:
            for idx in t.indexes:
                uq = ' UNIQUE' if idx.unique else ''
                a(f'    │  INDEX {idx.name} ({", ".join(idx.columns)}){uq}')
        a(f'    └{"─" * 46}')

    if state.sequences:
        a(f'\n  Sequences ({len(state.sequences)}):')
        for s in state.sequences.values():
            a(f'    {s.full_name:<30} START {s.start_with}  INCREMENT {s.increment_by}')

    a(f'\n  Relationships ({len(state.relationships)}):')
    for r in state.relationships:
        od  = f'  ON DELETE {r.on_delete}' if r.on_delete else ''
        a(f'    {r.from_table}.{r.from_columns} → {r.to_table}.{r.to_columns}  [{r.cardinality}]{od}')

    orphans = state.orphan_tables()
    no_pk   = state.tables_without_pk()
    if orphans or no_pk:
        a('\n  ⚠ Insights:')
        if orphans:
            a(f'    Orphan tables (no FK in/out) : {[t.name for t in orphans]}')
        if no_pk:
            a(f'    Tables without PK            : {[t.name for t in no_pk]}')

    a('')
    return '\n'.join(lines)


# ─────────────────────────────────────────────
# SUBCOMMAND: diff
# ─────────────────────────────────────────────

def cmd_diff(args: argparse.Namespace) -> None:
    """
    Compare two Schema State Dictionaries.

    Accepts either two state JSON files (produced by `sqlfy dump`)
    or two migration directories (reconstructed on the fly).
    """
    import os

    def is_json_file(p: str) -> bool:
        return os.path.isfile(p) and p.endswith('.json')

    if is_json_file(args.state_a) and is_json_file(args.state_b):
        # Fast path: diff pre-built state files
        result = diff_files(args.state_a, args.state_b)
    else:
        # Reconstruct on the fly from migration directories
        def load_dir(path: str):
            from pathlib import Path
            p = Path(path)
            if not p.is_dir():
                print(f'Error: "{path}" is not a directory or .json state file.', file=sys.stderr)
                sys.exit(1)
            sql_files = sorted(f for f in p.iterdir() if f.suffix.lower() == '.sql')
            files = [{'filename': f.name, 'sql': f.read_text(encoding='utf-8')} for f in sql_files]
            print(f'Loaded {len(files)} migration(s) from {path}', file=sys.stderr)
            return SchemaStateBuilder.from_graph(reconstruct(files))

        state_a = load_dir(args.state_a)
        state_b = load_dir(args.state_b)
        result  = SchemaDiffer.diff(state_a, state_b)

    fmt = (args.format or 'text').lower()
    if fmt == 'json':
        output = result.to_json()
    else:
        output = result.to_text()

    write_output(output, args.out)


# ─────────────────────────────────────────────
# SUBCOMMAND: chunks
# ─────────────────────────────────────────────

def cmd_chunks(args: argparse.Namespace) -> None:
    """Output LLM vector chunks from the schema."""
    files  = load_files(args.migrations_dir, args.json_input)
    graph  = reconstruct_at(files, args.at) if args.at else reconstruct(files)
    chunks = build_chunks(graph)

    fmt = (args.format or 'json').lower()
    if fmt == 'json':
        output = json.dumps(chunks_to_list(chunks), indent=2, ensure_ascii=False)
    else:
        output = format_human_chunks(chunks)

    write_output(output, args.out)


# ─────────────────────────────────────────────
# LEGACY MODE  (no subcommand)
# ─────────────────────────────────────────────

def legacy_main(args: argparse.Namespace) -> None:
    """Backward-compatible mode — original flag-based interface."""
    files = load_files(args.migrations_dir, getattr(args, 'json_input', None))

    if getattr(args, 'all', False):
        graph  = reconstruct(files)
        chunks = build_chunks(graph)
        output = json.dumps(
            {'graph': graph_to_dict(graph), 'chunks': chunks_to_list(chunks)},
            indent=2, ensure_ascii=False
        )
    elif getattr(args, 'chunks', False):
        graph  = reconstruct(files)
        chunks = build_chunks(graph)
        output = (json.dumps(chunks_to_list(chunks), indent=2, ensure_ascii=False)
                  if getattr(args, 'json', False) else format_human_chunks(chunks))
    else:
        graph  = reconstruct(files)
        output = (json.dumps(graph_to_dict(graph), indent=2, ensure_ascii=False)
                  if getattr(args, 'json', False) else format_human_graph(graph))

    write_output(output, getattr(args, 'out', None))


# ─────────────────────────────────────────────
# SUBCOMMAND: graph
# ─────────────────────────────────────────────

def cmd_graph(args: argparse.Namespace) -> None:
    """
    Output a graph representation of the schema.

    Formats:
      dot        — Graphviz DOT  (render with `dot -Tsvg schema.dot -o schema.svg`)
      mermaid    — Mermaid ERD   (paste into GitHub Markdown or https://mermaid.live)
      excalidraw — Excalidraw JSON (open in excalidraw.com or VSCode extension)
      drawio     — Draw.io XML (open in draw.io or VSCode extension)
      summary    — Compact ASCII adjacency list (good for LLM prompts)
      json       — NetworkX node-link graph (graph.json)
      html       — Interactive vis.js visualization (graph.html)
      report     — Human-readable graph summary (GRAPH_REPORT.md)
      all        — Generate json, html, and report together
    """
    files = load_files(args.migrations_dir, args.json_input)
    graph = reconstruct_at(files, args.at) if getattr(args, 'at', None) else reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph)

    fmt   = (args.format or 'dot').lower()
    title = getattr(args, 'title', '') or f'Schema V{state.version}'
    
    # Legacy formats (dot, mermaid, excalidraw, drawio, summary) - write to stdout or --out
    if fmt in ('dot', 'mermaid', 'excalidraw', 'drawio', 'summary'):
        if fmt == 'dot':
            output = Grapher.to_dot(state, title=title)
        elif fmt == 'mermaid':
            output = Grapher.to_mermaid(state, title=title)
        elif fmt == 'excalidraw':
            from .output.excalidraw_exporter import to_excalidraw
            import json as json_lib
            output = json_lib.dumps(to_excalidraw(state, title=title), indent=2)
        elif fmt == 'drawio':
            from .output.drawio_exporter import to_drawio
            output = to_drawio(state, title=title)
        else:  # summary
            output = Grapher.to_summary(state)
        write_output(output, args.out)
        return
    
    # New formats (json, html, report, all) - require NetworkX graph and output to files
    from .core import build_networkx_graph
    from .output.graph_export import export_graph_json, export_graph_html, export_graph_report
    
    # Build NetworkX graph
    nx_graph = build_networkx_graph(graph, directed=True)
    
    # Determine output directory
    output_dir = Path(getattr(args, 'output_dir', None) or 'sqlfy-out')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Extract clustering parameters
    resolution = getattr(args, 'resolution', 1.0)
    min_cohesion = getattr(args, 'min_cohesion', 0.1)
    enable_splitting = not getattr(args, 'no_split', False)
    
    if fmt == 'json':
        output_path = output_dir / 'graph.json'
        export_graph_json(
            nx_graph,
            output_path=output_path,
            resolution=resolution,
            min_cohesion=min_cohesion,
            enable_splitting=enable_splitting,
        )
        print(f'✓ Exported NetworkX graph to {output_path}', file=sys.stderr)
    
    elif fmt == 'html':
        output_path = output_dir / 'graph.html'
        export_graph_html(
            nx_graph,
            output_path=output_path,
            resolution=resolution,
            min_cohesion=min_cohesion,
            enable_splitting=enable_splitting,
        )
        print(f'✓ Exported interactive visualization to {output_path}', file=sys.stderr)
    
    elif fmt == 'report':
        output_path = output_dir / 'GRAPH_REPORT.md'
        export_graph_report(
            nx_graph,
            output_path=output_path,
            resolution=resolution,
            min_cohesion=min_cohesion,
            enable_splitting=enable_splitting,
        )
        print(f'✓ Exported graph report to {output_path}', file=sys.stderr)
    
    elif fmt == 'all':
        json_path = output_dir / 'graph.json'
        html_path = output_dir / 'graph.html'
        report_path = output_dir / 'GRAPH_REPORT.md'
        
        export_graph_json(
            nx_graph,
            output_path=json_path,
            resolution=resolution,
            min_cohesion=min_cohesion,
            enable_splitting=enable_splitting,
        )
        export_graph_html(
            nx_graph,
            output_path=html_path,
            resolution=resolution,
            min_cohesion=min_cohesion,
            enable_splitting=enable_splitting,
        )
        export_graph_report(
            nx_graph,
            output_path=report_path,
            resolution=resolution,
            min_cohesion=min_cohesion,
            enable_splitting=enable_splitting,
        )
        
        print(f'✓ Exported all graph outputs to {output_dir}/', file=sys.stderr)
        print(f'  - graph.json', file=sys.stderr)
        print(f'  - graph.html', file=sys.stderr)
        print(f'  - GRAPH_REPORT.md', file=sys.stderr)
    
    else:
        print(f'Error: unknown format "{fmt}". Choose dot, mermaid, summary, json, html, report, or all.', file=sys.stderr)
        sys.exit(1)


# ─────────────────────────────────────────────
# SUBCOMMAND: insights
# ─────────────────────────────────────────────

def cmd_insights(args: argparse.Namespace) -> None:
    """
    Analyse the schema and report Graphify-style insights.

    Detects: orphan tables, missing PKs, unindexed tables, missing FK
    candidates, unresolved FK targets, nullable PKs/FKs, circular
    references, wide tables, orphaned sequences, duplicate indexes,
    and disconnected islands.
    
    Also detects migration-specific anti-patterns: ADD NOT NULL without
    DEFAULT, SELECT * in views, complex triggers, and DELETE without WHERE.
    """
    files = load_files(args.migrations_dir, args.json_input)
    graph = reconstruct_at(files, args.at) if getattr(args, 'at', None) else reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)

    report = InsightsEngine.analyse(state)

    # Optionally filter by severity
    if getattr(args, 'severity', None):
        sev = args.severity.lower()
        report.findings = [f for f in report.findings if f.severity == sev]

    fmt = (args.format or 'text').lower()
    if fmt == 'json':
        output = report.to_json()
    else:
        output = report.to_text()

    write_output(output, args.out)

    # Exit with non-zero if errors found (useful in CI)
    if getattr(args, 'strict', False) and report.errors():
        sys.exit(1)


# ─────────────────────────────────────────────
# SUBCOMMAND: health
# ─────────────────────────────────────────────

def cmd_health(args: argparse.Namespace) -> None:
    """
    Generate migration folder health report.
    
    Provides high-level summary of migration quality:
    - Safe vs unsafe migrations
    - Irreversible operations
    - Health score (0-100)
    - Migration file status
    """
    from .analysis.health import HealthAnalyzer
    
    files = load_files(args.migrations_dir, args.json_input)
    graph = reconstruct_at(files, args.at) if getattr(args, 'at', None) else reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    # Run insights analysis first
    report = InsightsEngine.analyse(state)
    
    # Generate health report
    health_report = HealthAnalyzer.analyze(state, report, args.migrations_dir or '.')
    
    # Format output
    fmt = (args.format or 'text').lower()
    if fmt == 'json':
        output = health_report.to_json()
    else:
        output = health_report.to_text()
    
    write_output(output, args.out)
    
    # Exit with non-zero if health score is critical
    if getattr(args, 'strict', False) and health_report.health_score.grade == 'critical':
        sys.exit(1)


# ─────────────────────────────────────────────
# SUBCOMMAND: simulate
# ─────────────────────────────────────────────

def cmd_simulate(args: argparse.Namespace) -> None:
    """
    Simulate schema evolution with hypothetical migrations.
    
    Test DDL changes before committing:
    - Apply what-if SQL on top of existing state
    - Compare simulated vs actual state
    - Validate migration safety
    """
    from .analysis.simulator import SchemaSimulator
    
    files = load_files(args.migrations_dir, args.json_input)
    
    # Create simulator at base version
    simulator = SchemaSimulator(files, base_version=getattr(args, 'at', None))
    
    # Get SQL to simulate
    if getattr(args, 'sql', None):
        sql = args.sql
        result = simulator.simulate_sql(sql)
    elif getattr(args, 'file', None):
        result = simulator.simulate_file(args.file)
    else:
        print("Error: Must provide --sql or --file", file=sys.stderr)
        sys.exit(1)
    
    # Format output
    fmt = (args.format or 'text').lower()
    if fmt == 'json':
        output = result.to_json()
    else:
        output = result.to_text()
    
    write_output(output, args.out)
    
    # Show diff if requested
    if getattr(args, 'diff', False):
        print("\n" + "="*60)
        print("DIFF:")
        print("="*60)
        print(result.diff.to_text())
    
    # Exit with error if not safe
    if getattr(args, 'strict', False) and not result.is_safe():
        sys.exit(1)


# ─────────────────────────────────────────────
# SUBCOMMAND: integrity
# ─────────────────────────────────────────────

def cmd_integrity(args: argparse.Namespace) -> None:
    """
    Check migration file integrity using SHA256 hashes.
    
    Detect tampering or edits to migration files by comparing current
    file hashes against a manifest of previously recorded hashes.
    """
    from .analysis.integrity import check_integrity, update_manifest
    
    migrations_dir = Path(args.migrations_dir)
    
    if getattr(args, 'update_manifest', False):
        update_manifest(migrations_dir)
        print("✓ Manifest updated")
        return
    
    report = check_integrity(migrations_dir)
    
    if report.status == "clean":
        print(f"✓ All {report.total_migrations} migrations verified")
        return
    
    # Print warnings
    if report.modified:
        print("\n⚠ Modified migrations:")
        for m in report.modified:
            print(f"  {m['filename']} (V{m['version']})")
            print(f"    Old: {m['old_hash'][:12]}...")
            print(f"    New: {m['new_hash'][:12]}...")
    
    if report.missing:
        print("\n⚠ Missing migrations:")
        for m in report.missing:
            print(f"  {m['filename']} (V{m['version']})")
    
    if report.new:
        print(f"\n✓ New migrations ({len(report.new)}):")
        for m in report.new:
            print(f"  {m['filename']} (V{m['version']})")
    
    if getattr(args, 'strict', False) and report.modified:
        print("\nError: Modified migrations detected (--strict mode)")
        sys.exit(1)


# ─────────────────────────────────────────────
# SUBCOMMAND: cache
# ─────────────────────────────────────────────

def cmd_cache(args: argparse.Namespace) -> None:
    """
    Manage the file-based caching system.
    
    Subcommands:
    - clear: Delete all cache entries
    - info: Show cache statistics
    """
    from .cache import clear_cache, _CACHE_ROOT
    
    action = args.cache_action
    
    if action == "clear":
        clear_cache()
        print("✓ Cache cleared")
    elif action == "info":
        cache_dir = _CACHE_ROOT / "migrations"
        stat_index = _CACHE_ROOT / "stat-index.json"
        
        if not cache_dir.exists() and not stat_index.exists():
            print("Cache is empty")
            return
        
        # Count cache entries
        cache_count = len(list(cache_dir.glob("*.json"))) if cache_dir.exists() else 0
        
        # Compute total cache size
        total_size = 0
        if cache_dir.exists():
            for f in cache_dir.glob("*.json"):
                try:
                    total_size += f.stat().st_size
                except OSError:
                    pass
        if stat_index.exists():
            try:
                total_size += stat_index.stat().st_size
            except OSError:
                pass
        
        size_mb = total_size / (1024 * 1024)
        
        print(f"Cache location: {_CACHE_ROOT}")
        print(f"Cached entries: {cache_count}")
        print(f"Total size: {size_mb:.2f} MB")


# ─────────────────────────────────────────────
# SUBCOMMAND: ask
# ─────────────────────────────────────────────

def cmd_ask(args: argparse.Namespace) -> None:
    """
    Ask a natural language question about the schema (single question).

    Uses RAG: retrieves the most relevant schema chunks, then passes them
    as context to Claude for a grounded, accurate answer.

    Requires: ANTHROPIC_API_KEY environment variable.
    """
    files = load_files(args.migrations_dir, args.json_input)
    graph = reconstruct_at(files, args.at) if getattr(args, 'at', None) else reconstruct(files)

    try:
        asker = Asker(
            graph,
            api_key=getattr(args, 'api_key', None),
            use_embeddings=getattr(args, 'embed', False),
            k=getattr(args, 'k', 6),
            use_cache=not getattr(args, 'no_cache', False),
            files=files,
        )
    except ValueError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    question = ' '.join(args.question) if isinstance(args.question, list) else args.question
    fmt = getattr(args, 'format', 'text')

    if fmt == 'json':
        result = asker.ask(question)
        write_output(result.to_json(), args.out)
    else:
        show_src = not getattr(args, 'no_sources', False)
        result = asker.ask_print(question, show_sources=show_src, stream=True)
        if args.out:
            write_output(result.to_json(), args.out)


# ─────────────────────────────────────────────
# SUBCOMMAND: chat
# ─────────────────────────────────────────────

def cmd_chat(args: argparse.Namespace) -> None:
    """
    Start an interactive multi-turn chat session about the schema.

    Follow-up questions maintain context from previous turns.
    Type 'exit', 'quit', or Ctrl-C to end.

    Requires: ANTHROPIC_API_KEY environment variable.
    """
    files = load_files(args.migrations_dir, args.json_input)
    graph = reconstruct_at(files, args.at) if getattr(args, 'at', None) else reconstruct(files)

    try:
        asker = Asker(
            graph,
            api_key=getattr(args, 'api_key', None),
            use_embeddings=getattr(args, 'embed', False),
            k=getattr(args, 'k', 6),
        )
    except ValueError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    session = ChatSession(asker)

    n_tables = len(graph.tables)
    n_edges  = len(graph.edges)
    print(f'\n\033[1msqlfy chat\033[0m — schema V{graph.mig_hist[-1].version if graph.mig_hist else "?"} '
          f'({n_tables} tables, {n_edges} FK edges)')
    print('\033[2mType your question. "reset" clears history. "exit" quits.\033[0m\n')

    while True:
        try:
            question = input('\033[1m?\033[0m  ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\nBye!')
            break

        if not question:
            continue
        if question.lower() in ('exit', 'quit', 'q', 'bye'):
            print('Bye!')
            break
        if question.lower() == 'reset':
            session.reset()
            print('\033[2mConversation history cleared.\033[0m\n')
            continue

        print()
        try:
            session.ask(question, stream=True)
        except Exception as e:
            print(f'\n\033[31mError: {e}\033[0m\n')

        print()


# ─────────────────────────────────────────────
# SUBCOMMAND: export
# ─────────────────────────────────────────────

def cmd_export(args: argparse.Namespace) -> None:
    """
    Export schema as a self-contained HTML documentation file.

    Produces a single .html file with no external dependencies:
      - Searchable, filterable table list with column details
      - Inline Mermaid ERD diagram
      - Schema insights panel (if --insights flag set)
      - Migration history timeline
      - Dark/light mode toggle

    The file can be opened in any browser, emailed, or committed
    to the repo as living documentation.
    """
    files = load_files(args.migrations_dir, args.json_input)
    graph = reconstruct_at(files, args.at) if getattr(args, 'at', None) else reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph)

    report = None
    if getattr(args, 'insights', False):
        report = InsightsEngine.analyse(state)

    title  = getattr(args, 'title', '') or f'Schema Documentation — V{state.version}'
    html   = Exporter.to_html(state, report=report, title=title)

    out = args.out or 'schema_docs.html'
    write_output(html, out)
    print(f'HTML documentation written to {out}', file=sys.stderr)
    print(f'  Tables   : {state.stats["table_count"]}', file=sys.stderr)
    print(f'  Columns  : {state.stats["column_count"]}', file=sys.stderr)
    print(f'  Size     : {len(html):,} chars', file=sys.stderr)


# ─────────────────────────────────────────────
# SUBCOMMAND: query
# ─────────────────────────────────────────────

_QUERY_TYPES = [
    'tables', 'columns', 'fk-path', 'refs',
    'orphans', 'islands', 'cycles',
    'missing-pk', 'missing-fk', 'impact', 'indexes',
]

def cmd_query(args: argparse.Namespace) -> None:
    """
    Run a deterministic graph-traversal query against the schema.
    No LLM, no API calls — instant results.

    Query types
    -----------
      tables      List/filter tables
      columns     List/filter columns
      fk-path     Shortest FK path between two tables
      refs        Tables referencing or referenced by a table
      orphans     Tables with no FK relationships
      islands     Disconnected clusters of tables
      cycles      Circular FK references
      missing-pk  Tables without a primary key
      missing-fk  Columns that look like FKs but have no constraint
      impact      Tables affected by dropping a given table
      indexes     List all indexes
    """
    files  = load_files(args.migrations_dir, args.json_input)
    graph  = reconstruct_at(files, args.at) if getattr(args, 'at', None) else reconstruct(files)
    state  = SchemaStateBuilder.from_graph(graph)
    engine = QueryEngine(state)
    qt     = args.query_type
    fmt    = getattr(args, 'format', 'text')

    # Dispatch to correct engine method
    if qt == 'tables':
        result = engine.tables(
            pattern=getattr(args, 'pattern', None),
            schema=getattr(args, 'schema', None),
            has_pk=_parse_bool(getattr(args, 'has_pk', None)),
            is_orphan=_parse_bool(getattr(args, 'is_orphan', None)),
            min_cols=getattr(args, 'min_cols', None),
            max_cols=getattr(args, 'max_cols', None),
            created_in=getattr(args, 'created_in', None),
        )
    elif qt == 'columns':
        result = engine.columns(
            table=getattr(args, 'table', None),
            pattern=getattr(args, 'pattern', None),
            type_like=getattr(args, 'type_like', None),
            is_pk=_parse_bool(getattr(args, 'is_pk', None)),
            is_fk=_parse_bool(getattr(args, 'is_fk', None)),
            is_unique=_parse_bool(getattr(args, 'is_unique', None)),
            nullable=_parse_bool(getattr(args, 'nullable', None)),
            has_default=_parse_bool(getattr(args, 'has_default', None)),
        )
    elif qt == 'fk-path':
        if not args.from_table or not args.to_table:
            print('Error: fk-path requires --from TABLE and --to TABLE', file=sys.stderr)
            sys.exit(1)
        result = engine.fk_path(args.from_table, args.to_table)
    elif qt == 'refs':
        if not args.table:
            print('Error: refs requires --table TABLE', file=sys.stderr)
            sys.exit(1)
        result = engine.refs(args.table, direction=getattr(args, 'direction', 'both'))
    elif qt == 'orphans':
        result = engine.orphans()
    elif qt == 'islands':
        result = engine.islands()
    elif qt == 'cycles':
        result = engine.cycles()
    elif qt == 'missing-pk':
        result = engine.missing_pk()
    elif qt == 'missing-fk':
        result = engine.missing_fk()
    elif qt == 'impact':
        if not args.table:
            print('Error: impact requires --table TABLE', file=sys.stderr)
            sys.exit(1)
        result = engine.impact(args.table)
    elif qt == 'indexes':
        result = engine.indexes(
            table=getattr(args, 'table', None),
            unique_only=getattr(args, 'unique_only', False),
        )
    else:
        print(f'Unknown query type: {qt}', file=sys.stderr)
        sys.exit(1)

    if fmt == 'json':
        output = result.to_json()
    elif fmt == 'csv':
        output = result.to_csv()
    else:
        output = result.to_text()

    write_output(output, args.out)

    # Summary to stderr so it doesn't pollute piped output
    print(f'  {len(result)} row(s)', file=sys.stderr)


def _parse_bool(val: object) -> 'bool | None':
    """Parse 'true'|'false'|None from argparse string."""
    if val is None:     return None
    if isinstance(val, bool): return val
    return str(val).lower() in ('1', 'true', 'yes')


# ─────────────────────────────────────────────
# SUBCOMMAND: impact
# ─────────────────────────────────────────────

def cmd_impact(args: argparse.Namespace) -> None:
    """
    Analyze impact of changes to a schema object.
    
    Uses graph traversal to find all objects (tables, views, columns, etc.)
    that would be affected by changes to the specified object.
    
    Supports:
      - Direct dependencies (depth 1)
      - Transitive dependencies (depth > 1)
      - Critical path identification
      - Grouping by object type
    """
    files = load_files(args.migrations_dir, args.json_input)
    graph_data = reconstruct_at(files, args.at) if getattr(args, 'at', None) else reconstruct(files)
    
    # Build NetworkX graph
    from .core import build_networkx_graph
    from .analysis.impact import analyze_impact, format_impact_text, format_impact_json
    
    nx_graph = build_networkx_graph(graph_data, directed=True)
    
    # Analyze impact
    object_id = args.object.upper()
    max_depth = getattr(args, 'depth', 5)
    direction = getattr(args, 'direction', 'out')
    
    result = analyze_impact(nx_graph, object_id, max_depth=max_depth, follow_direction=direction)
    
    # Format output
    fmt = getattr(args, 'format', 'text')
    if fmt == 'json':
        output = format_impact_json(result)
    else:
        output = format_impact_text(result, nx_graph)
    
    write_output(output, args.out)
    
    # Summary to stderr
    if result.total_count == 0:
        print(f'No affected objects found for {object_id}', file=sys.stderr)
    else:
        print(f'  {result.total_count} affected object(s)', file=sys.stderr)
        print(f'  {len(result.direct)} direct, {len(result.transitive)} transitive', file=sys.stderr)
        print(f'  Max depth: {result.max_depth}', file=sys.stderr)


# ─────────────────────────────────────────────
# SUBCOMMAND: graph-migrations
# ─────────────────────────────────────────────

def cmd_graph_migrations(args: argparse.Namespace) -> None:
    """
    Visualize migration timeline and dependency graph.
    
    Generates:
      - DOT format (Graphviz) for static diagrams
      - HTML format (vis.js) for interactive exploration
      - Timeline format for chronological view
      - JSON format for programmatic access
    
    Dependency detection:
      - CREATE TABLE → no dependencies
      - ALTER TABLE → depends on migrations that created the table
      - CREATE VIEW → depends on tables used in the view
      - Foreign keys → depends on referenced tables
    """
    files = load_files(args.migrations_dir, args.json_input, use_cache=False)
    
    from .migration_graph import build_migration_graph, format_dot, format_html, format_timeline, format_json
    
    # Build migration graph
    migration_graph = build_migration_graph(files)
    
    # Format output
    fmt = getattr(args, 'format', 'timeline')
    if fmt == 'dot':
        output = format_dot(migration_graph)
    elif fmt == 'html':
        output = format_html(migration_graph)
    elif fmt == 'timeline':
        output = format_timeline(migration_graph)
    elif fmt == 'json':
        output = format_json(migration_graph)
    else:
        print(f'Error: unsupported format: {fmt}', file=sys.stderr)
        sys.exit(1)
    
    write_output(output, args.out)
    
    # Summary to stderr
    print(f'  {len(migration_graph.nodes)} migrations', file=sys.stderr)
    print(f'  {len(migration_graph.edges)} dependencies', file=sys.stderr)


# ─────────────────────────────────────────────
# SUBCOMMAND: rollback-analysis
# ─────────────────────────────────────────────

def cmd_rollback_analysis(args: argparse.Namespace) -> None:
    """
    Analyze migration rollback feasibility.
    
    Determines whether each migration can be safely rolled back:
      - Reversible: Can be undone without data loss
      - Partially reversible: Can be undone with caveats
      - Irreversible: Cannot be undone
    
    Provides:
      - Rollback difficulty score (0-100)
      - Suggested rollback script (reverse migration)
      - Warnings about data loss and risks
    """
    files = load_files(args.migrations_dir, args.json_input, use_cache=False)
    
    from .analysis.rollback import analyze_migrations, format_rollback_text, format_rollback_json
    
    # Analyze all migrations
    results = analyze_migrations(files)
    
    # Format output
    fmt = getattr(args, 'format', 'text')
    if fmt == 'json':
        output = format_rollback_json(results)
    else:
        output = format_rollback_text(results)
    
    write_output(output, args.out)
    
    # Summary to stderr
    reversible = sum(1 for r in results if r.feasibility == 'reversible')
    partial = sum(1 for r in results if r.feasibility == 'partial')
    irreversible = sum(1 for r in results if r.feasibility == 'irreversible')
    
    print(f'  {len(results)} migrations analyzed', file=sys.stderr)
    print(f'  ✓ {reversible} reversible, ⚠️  {partial} partial, ✗ {irreversible} irreversible', file=sys.stderr)


# ─────────────────────────────────────────────
# SUBCOMMAND: lint
# ─────────────────────────────────────────────

def cmd_lint(args: argparse.Namespace) -> None:
    """
    Lint migration SQL files for quality and style using sqlfluff.
    
    Checks:
      - Keyword capitalization
      - Naming conventions
      - Query anti-patterns (SELECT *)
      - Code formatting and style
      - SQL best practices
    
    Supports single file or directory (recursive) linting.
    Configurable via .sqlfluff config file.
    """
    from .analysis.linter import (
        lint_migration,
        lint_directory,
        format_text,
        format_json,
        format_directory_text,
        format_directory_json,
        SQLFLUFF_AVAILABLE,
    )
    
    if not SQLFLUFF_AVAILABLE:
        print("Error: sqlfluff is not installed", file=sys.stderr)
        print("Install with: pip install sqlfluff>=3.0.0", file=sys.stderr)
        sys.exit(1)
    
    path = args.path
    dialect = getattr(args, 'dialect', 'oracle')
    config_path = getattr(args, 'config', None)
    min_score = getattr(args, 'min_score', 0)
    fmt = getattr(args, 'format', 'text')
    
    # Check if path is file or directory
    p = Path(path)
    if not p.exists():
        print(f"Error: path does not exist: {path}", file=sys.stderr)
        sys.exit(1)
    
    if p.is_file():
        # Lint single file
        sql_content = p.read_text(encoding='utf-8')
        result = lint_migration(sql_content, p.name, dialect=dialect, config_path=config_path)
        
        if fmt == 'json':
            output = format_json(result)
        else:
            output = format_text(result)
        
        write_output(output, args.out)
        
        # Exit with error if below threshold
        if result.score < min_score:
            print(f"\nError: Score {result.score} is below minimum {min_score}", file=sys.stderr)
            sys.exit(1)
    
    else:
        # Lint directory
        results = lint_directory(
            str(p),
            min_score=min_score,
            recursive=not getattr(args, 'no_recursive', False),
            dialect=dialect,
            config_path=config_path,
        )
        
        if fmt == 'json':
            output = format_directory_json(results)
        else:
            output = format_directory_text(results)
        
        write_output(output, args.out)
        
        # Exit with error if any file below threshold
        failed = [r for r in results if r.score < min_score]
        if failed:
            print(f"\nError: {len(failed)}/{len(results)} files below minimum score {min_score}", file=sys.stderr)
            sys.exit(1)


# ─────────────────────────────────────────────
# ARGUMENT PARSER
# ─────────────────────────────────────────────

def _subcommand_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='sqlfy')
    sub = parser.add_subparsers(dest='subcommand', required=True)

    def shared(p):
        p.add_argument('migrations_dir', nargs='?')
        p.add_argument('--json-input', metavar='FILE')
        p.add_argument('--at', metavar='VERSION')
        p.add_argument('--out', metavar='FILE')

    def rag_shared(p):
        shared(p)
        p.add_argument('--embed', action='store_true')
        p.add_argument('--api-key', metavar='KEY')
        p.add_argument('-k', type=int, default=6)

    # dump
    p = sub.add_parser('dump', help='Output the Schema State Dictionary')
    shared(p); p.add_argument('--format', choices=['json','yaml','summary'], default='json')
    p.set_defaults(func=cmd_dump)

    # manifest
    p = sub.add_parser('manifest', help='Output graph manifest/metadata summary')
    shared(p)
    p.set_defaults(func=cmd_manifest)

    # chunks
    p = sub.add_parser('chunks', help='Output LLM vector chunks')
    shared(p); p.add_argument('--format', choices=['json','text'], default='json')
    p.set_defaults(func=cmd_chunks)

    # diff
    p = sub.add_parser('diff', help='Compare two Schema State Dictionaries or dirs')
    p.add_argument('state_a'); p.add_argument('state_b')
    p.add_argument('--format', choices=['json','text'], default='text')
    p.add_argument('--out', metavar='FILE')
    p.set_defaults(func=cmd_diff)

    # graph
    p = sub.add_parser('graph', help='Output graph (DOT, Mermaid, Excalidraw, Draw.io, JSON, HTML, or report)')
    shared(p); p.add_argument('--format', choices=['dot','mermaid','excalidraw','drawio','summary','json','html','report','all'], default='dot')
    p.add_argument('--title', metavar='TEXT')
    p.add_argument('--output-dir', metavar='PATH', help='Output directory for json/html/report (default: sqlfy-out)')
    p.add_argument('--resolution', type=float, default=1.0, metavar='FLOAT',
                   help='Community detection resolution: >1 = more communities, <1 = fewer (default: 1.0)')
    p.add_argument('--min-cohesion', type=float, default=0.1, metavar='FLOAT',
                   help='Minimum cohesion score to keep a community (default: 0.1)')
    p.add_argument('--no-split', action='store_true',
                   help='Disable oversized community splitting')
    p.set_defaults(func=cmd_graph)

    # insights
    p = sub.add_parser('insights', help='Analyse schema and report insights')
    shared(p); p.add_argument('--format', choices=['text','json'], default='text')
    p.add_argument('--severity', choices=['error','warning','info'])
    p.add_argument('--strict', action='store_true')
    p.set_defaults(func=cmd_insights)

    # health
    p = sub.add_parser('health', help='Generate migration folder health report')
    shared(p); p.add_argument('--format', choices=['text','json'], default='text')
    p.add_argument('--strict', action='store_true',
                   help='Exit with error code if health score is critical')
    p.set_defaults(func=cmd_health)

    # simulate
    p = sub.add_parser('simulate', help='Simulate schema evolution with hypothetical migrations')
    shared(p)
    p.add_argument('--sql', metavar='SQL', help='Inline SQL to simulate')
    p.add_argument('--file', metavar='PATH', help='Path to SQL file to simulate')
    p.add_argument('--format', choices=['text', 'json'], default='text',
                   help='Output format')
    p.add_argument('--diff', action='store_true',
                   help='Show diff between base and simulated state')
    p.add_argument('--strict', action='store_true',
                   help='Exit with error if simulation is unsafe')
    p.set_defaults(func=cmd_simulate)

    # integrity
    p = sub.add_parser('integrity', help='Check migration file integrity using SHA256 hashes')
    p.add_argument('migrations_dir', help='Path to migrations directory')
    p.add_argument('--strict', action='store_true',
                   help='Exit with error if modified migrations detected')
    p.add_argument('--update-manifest', action='store_true',
                   help='Accept modifications and update manifest')
    p.set_defaults(func=cmd_integrity)

    # cache
    p = sub.add_parser('cache', help='Manage file-based caching system')
    p.add_argument('cache_action', choices=['clear', 'info'],
                   help='Action: clear (delete all) or info (show stats)')
    p.set_defaults(func=cmd_cache)

    # ask
    p = sub.add_parser('ask', help='Ask a natural language question (RAG)')
    rag_shared(p)
    p.add_argument('question', nargs='+')
    p.add_argument('--format', choices=['text','json'], default='text')
    p.add_argument('--no-sources', action='store_true')
    p.add_argument('--no-cache', action='store_true', 
                   help='Skip chunk cache (rebuild chunks from scratch)')
    p.set_defaults(func=cmd_ask)

    # chat
    p = sub.add_parser('chat', help='Interactive multi-turn schema chat')
    rag_shared(p)
    p.set_defaults(func=cmd_chat)

    # export
    p = sub.add_parser('export', help='Export schema as self-contained HTML docs')
    shared(p)
    p.add_argument('--title', metavar='TEXT')
    p.add_argument('--insights', action='store_true')
    p.set_defaults(func=cmd_export)

    # query  ← new
    p = sub.add_parser('query', help='Deterministic graph queries (no LLM)')
    shared(p)
    p.add_argument('query_type', choices=_QUERY_TYPES, metavar='TYPE',
                   help='Query type: ' + ' | '.join(_QUERY_TYPES))
    p.add_argument('--format', choices=['text','json','csv'], default='text')
    # Shared filter flags
    p.add_argument('--pattern',    metavar='REGEX',  help='Name regex filter')
    p.add_argument('--schema',     metavar='NAME',   help='Schema filter')
    p.add_argument('--table',      metavar='TABLE',  help='Table name (full)')
    p.add_argument('--type-like',  metavar='TYPE',   help='Column type substring')
    p.add_argument('--from-table', metavar='TABLE',  help='fk-path: source table')
    p.add_argument('--to-table',   metavar='TABLE',  help='fk-path: target table')
    p.add_argument('--direction',  choices=['in','out','both'], default='both',
                   help='refs: direction (default: both)')
    p.add_argument('--has-pk',     metavar='BOOL',   help='Filter by PK presence (true/false)')
    p.add_argument('--is-orphan',  metavar='BOOL',   help='Filter by orphan status')
    p.add_argument('--is-pk',      metavar='BOOL',   help='Filter columns: is primary key')
    p.add_argument('--is-fk',      metavar='BOOL',   help='Filter columns: is foreign key')
    p.add_argument('--is-unique',  metavar='BOOL',   help='Filter columns: is unique')
    p.add_argument('--nullable',   metavar='BOOL',   help='Filter columns: is nullable')
    p.add_argument('--has-default',metavar='BOOL',   help='Filter columns: has default')
    p.add_argument('--min-cols',   type=int,          help='Min column count')
    p.add_argument('--max-cols',   type=int,          help='Max column count')
    p.add_argument('--created-in', metavar='VER',    help='Filter by created version')
    p.add_argument('--unique-only',action='store_true', help='indexes: unique only')
    p.set_defaults(func=cmd_query)

    # impact
    p = sub.add_parser('impact', help='Analyze impact of schema object changes (NetworkX)')
    shared(p)
    p.add_argument('object', metavar='OBJECT_ID',
                   help='Schema object to analyze (e.g., APP.USERS, APP.USERS.EMAIL)')
    p.add_argument('--depth', type=int, default=5, metavar='N',
                   help='Maximum traversal depth (default: 5)')
    p.add_argument('--direction', choices=['in', 'out'], default='out',
                   help='Traversal direction: out=affected by, in=depends on (default: out)')
    p.add_argument('--format', choices=['text', 'json'], default='text',
                   help='Output format (default: text)')
    p.set_defaults(func=cmd_impact)

    # graph-migrations
    p = sub.add_parser('graph-migrations', help='Visualize migration timeline and dependencies')
    shared(p)
    p.add_argument('--format', choices=['dot', 'html', 'timeline', 'json'], default='timeline',
                   help='Output format: dot (Graphviz), html (interactive), timeline (text), json (default: timeline)')
    p.set_defaults(func=cmd_graph_migrations)

    # rollback-analysis
    p = sub.add_parser('rollback-analysis', help='Analyze migration rollback feasibility')
    shared(p)
    p.add_argument('--format', choices=['text', 'json'], default='text',
                   help='Output format (default: text)')
    p.add_argument('--generate', action='store_true',
                   help='Generate rollback scripts for reversible migrations')
    p.set_defaults(func=cmd_rollback_analysis)

    # lint
    p = sub.add_parser('lint', help='Lint migration SQL files for quality and style (sqlfluff)')
    p.add_argument('path', metavar='PATH',
                   help='Path to SQL file or directory')
    p.add_argument('--format', choices=['text', 'json'], default='text',
                   help='Output format (default: text)')
    p.add_argument('--min-score', type=int, default=0, metavar='N',
                   help='Fail if score < N (default: 0)')
    p.add_argument('--config', metavar='FILE',
                   help='Path to .sqlfluff config file')
    p.add_argument('--dialect', default='oracle',
                   help='SQL dialect: oracle, postgres, mysql, sqlite (default: oracle)')
    p.add_argument('--no-recursive', action='store_true',
                   help='Do not recursively scan subdirectories')
    p.add_argument('--out', metavar='FILE',
                   help='Write output to file instead of stdout')
    p.set_defaults(func=cmd_lint)

    return parser


def _legacy_parser() -> argparse.ArgumentParser:
    """Parser for legacy flag-based mode."""
    parser = argparse.ArgumentParser(prog='sqlfy', add_help=False)
    parser.add_argument('migrations_dir', nargs='?')
    parser.add_argument('--json-input', metavar='FILE')
    parser.add_argument('--chunks', action='store_true')
    parser.add_argument('--all',    action='store_true')
    parser.add_argument('--json',   action='store_true')
    parser.add_argument('--out',    metavar='FILE')
    parser.add_argument('--at',     metavar='VERSION')
    return parser


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

KNOWN_SUBCOMMANDS = {'dump', 'manifest', 'chunks', 'diff', 'graph', 'graph-migrations', 'rollback-analysis', 'insights', 'health', 'simulate', 'integrity', 'cache', 'ask', 'chat', 'export', 'query', 'impact', 'lint'}


def main() -> None:
    argv = sys.argv[1:]
    first_positional = next((a for a in argv if not a.startswith('-')), None)

    if first_positional in KNOWN_SUBCOMMANDS:
        # Subcommand mode
        args = _subcommand_parser().parse_args(argv)
        args.func(args)
    else:
        # Legacy mode
        args = _legacy_parser().parse_args(argv)
        if args.all:
            args.json = True
        legacy_main(args)


if __name__ == '__main__':
    main()