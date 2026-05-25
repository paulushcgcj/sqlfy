#!/usr/bin/env python3
"""
sqlfy — cli/main.py

CLI entry point. Reads Flyway migration .sql files from a directory
OR from a JSON input file (used by the Tauri frontend bridge),
applies migrations via core.py, and outputs the result.

Usage:
    # From a directory of .sql files
    python -m sqlfy <migrations-dir> [options]

    # From a JSON input file (used by Tauri bridge)
    python -m sqlfy --json-input FILE [options]

Options:
    --chunks              Output LLM vector chunks instead of schema graph
    --json                Output raw JSON (default: human-readable text)
    --all                 Output both graph AND chunks as combined JSON { graph, chunks }
    --state               Output SchemaState dictionary JSON (richer metadata)
    --at-version VERSION  Reconstruct schema at a specific Flyway version (e.g. 2)
    --dialect DIALECT     SQL dialect to use (default: oracle)
    --json-input FILE     Read migrations from JSON file: [{ filename, sql }]
    --out FILE            Write output to FILE instead of stdout

Examples:
    sqlfy ./migrations
    sqlfy ./migrations --json
    sqlfy ./migrations --chunks
    sqlfy ./migrations --chunks --json
    sqlfy ./migrations --all
    sqlfy ./migrations --state
    sqlfy ./migrations --at-version 2 --json
    sqlfy ./migrations --at-version 2 --state
    sqlfy ./migrations --dialect postgres --json
    sqlfy --json-input /tmp/sqlfy-input.json --all
    sqlfy ./migrations --json --out schema.json
"""

import sys
import json
import argparse
from pathlib import Path

from .core import (
    apply_migrations,
    build_chunks,
    type_str,
    SchemaGraph,
    VectorChunk,
)


# ─────────────────────────────────────────────
# HUMAN-READABLE FORMATTERS
# ─────────────────────────────────────────────

def print_human_graph(graph: SchemaGraph) -> str:
    lines: list[str] = []
    a = lines.append

    a('')
    a('╔══════════════════════════════════════════╗')
    a('║          SCHEMA GRAPH — SUMMARY          ║')
    a('╚══════════════════════════════════════════╝')
    a('')
    a('Migration history:')
    for m in graph.mig_hist:
        a(f'  V{m.version}  {m.description}')

    a(f'\nTables ({len(graph.tables)}):')
    for t in graph.tables.values():
        pk    = next((c for c in t.constraints if c.type == 'primary_key'), None)
        out_e = [e for e in graph.edges if e.from_table == t.full]
        in_e  = [e for e in graph.edges if e.to_table   == t.full]
        modified = f'  Modified: V{", ".join(t.modified_in)}' if t.modified_in else ''
        a(f'\n  ┌─ {t.full} {"─" * max(0, 42 - len(t.full))}')
        if t.comments.get('__table__'):
            a(f'  │  {t.comments["__table__"]}')
        a(f'  │  Created: V{t.created_in}{modified}')
        a(f'  │  Columns:')
        for col in t.columns:
            flags: list[str] = []
            if pk and col.name in pk.columns: flags.append('PK')
            if not col.nullable:              flags.append('NN')
            if col.default:                   flags.append(f'DEFAULT {col.default}')
            comment  = t.comments.get(col.name, '')
            flag_str = f'  {" ".join(flags)}' if flags else ''
            cmt_str  = f'  -- {comment}' if comment else ''
            a(f'  │    {col.name:<24} {type_str(col):<18}{flag_str}{cmt_str}')
        if out_e:
            a(f'  │  References:')
            for e in out_e:
                od = f' ON DELETE {e.on_delete}' if e.on_delete else ''
                a(f'  │    {",".join(e.from_cols)} → {e.to_table}({",".join(e.to_cols)}){od}')
        if in_e:
            a(f'  │  Referenced by:')
            for e in in_e:
                a(f'  │    {e.from_table}.{",".join(e.from_cols)}')
        if t.indexes:
            a(f'  │  Indexes:')
            for idx in t.indexes:
                a(f'  │    {idx.name}  ({", ".join(idx.columns)}){"  UNIQUE" if idx.unique else ""}')
        a(f'  └{"─" * 44}')

    if graph.seqs:
        a(f'\nSequences ({len(graph.seqs)}):')
        for s in graph.seqs.values():
            a(f'  {s.full:<30} START {s.start_with}  INCREMENT {s.increment_by}  [V{s.created_in}]')

    a(f'\nRelationships ({len(graph.edges)}):')
    for e in graph.edges:
        od = f'  [ON DELETE {e.on_delete}]' if e.on_delete else ''
        a(f'  {e.from_table}.{",".join(e.from_cols)}  →  {e.to_table}.{",".join(e.to_cols)}{od}')
    a('')
    return '\n'.join(lines)


def print_human_chunks(chunks: list[VectorChunk]) -> str:
    lines: list[str] = []
    a = lines.append
    a('')
    a('╔══════════════════════════════════════════╗')
    a('║         LLM VECTOR CHUNKS                ║')
    a('╚══════════════════════════════════════════╝')
    a('')
    for chunk in chunks:
        sep = '─' * max(0, 50 - len(chunk.title))
        a(f'━━━ [{chunk.type}] {chunk.title} {sep}')
        a(f'Hint: {chunk.hint}')
        a('')
        a(chunk.content)
        a('')
        a('Metadata:')
        a(json.dumps(chunk.meta, indent=2))
        a('')
    return '\n'.join(lines)


# ─────────────────────────────────────────────
# JSON SERIALISERS
# ─────────────────────────────────────────────

