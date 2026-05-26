"""
sqlfy.query
===========
Structured deterministic schema queries.

Pure graph traversal over SchemaState — no LLM, no API calls, instant.
Designed for scripting, CI pipelines, and precise programmatic lookups.

Query types
-----------
  tables          Filter tables by name pattern, schema, properties
  columns         Filter columns by name pattern, type, flags
  fk-path         Shortest FK path between two tables (BFS)
  refs            Tables that reference or are referenced by a table
  orphans         Tables with no FK relationships
  islands         Disconnected clusters of tables
  cycles          Circular FK references
  missing-pk      Tables with no primary key
  missing-fk      Columns that look like FKs but have no constraint
  impact          Tables affected by a DROP/MODIFY of a given table

Usage
-----
    from sqlfy.query import QueryEngine

    state  = SchemaStateBuilder.from_graph(reconstruct(files))
    engine = QueryEngine(state)

    # Tables
    result = engine.tables(pattern='order', schema='APP')
    result = engine.tables(has_pk=False)
    result = engine.tables(is_orphan=True)

    # Columns
    result = engine.columns(type_like='VARCHAR', is_fk=True)

    # FK path
    result = engine.fk_path('APP.ORDER_ITEMS', 'APP.USERS')
    # → [APP.ORDER_ITEMS, APP.ORDERS, APP.USERS]

    # Impact analysis
    result = engine.impact('APP.USERS')
    # → all tables that would be affected by dropping APP.USERS

    print(result.to_text())
    print(result.to_json())
"""

from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from ..domain.schema_state import SchemaState, TableState, ColumnState


# ─────────────────────────────────────────────
# RESULT TYPE
# ─────────────────────────────────────────────

@dataclass
class QueryResult:
    query:   str                        # human-readable query description
    rows:    list[dict]                 # list of result rows
    columns: list[str]                  # column headers for tabular display
    meta:    dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {'query': self.query, 'count': len(self.rows),
                'columns': self.columns, 'rows': self.rows, 'meta': self.meta}

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_text(self) -> str:
        if not self.rows:
            return f'\n  Query: {self.query}\n  No results.\n'

        lines: list[str] = [f'\n  Query   : {self.query}',
                             f'  Results : {len(self.rows)}\n']

        # Column widths
        widths = {c: len(c) for c in self.columns}
        for row in self.rows:
            for col in self.columns:
                widths[col] = max(widths[col], len(str(row.get(col, ''))))

        # Header
        header = '  ' + '  '.join(c.ljust(widths[c]) for c in self.columns)
        sep    = '  ' + '  '.join('─' * widths[c] for c in self.columns)
        lines.append(header)
        lines.append(sep)

        for row in self.rows:
            lines.append('  ' + '  '.join(
                str(row.get(c, '')).ljust(widths[c]) for c in self.columns
            ))

        lines.append('')
        return '\n'.join(lines)

    def to_csv(self) -> str:
        lines = [','.join(self.columns)]
        for row in self.rows:
            lines.append(','.join(
                f'"{str(row.get(c,"")).replace(chr(34), chr(34)*2)}"'
                for c in self.columns
            ))
        return '\n'.join(lines)

    def __len__(self) -> int:
        return len(self.rows)

    def __bool__(self) -> bool:
        return bool(self.rows)


# ─────────────────────────────────────────────
# QUERY ENGINE
# ─────────────────────────────────────────────

