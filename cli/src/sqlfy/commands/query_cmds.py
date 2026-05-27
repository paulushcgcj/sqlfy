"""Query commands: query, impact, lineage, deps, validate."""

from __future__ import annotations

import json
import sys
import argparse
from pathlib import Path

from ..reconstructor import reconstruct, reconstruct_at
from ..domain.schema_state import SchemaStateBuilder
from .. import analysis
from .io import load_files, write_output

QUERY_TYPES = [
    'tables', 'columns', 'fk-path', 'refs',
    'orphans', 'islands', 'cycles',
    'missing-pk', 'missing-fk', 'impact', 'indexes',
]


def _parse_bool(val: object) -> 'bool | None':
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    return str(val).lower() in ('1', 'true', 'yes')


def cmd_query(args: argparse.Namespace) -> None:
    from ..analysis.query import QueryEngine
    files = load_files(args.migrations_dir, args.json_input)
    dialect = getattr(args, 'dialect', 'oracle')
    graph = (
        reconstruct_at(files, args.at, dialect=dialect)
        if args.at
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph)
    engine = QueryEngine(state)
    qt = args.query_type
    fmt = getattr(args, 'format', 'text')

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
    print(f'  {len(result)} row(s)', file=sys.stderr)


def cmd_impact(args: argparse.Namespace) -> None:
    from ..core import build_networkx_graph
    from ..analysis.impact import analyze_impact, format_impact_text, format_impact_json
    files = load_files(args.migrations_dir, args.json_input)
    dialect = getattr(args, 'dialect', 'oracle')
    graph_data = (
        reconstruct_at(files, args.at, dialect=dialect)
        if args.at
        else reconstruct(files, dialect=dialect)
    )
    nx_graph = build_networkx_graph(graph_data, directed=True)
    object_id = args.object.upper()
    max_depth = getattr(args, 'depth', 5)
    direction = getattr(args, 'direction', 'out')
    result = analyze_impact(nx_graph, object_id, max_depth=max_depth, follow_direction=direction)
    fmt = getattr(args, 'format', 'text')
    output = format_impact_json(result) if fmt == 'json' else format_impact_text(result, nx_graph)
    write_output(output, args.out)
    if result.total_count == 0:
        print(f'No affected objects found for {object_id}', file=sys.stderr)
    else:
        print(f'  {result.total_count} affected object(s)', file=sys.stderr)
        print(f'  {len(result.direct)} direct, {len(result.transitive)} transitive', file=sys.stderr)


def cmd_validate(args: argparse.Namespace) -> int:
    from .. import analysis
    from ..analysis import ordering
    migrations_dir = Path(args.migrations_dir)
    if not migrations_dir.is_dir():
        print(f'Error: migrations directory not found: {migrations_dir}', file=sys.stderr)
        return 1
    report = ordering.validate_migrations(migrations_dir)
    fmt = getattr(args, 'format', 'text')
    output = ordering.format_json(report) if fmt == 'json' else ordering.format_text(report, show_suggestions=True)
    write_output(output, getattr(args, 'out', None))
    if getattr(args, 'fix_numbering', False):
        suggestions = ordering.suggest_renumbering(migrations_dir)
        if suggestions:
            print('\n📋 Renumbering suggestions:')
            for s in suggestions:
                print(f'  {s["old"]} → {s["new"]}')
        else:
            print('\n✓ No renumbering needed')
    if report.has_errors:
        return 1
    if getattr(args, 'strict', False) and report.has_warnings:
        return 1
    return 0