def graph_to_dict(graph: SchemaGraph) -> dict:
    def col_d(col):
        return {'name': col.name, 'type': col.type, 'precision': col.precision,
                'scale': col.scale, 'nullable': col.nullable, 'default': col.default,
                'primary_key': col.primary_key, 'unique': col.unique, 'references': col.references}

    def con_d(c):
        d = {'name': c.name, 'type': c.type, 'columns': c.columns}
        if c.references:  d['references'] = c.references
        if c.check_expr:  d['check_expr'] = c.check_expr
        return d

    return {
        'migration_history': [{'version': m.version, 'description': m.description} for m in graph.mig_hist],
        'tables': {
            k: {'id': t.id, 'schema': t.schema, 'name': t.name, 'full': t.full,
                'columns': [col_d(c) for c in t.columns],
                'constraints': [con_d(c) for c in t.constraints],
                'indexes': [{'name': i.name, 'columns': i.columns, 'unique': i.unique, 'created_in': i.created_in} for i in t.indexes],
                'comments': t.comments, 'created_in': t.created_in, 'modified_in': t.modified_in}
            for k, t in graph.tables.items()
        },
        'sequences': {
            k: {'name': s.name, 'schema': s.schema, 'full': s.full,
                'start_with': s.start_with, 'increment_by': s.increment_by, 'created_in': s.created_in}
            for k, s in graph.seqs.items()
        },
        'edges': [
            {'id': e.id, 'from_table': e.from_table, 'from_cols': e.from_cols,
             'to_table': e.to_table, 'to_cols': e.to_cols,
             'constraint_name': e.constraint_name, 'on_delete': e.on_delete}
            for e in graph.edges
        ],
    }


def chunks_to_list(chunks: list[VectorChunk]) -> list[dict]:
    return [{'id': c.id, 'type': c.type, 'title': c.title,
             'content': c.content, 'metadata': c.meta, 'hint': c.hint}
            for c in chunks]


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog='sqlfy',
        description='Parse Flyway SQL migrations → schema graph / LLM vector chunks.',
    )
    # migrations_dir is now optional — can use --json-input instead
    parser.add_argument(
        'migrations_dir', nargs='?',
        help='Directory containing Flyway .sql files'
    )
    parser.add_argument(
        '--json-input', metavar='FILE',
        help='Read migrations from a JSON file containing [{filename, sql}] (used by Tauri bridge)'
    )
    parser.add_argument('--chunks', action='store_true', help='Output LLM vector chunks')
    parser.add_argument('--all',    action='store_true', help='Output { graph, chunks } combined JSON (implies --json)')
    parser.add_argument('--state',  action='store_true', help='Output SchemaState dictionary JSON (implies --json)')
    parser.add_argument('--json',   action='store_true', help='Output raw JSON')
    parser.add_argument('--at-version', metavar='VERSION',
                        help='Reconstruct schema at a specific Flyway version number (e.g. 2)')
    parser.add_argument('--dialect', default='oracle', metavar='DIALECT',
                        help='SQL dialect (default: oracle; e.g. postgres)')
    parser.add_argument('--out',    metavar='FILE',      help='Write output to FILE')
    args = parser.parse_args()

    # --all and --state both imply --json
    if args.all or args.state:
        args.json = True

    # ── Load files ──
    files: list[dict]

    if args.json_input:
        # Tauri bridge mode: read from a JSON file
        input_path = Path(args.json_input)
        if not input_path.is_file():
            print(f'Error: --json-input file not found: {input_path}', file=sys.stderr)
            sys.exit(1)
        files = json.loads(input_path.read_text(encoding='utf-8'))
        print(f'Loaded {len(files)} migration(s) from JSON input', file=sys.stderr)

    elif args.migrations_dir:
        # Directory mode: read .sql files from disk
        migrations_path = Path(args.migrations_dir)
        if not migrations_path.is_dir():
            print(f'Error: "{migrations_path}" is not a directory.', file=sys.stderr)
            sys.exit(1)
        sql_files = sorted(p for p in migrations_path.iterdir() if p.suffix.lower() == '.sql')
        if not sql_files:
            print(f'No .sql files found in {migrations_path}', file=sys.stderr)
            sys.exit(1)
        files = [{'filename': p.name, 'sql': p.read_text(encoding='utf-8')} for p in sql_files]
        print(f'Loaded {len(files)} migration file(s) from {migrations_path}', file=sys.stderr)

    else:
        parser.error('Provide either migrations_dir or --json-input FILE')

    # ── Run ──
    if args.at_version:
        from .reconstructor import reconstruct_at
        graph = reconstruct_at(files, version=args.at_version, dialect=args.dialect)
    else:
        graph  = apply_migrations(files, dialect=args.dialect)
    chunks = build_chunks(graph) if (args.chunks or args.all) else None

    # ── Format output ──
    if args.state:
        from .schema_state import SchemaStateBuilder
        state_obj = SchemaStateBuilder.from_graph(graph, dialect=args.dialect)
        output = state_obj.to_json()
    elif args.all:
        # Combined mode for Tauri bridge: one call, everything
        output = json.dumps(
            {'graph': graph_to_dict(graph), 'chunks': chunks_to_list(chunks)},  # type: ignore[arg-type]
            indent=2, ensure_ascii=False
        )
    elif args.chunks:
        output = json.dumps(chunks_to_list(chunks), indent=2, ensure_ascii=False) if args.json else print_human_chunks(chunks)  # type: ignore[arg-type]
    else:
        output = json.dumps(graph_to_dict(graph), indent=2, ensure_ascii=False) if args.json else print_human_graph(graph)

    # ── Write ──
    if args.out:
        Path(args.out).write_text(output, encoding='utf-8')
        print(f'Output written to {args.out}', file=sys.stderr)
    else:
        print(output)


if __name__ == '__main__':
    main()