class QueryEngine:
    """
    Deterministic graph-traversal query engine over a SchemaState.

    All methods return a QueryResult — consistent shape regardless of query type.
    """

    def __init__(self, state: SchemaState) -> None:
        self._state = state
        # Build adjacency for path queries
        self._adj_out: dict[str, list[str]] = {t: [] for t in state.tables}
        self._adj_in:  dict[str, list[str]] = {t: [] for t in state.tables}
        self._adj_und: dict[str, list[str]] = {t: [] for t in state.tables}
        for r in state.relationships:
            # Guard against unresolved FK targets (UNRESOLVED_FK insight)
            if r.from_table not in self._adj_out:
                self._adj_out[r.from_table] = []
            if r.to_table not in self._adj_in:
                self._adj_in[r.to_table] = []
            if r.from_table not in self._adj_und:
                self._adj_und[r.from_table] = []
            if r.to_table not in self._adj_und:
                self._adj_und[r.to_table] = []
            self._adj_out[r.from_table].append(r.to_table)
            self._adj_in[r.to_table].append(r.from_table)
            self._adj_und[r.from_table].append(r.to_table)
            self._adj_und[r.to_table].append(r.from_table)

    # ── tables ─────────────────────────────────────────────────────────

    def tables(
        self,
        pattern:   Optional[str]  = None,   # regex / substring match on full name
        schema:    Optional[str]  = None,   # exact schema match (case-insensitive)
        has_pk:    Optional[bool] = None,   # filter by PK presence
        is_orphan: Optional[bool] = None,   # filter by FK isolation
        min_cols:  Optional[int]  = None,   # minimum column count
        max_cols:  Optional[int]  = None,   # maximum column count
        created_in: Optional[str] = None,   # exact migration version
    ) -> QueryResult:
        """Filter and list tables matching the given criteria."""
        filters: list[str] = []
        if pattern:    filters.append(f'name~"{pattern}"')
        if schema:     filters.append(f'schema="{schema.upper()}"')
        if has_pk is not None:    filters.append(f'has_pk={has_pk}')
        if is_orphan is not None: filters.append(f'is_orphan={is_orphan}')
        if min_cols:   filters.append(f'cols>={min_cols}')
        if max_cols:   filters.append(f'cols<={max_cols}')
        if created_in: filters.append(f'created_in=V{created_in}')
        query_str = 'SELECT tables WHERE ' + (', '.join(filters) if filters else 'ALL')

        rel_tables = {r.from_table for r in self._state.relationships} | \
                     {r.to_table   for r in self._state.relationships}

        rows: list[dict] = []
        for t in self._state.tables.values():
            orphan = t.full_name not in rel_tables
            if pattern and not re.search(pattern, t.full_name, re.I):
                continue
            if schema and (t.schema or '').upper() != schema.upper():
                continue
            if has_pk is not None and t.has_pk != has_pk:
                continue
            if is_orphan is not None and orphan != is_orphan:
                continue
            if min_cols is not None and t.column_count < min_cols:
                continue
            if max_cols is not None and t.column_count > max_cols:
                continue
            if created_in and t.created_in != created_in:
                continue

            fk_out = len(self._adj_out.get(t.full_name, []))
            fk_in  = len(self._adj_in.get(t.full_name, []))
            rows.append({
                'table':       t.full_name,
                'schema':      t.schema or '',
                'columns':     t.column_count,
                'has_pk':      '✓' if t.has_pk else '✗',
                'fk_out':      fk_out,
                'fk_in':       fk_in,
                'is_orphan':   '✓' if orphan else '',
                'created_in':  f'V{t.created_in}',
                'modified_in': ', '.join(f'V{v}' for v in t.modified_in) or '',
                'comment':     t.comment or '',
            })

        return QueryResult(
            query=query_str,
            rows=rows,
            columns=['table', 'schema', 'columns', 'has_pk', 'fk_out', 'fk_in',
                     'is_orphan', 'created_in', 'comment'],
        )

    # ── columns ────────────────────────────────────────────────────────

    def columns(
        self,
        table:     Optional[str]  = None,   # table full name pattern
        pattern:   Optional[str]  = None,   # column name pattern
        type_like: Optional[str]  = None,   # data type substring
        is_pk:     Optional[bool] = None,
        is_fk:     Optional[bool] = None,
        is_unique: Optional[bool] = None,
        nullable:  Optional[bool] = None,
        has_default: Optional[bool] = None,
    ) -> QueryResult:
        """Filter columns across all (or one) table(s)."""
        filters: list[str] = []
        if table:      filters.append(f'table~"{table}"')
        if pattern:    filters.append(f'name~"{pattern}"')
        if type_like:  filters.append(f'type~"{type_like}"')
        if is_pk is not None:     filters.append(f'is_pk={is_pk}')
        if is_fk is not None:     filters.append(f'is_fk={is_fk}')
        if is_unique is not None: filters.append(f'is_unique={is_unique}')
        if nullable is not None:  filters.append(f'nullable={nullable}')
        if has_default is not None: filters.append(f'has_default={has_default}')

        query_str = 'SELECT columns WHERE ' + (', '.join(filters) if filters else 'ALL')
        rows: list[dict] = []

        for t in self._state.tables.values():
            if table and not re.search(table, t.full_name, re.I):
                continue
            for col in t.columns:
                if pattern   and not re.search(pattern,   col.name,     re.I): continue
                if type_like and not re.search(type_like, col.data_type, re.I): continue
                if is_pk     is not None and col.is_pk     != is_pk:     continue
                if is_fk     is not None and col.is_fk     != is_fk:     continue
                if is_unique is not None and col.is_unique != is_unique:  continue
                if nullable  is not None and col.nullable  != nullable:   continue
                if has_default is not None:
                    if has_default and not col.default:   continue
                    if not has_default and col.default:   continue

                flags = []
                if col.is_pk:     flags.append('PK')
                if col.is_fk:     flags.append('FK')
                if col.is_unique: flags.append('UQ')
                if not col.nullable: flags.append('NN')

                rows.append({
                    'table':    t.full_name,
                    'column':   col.name,
                    'type':     col.data_type,
                    'flags':    ' '.join(flags),
                    'default':  col.default or '',
                    'comment':  col.comment or '',
                })

        return QueryResult(
            query=query_str,
            rows=rows,
            columns=['table', 'column', 'type', 'flags', 'default', 'comment'],
        )

    # ── fk-path ────────────────────────────────────────────────────────

    def fk_path(self, from_table: str, to_table: str) -> QueryResult:
        """
        Find the shortest FK path between two tables using BFS.

        Traverses FK edges in both directions (treats the graph as undirected)
        so it finds JOIN paths even when the FK goes 'the wrong way'.
        """
        from_upper = from_table.upper()
        to_upper   = to_table.upper()
        query_str  = f'FK-PATH FROM {from_upper} TO {to_upper}'

        if from_upper not in self._state.tables:
            return QueryResult(query=query_str, rows=[
                {'step': '✗', 'table': from_upper, 'via': f'Table not found'}
            ], columns=['step', 'table', 'via'],
            meta={'found': False, 'reason': f'{from_upper} not in schema'})

        if to_upper not in self._state.tables:
            return QueryResult(query=query_str, rows=[
                {'step': '✗', 'table': to_upper, 'via': 'Table not found'}
            ], columns=['step', 'table', 'via'],
            meta={'found': False, 'reason': f'{to_upper} not in schema'})

        if from_upper == to_upper:
            return QueryResult(query=query_str,
                rows=[{'step': 0, 'table': from_upper, 'via': '(same table)'}],
                columns=['step', 'table', 'via'],
                meta={'found': True, 'path': [from_upper], 'length': 0})

        # BFS — undirected FK graph
        visited  = {from_upper}
        queue: deque[tuple[str, list[tuple[str, str]]]] = deque()
        queue.append((from_upper, []))

        # Build edge label map for path annotation
        edge_labels: dict[tuple[str, str], str] = {}
        for r in self._state.relationships:
            label = (f'{",".join(r.from_columns)} → {",".join(r.to_columns)}'
                     + (f' [ON DELETE {r.on_delete}]' if r.on_delete else ''))
            edge_labels[(r.from_table, r.to_table)] = label
            edge_labels[(r.to_table, r.from_table)] = label + ' (↩ reverse)'

        while queue:
            current, path = queue.popleft()
            for neighbour in self._adj_und.get(current, []):
                if neighbour in visited:
                    continue
                new_path = path + [(current, neighbour)]
                if neighbour == to_upper:
                    # Reconstruct path
                    full_path = [from_upper] + [t for _, t in new_path]
                    rows = []
                    for step, (a, b) in enumerate(new_path):
                        rows.append({
                            'step':  step,
                            'table': b,
                            'via':   edge_labels.get((a, b), ''),
                        })
                    rows.insert(0, {'step': 'start', 'table': from_upper, 'via': ''})
                    return QueryResult(
                        query=query_str, rows=rows,
                        columns=['step', 'table', 'via'],
                        meta={'found': True, 'path': full_path,
                              'length': len(new_path)},
                    )
                visited.add(neighbour)
                queue.append((neighbour, new_path))

        return QueryResult(
            query=query_str,
            rows=[{'step': '✗', 'table': '—', 'via': 'No FK path found'}],
            columns=['step', 'table', 'via'],
            meta={'found': False, 'reason': 'Tables are not connected via FK edges'},
        )

    # ── refs ───────────────────────────────────────────────────────────

    def refs(self, table: str, direction: str = 'both') -> QueryResult:
        """
        Find tables that reference, or are referenced by, a given table.

        direction: 'in'  → tables that have a FK pointing TO this table
                   'out' → tables that this table points TO via FK
                   'both'→ both directions (default)
        """
        upper     = table.upper()
        query_str = f'REFS {direction.upper()} {upper}'
        rows: list[dict] = []

        if direction in ('in', 'both'):
            for r in self._state.relationships:
                if r.to_table != upper:
                    continue
                t = self._state.tables.get(r.from_table)
                rows.append({
                    'direction':  '◀ references this',
                    'table':      r.from_table,
                    'via':        ', '.join(r.from_columns),
                    'fk_name':    r.constraint_name or '',
                    'on_delete':  r.on_delete or '',
                    'cardinality': r.cardinality,
                    'cols':       t.column_count if t else '?',
                })

        if direction in ('out', 'both'):
            for r in self._state.relationships:
                if r.from_table != upper:
                    continue
                t = self._state.tables.get(r.to_table)
                rows.append({
                    'direction':  '▶ this references',
                    'table':      r.to_table,
                    'via':        ', '.join(r.from_columns),
                    'fk_name':    r.constraint_name or '',
                    'on_delete':  r.on_delete or '',
                    'cardinality': r.cardinality,
                    'cols':       t.column_count if t else '?',
                })

        return QueryResult(
            query=query_str, rows=rows,
            columns=['direction', 'table', 'via', 'fk_name', 'on_delete', 'cardinality'],
            meta={'table': upper, 'total_refs': len(rows)},
        )

    # ── orphans ────────────────────────────────────────────────────────

    def orphans(self) -> QueryResult:
        """List tables with no FK relationships in or out."""
        rel_tables = {r.from_table for r in self._state.relationships} | \
                     {r.to_table   for r in self._state.relationships}
        rows = [
            {'table': t.full_name, 'schema': t.schema or '',
             'columns': t.column_count, 'has_pk': '✓' if t.has_pk else '✗',
             'created_in': f'V{t.created_in}', 'comment': t.comment or ''}
            for t in self._state.tables.values()
            if t.full_name not in rel_tables
        ]
        return QueryResult(
            query='SELECT tables WHERE is_orphan=True',
            rows=rows,
            columns=['table', 'schema', 'columns', 'has_pk', 'created_in', 'comment'],
            meta={'orphan_count': len(rows)},
        )

    # ── islands ────────────────────────────────────────────────────────

    def islands(self) -> QueryResult:
        """Find disconnected clusters of tables (connected components)."""
        visited: set[str] = set()
        components: list[list[str]] = []
        for node in self._state.tables:
            if node in visited:
                continue
            comp: list[str] = []
            stack = [node]
            while stack:
                n = stack.pop()
                if n in visited:
                    continue
                visited.add(n); comp.append(n)
                stack.extend(nb for nb in self._adj_und.get(n, []) if nb not in visited)
            components.append(sorted(comp))

        components.sort(key=len, reverse=True)
        rows: list[dict] = []
        for i, comp in enumerate(components):
            label = 'main' if i == 0 and len(comp) == max(len(c) for c in components) else f'island-{i}'
            for t in comp:
                rows.append({'component': label, 'table': t,
                             'size': len(comp), 'is_island': i > 0 or len(components) == 1})

        return QueryResult(
            query='FIND disconnected table clusters',
            rows=rows,
            columns=['component', 'table', 'size', 'is_island'],
            meta={'component_count': len(components),
                  'island_count': sum(1 for c in components if len(c) > 1) - 1},
        )

    # ── cycles ─────────────────────────────────────────────────────────

    def cycles(self) -> QueryResult:
        """Detect circular FK references using DFS."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color:  dict[str, int] = {n: WHITE for n in self._state.tables}
        parent: dict[str, Optional[str]] = {n: None for n in self._state.tables}
        found:  list[list[str]] = []
        seen:   set[frozenset] = set()

        def dfs(node: str) -> None:
            color[node] = GRAY
            for nb in self._adj_out.get(node, []):
                if nb not in color:
                    continue
                if color[nb] == GRAY:
                    cycle: list[str] = [nb, node]
                    cur = node
                    while parent.get(cur) and parent[cur] != nb:
                        cur = parent[cur]  # type: ignore[assignment]
                        cycle.append(cur)
                    cycle_key = frozenset(cycle)
                    if cycle_key not in seen:
                        seen.add(cycle_key)
                        found.append(list(reversed(cycle)))
                elif color[nb] == WHITE:
                    parent[nb] = node
                    dfs(nb)
            color[node] = BLACK

        for node in list(self._state.tables.keys()):
            if color[node] == WHITE:
                dfs(node)

        rows = [
            {'cycle_id': i + 1, 'length': len(c),
             'path': ' → '.join(c) + f' → {c[0]}'}
            for i, c in enumerate(found)
        ]
        return QueryResult(
            query='FIND FK cycles',
            rows=rows,
            columns=['cycle_id', 'length', 'path'],
            meta={'cycle_count': len(found)},
        )

    # ── missing-pk ─────────────────────────────────────────────────────

    def missing_pk(self) -> QueryResult:
        """List tables with no primary key constraint."""
        rows = [
            {'table': t.full_name, 'schema': t.schema or '',
             'columns': t.column_count,
             'created_in': f'V{t.created_in}', 'comment': t.comment or ''}
            for t in self._state.tables.values() if not t.has_pk
        ]
        return QueryResult(
            query='SELECT tables WHERE has_pk=False',
            rows=rows,
            columns=['table', 'schema', 'columns', 'created_in', 'comment'],
            meta={'count': len(rows)},
        )

    # ── missing-fk ─────────────────────────────────────────────────────

    def missing_fk(self) -> QueryResult:
        """
        Find columns that look like foreign keys (name ends in _id, _key, _ref, _fk)
        but have no actual FK constraint.
        """
        _PATTERN = re.compile(r'(?:_id|_key|_fk|_ref)$', re.I)
        fk_col_map: dict[str, set[str]] = {}
        for r in self._state.relationships:
            fk_col_map.setdefault(r.from_table, set()).update(r.from_columns)

        rows: list[dict] = []
        for t in self._state.tables.values():
            fk_cols = fk_col_map.get(t.full_name, set())
            for col in t.columns:
                if _PATTERN.search(col.name) and col.name not in fk_cols and not col.is_pk:
                    rows.append({
                        'table':   t.full_name,
                        'column':  col.name,
                        'type':    col.data_type,
                        'nullable': '✓' if col.nullable else '✗',
                        'suggestion': (
                            f'FOREIGN KEY ({col.name}) REFERENCES <table>(<pk>)'
                        ),
                    })

        return QueryResult(
            query='SELECT columns WHERE looks_like_fk AND has_no_fk_constraint',
            rows=rows,
            columns=['table', 'column', 'type', 'nullable', 'suggestion'],
            meta={'count': len(rows)},
        )

    # ── impact ─────────────────────────────────────────────────────────

    def impact(self, table: str, cascade: bool = True) -> QueryResult:
        """
        Find all tables affected by a DROP or MODIFY of the given table.

        Traverses FK edges INWARD — tables that reference this one would
        break or cascade. Returns a BFS-ordered list with depth and
        cascade behaviour at each hop.
        """
        upper     = table.upper()
        query_str = f'IMPACT ANALYSIS: DROP {upper}'

        rows: list[dict] = []
        visited = {upper}
        queue: deque[tuple[str, int, str]] = deque()

        # Seed with direct inbound references
        for r in self._state.relationships:
            if r.to_table == upper:
                if r.from_table not in visited:
                    visited.add(r.from_table)
                    action = f'CASCADE DELETE' if r.on_delete == 'CASCADE' else \
                             f'SET NULL' if r.on_delete == 'SET_NULL' else \
                             'RESTRICT / ERROR'
                    queue.append((r.from_table, 1, action))
                    rows.append({
                        'depth':       1,
                        'table':       r.from_table,
                        'fk':          r.constraint_name or 'unnamed',
                        'via_column':  ', '.join(r.from_columns),
                        'action':      action,
                    })

        # BFS further
        while queue:
            current, depth, _ = queue.popleft()
            for r in self._state.relationships:
                if r.to_table != current or r.from_table in visited:
                    continue
                visited.add(r.from_table)
                action = f'CASCADE' if r.on_delete == 'CASCADE' else \
                         f'SET NULL' if r.on_delete == 'SET_NULL' else 'RESTRICT'
                queue.append((r.from_table, depth + 1, action))
                rows.append({
                    'depth':      depth + 1,
                    'table':      r.from_table,
                    'fk':         r.constraint_name or 'unnamed',
                    'via_column': ', '.join(r.from_columns),
                    'action':     action,
                })

        rows.sort(key=lambda r: r['depth'])
        return QueryResult(
            query=query_str, rows=rows,
            columns=['depth', 'table', 'fk', 'via_column', 'action'],
            meta={'target': upper, 'affected_count': len(rows)},
        )

    # ── indexes ────────────────────────────────────────────────────────

    def indexes(self, table: Optional[str] = None,
                unique_only: bool = False) -> QueryResult:
        """List all indexes, optionally filtered by table or uniqueness."""
        query_str = 'SELECT indexes'
        if table:       query_str += f' WHERE table~"{table}"'
        if unique_only: query_str += ' AND unique=True'
        rows: list[dict] = []
        for t in self._state.tables.values():
            if table and not re.search(table, t.full_name, re.I):
                continue
            for idx in t.indexes:
                if unique_only and not idx.unique:
                    continue
                rows.append({
                    'table':      t.full_name,
                    'index':      idx.name,
                    'columns':    ', '.join(idx.columns),
                    'unique':     '✓' if idx.unique else '',
                    'created_in': f'V{idx.created_in}',
                })
        return QueryResult(
            query=query_str, rows=rows,
            columns=['table', 'index', 'columns', 'unique', 'created_in'],
        )