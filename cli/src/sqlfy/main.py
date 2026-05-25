#!/usr/bin/env python3
"""
sqlfy — cli/main.py

CLI entry point with subcommand architecture.

Subcommands
-----------
  dump     Output the Schema State Dictionary (JSON or YAML)
  chunks   Output LLM vector chunks
  diff     Compare two Schema State Dictionaries
  graph    (coming in step 13)

Legacy mode (no subcommand) is preserved for backward compatibility:
  sqlfy <dir> [--chunks] [--json] [--all] [--json-input FILE] [--out FILE]

Usage
-----
  # Subcommand style (preferred)
  sqlfy dump  <migrations-dir> [--format json|yaml] [--out FILE] [--at VERSION]
  sqlfy dump  --json-input FILE [--format json|yaml] [--out FILE]
  sqlfy chunks <migrations-dir> [--format json] [--out FILE] [--at VERSION]

  sqlfy diff state_a.json state_b.json
  sqlfy diff state_a.json state_b.json --format json
  sqlfy diff ./migrations-v1 ./migrations-v2

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

from .core import (
    apply_migrations,
    build_chunks,
    type_str,
    SchemaGraph,
    VectorChunk,
)
from .reconstructor import reconstruct, reconstruct_at
from .schema_state import SchemaStateBuilder
from .differ import SchemaDiffer, diff_files


# ─────────────────────────────────────────────
# FILE LOADING
# ─────────────────────────────────────────────

def load_files(migrations_dir: str | None, json_input: str | None) -> list[dict]:
    """Load migration files from a directory or a JSON input file."""
    if json_input:
        p = Path(json_input)
        if not p.is_file():
            print(f'Error: --json-input file not found: {p}', file=sys.stderr)
            sys.exit(1)
        files = json.loads(p.read_text(encoding='utf-8'))
        print(f'Loaded {len(files)} migration(s) from JSON input', file=sys.stderr)
        return files

    if migrations_dir:
        p = Path(migrations_dir)
        if not p.is_dir():
            print(f'Error: "{p}" is not a directory.', file=sys.stderr)
            sys.exit(1)
        sql_files = sorted(f for f in p.iterdir() if f.suffix.lower() == '.sql')
        if not sql_files:
            print(f'No .sql files found in {p}', file=sys.stderr)
            sys.exit(1)
        files = [{'filename': f.name, 'sql': f.read_text(encoding='utf-8')} for f in sql_files]
        print(f'Loaded {len(files)} migration file(s) from {p}', file=sys.stderr)
        return files

    print('Error: provide either migrations_dir or --json-input FILE', file=sys.stderr)
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
# ARGUMENT PARSER
# ─────────────────────────────────────────────

def _subcommand_parser() -> argparse.ArgumentParser:
    """Parser for subcommand mode (dump, chunks, diff, graph)."""
    parser = argparse.ArgumentParser(prog='sqlfy')
    sub = parser.add_subparsers(dest='subcommand', required=True)

    def shared(p):
        p.add_argument('migrations_dir', nargs='?')
        p.add_argument('--json-input', metavar='FILE')
        p.add_argument('--at', metavar='VERSION')
        p.add_argument('--out', metavar='FILE')

    p_dump = sub.add_parser('dump', help='Output the Schema State Dictionary')
    shared(p_dump)
    p_dump.add_argument('--format', choices=['json', 'yaml', 'summary'], default='json')
    p_dump.set_defaults(func=cmd_dump)

    p_chunks = sub.add_parser('chunks', help='Output LLM vector chunks')
    shared(p_chunks)
    p_chunks.add_argument('--format', choices=['json', 'text'], default='json')
    p_chunks.set_defaults(func=cmd_chunks)

    p_diff = sub.add_parser('diff',
        help='Compare two Schema State Dictionaries or migration directories')
    p_diff.add_argument('state_a',
        help='State JSON file (from sqlfy dump) or migrations directory')
    p_diff.add_argument('state_b',
        help='State JSON file (from sqlfy dump) or migrations directory')
    p_diff.add_argument('--format', choices=['json', 'text'], default='text',
        help='Output format (default: text)')
    p_diff.add_argument('--out', metavar='FILE',
        help='Write output to FILE instead of stdout')
    p_diff.set_defaults(func=cmd_diff)

    p_graph = sub.add_parser('graph', help='Output graph representation (step 13)')
    shared(p_graph)
    p_graph.add_argument('--format', choices=['dot', 'mermaid'], default='dot')
    p_graph.set_defaults(func=lambda a: (print('graph coming in step 13', file=sys.stderr), sys.exit(0)))

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

KNOWN_SUBCOMMANDS = {'dump', 'chunks', 'diff', 'graph'}


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