def cmd_deps(args: argparse.Namespace) -> int:
    from ..analysis.deps import analyze_dependencies, format_text, format_json, format_dot, validate_dependencies
    migrations_dir = Path(args.migrations_dir)
    if not migrations_dir.is_dir():
        print(f'Error: migrations directory not found: {migrations_dir}', file=sys.stderr)
        return 1
    try:
        analysis_result = analyze_dependencies(migrations_dir)
        fmt = getattr(args, 'format', 'text')
        show_details = not getattr(args, 'summary_only', False)
        if fmt == 'json':
            output = format_json(analysis_result)
        elif fmt == 'dot':
            output = format_dot(analysis_result)
        else:
            output = format_text(analysis_result, show_details=show_details)
        write_output(output, getattr(args, 'out', None))
        if getattr(args, 'validate', False):
            is_valid, message = validate_dependencies(analysis_result, strict=getattr(args, 'strict', False))
            print(f'\n{message}', file=sys.stderr)
            if not is_valid:
                return 1
        if getattr(args, 'critical_path', False) and analysis_result.critical_path:
            print('\n🔴 Critical Path:', file=sys.stderr)
            print(f'  {" → ".join(analysis_result.critical_path)}', file=sys.stderr)
        error_count = sum(1 for issue in analysis_result.issues if issue.severity == 'error')
        warning_count = sum(1 for issue in analysis_result.issues if issue.severity == 'warning')
        if error_count > 0:
            return 1
        if getattr(args, 'strict', False) and warning_count > 0:
            return 1
        return 0
    except ImportError as e:
        print(f'Error: {e}', file=sys.stderr)
        print('Install networkx: pip install networkx', file=sys.stderr)
        return 1
    except Exception as e:
        import traceback
        print(f'Error analyzing dependencies: {e}', file=sys.stderr)
        traceback.print_exc()
        return 1


def cmd_lineage(args: argparse.Namespace) -> None:
    from ..analysis.lineage import (
        extract_column_lineage, find_downstream, find_upstream,
        find_unused_columns, find_god_columns,
        format_lineage_text, format_lineage_json, format_lineage_mermaid,
    )
    files = load_files(args.migrations_dir, args.json_input)
    dialect = getattr(args, 'dialect', 'oracle')
    graph = (
        reconstruct_at(files, args.at, dialect=dialect)
        if args.at
        else reconstruct(files, dialect=dialect)
    )
    lineage = extract_column_lineage(graph, files)
    fmt = getattr(args, 'format', 'text')

    if getattr(args, 'unused_columns', False):
        unused = find_unused_columns(graph, lineage)
        if fmt == 'json':
            output = json.dumps({
                'unused_columns': [
                    {'column': col.full_name, 'table': col.table,
                     'column_name': col.column, 'created_in': version}
                    for col, version in unused
                ]
            }, indent=2)
        else:
            lines = ['Unused Columns Report', '=' * 60, '',
                     f'Found {len(unused)} unused column(s):', '']
            for col, version in unused:
                lines += [f'  {col.full_name}', f'    Created: {version}', '']
            if not unused:
                lines.append('  (none)')
            output = '\n'.join(lines)
        write_output(output, args.out)
        print(f'  {len(unused)} unused column(s)', file=sys.stderr)

    elif getattr(args, 'god_columns', False):
        min_refs = getattr(args, 'min_refs', 20)
        god_cols = find_god_columns(lineage, min_refs=min_refs)
        if fmt == 'json':
            output = json.dumps({
                'god_columns': [
                    {'column': col.full_name, 'table': col.table,
                     'column_name': col.column, 'reference_count': refs}
                    for col, refs in god_cols
                ]
            }, indent=2)
        else:
            lines = [f'God Columns Report (min_refs={min_refs})', '=' * 60, '',
                     f'Found {len(god_cols)} god column(s):', '']
            for col, refs in god_cols:
                lines += [f'  {col.full_name}', f'    Total references: {refs}', '']
            output = '\n'.join(lines)
        write_output(output, args.out)
        print(f'  {len(god_cols)} god column(s)', file=sys.stderr)

    elif args.column:
        column = args.column.upper()
        if column not in lineage:
            print(f'Error: Column not found: {column}', file=sys.stderr)
            sys.exit(1)
        direction = 'upstream' if getattr(args, 'upstream', False) else 'downstream'
        if fmt == 'json':
            output = json.dumps(lineage[column].to_dict(), indent=2)
        elif fmt == 'mermaid':
            max_depth = getattr(args, 'max_depth', 3)
            output = format_lineage_mermaid(column, lineage, direction=direction, max_depth=max_depth)
        else:
            output = format_lineage_text(column, lineage, direction=direction)
        write_output(output, args.out)
        col_lineage = lineage[column]
        count = len(col_lineage.upstream if direction == 'upstream' else col_lineage.downstream)
        print(f'  {count} {direction} column(s)', file=sys.stderr)

    else:
        output = format_lineage_json(lineage) if fmt == 'json' else (
            'Column Lineage Summary\n' + '=' * 60 + f'\n\nTotal columns analyzed: {len(lineage)}'
        )
        write_output(output, args.out)
        print(f'  {len(lineage)} column(s) analyzed', file=sys.stderr)
