"""
sqlfy.insights
==============
Graphify-style schema insights engine.

Analyses a SchemaState and produces categorised findings covering:

  ── Structural ──────────────────────────────────────────────────────
  ORPHAN_TABLE          Table with no FK relationships in or out
  NO_PK                 Table missing a primary key constraint
  NO_INDEXES            Table with no indexes at all (excl. PK)
  WIDE_TABLE            Table with many columns (heuristic: > 20)
  EMPTY_TABLE_COMMENT   Table has no COMMENT ON TABLE

  ── Referential integrity ────────────────────────────────────────────
  MISSING_FK_CANDIDATE  Column named *_id / *_key with no FK constraint
  UNRESOLVED_FK         FK pointing to a table not in the schema
  NULLABLE_FK           FK column is nullable (cascade semantics unclear)
  CIRCULAR_FK           Cycle detected in the FK graph

  ── Data modelling ──────────────────────────────────────────────────
  NULLABLE_PK           PK column marked nullable
  VARCHAR_ID            ID/key column using VARCHAR instead of NUMBER
  ORPHAN_SEQUENCE       Sequence with no apparent associated table
  DUPLICATE_INDEX       Two indexes on the same column set in same table
  UNIQUE_WITHOUT_INDEX  UNIQUE constraint with no backing index defined

  ── Connectivity ────────────────────────────────────────────────────
  ISLAND                Group of tables connected to each other
                        but disconnected from the rest of the schema

Severities
----------
  error    Almost certainly a problem (missing FK target, nullable PK)
  warning  Likely a problem or unintentional gap
  info     Observation worth knowing — may be intentional

Usage
-----
    from cli.insights import InsightsEngine

    state  = SchemaStateBuilder.from_graph(reconstruct(files))
    report = InsightsEngine.analyse(state)

    print(report.to_text())
    print(report.to_json())
    print(report.summary())
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from ..domain.schema_state import SchemaState, TableState


# ─────────────────────────────────────────────
# FINDING
# ─────────────────────────────────────────────

SEVERITIES = ('error', 'warning', 'info')

@dataclass
class Finding:
    code:      str            # e.g. "ORPHAN_TABLE"
    severity:  str            # error | warning | info
    category:  str            # structural | referential | modelling | connectivity
    message:   str            # human-readable description
    table:     Optional[str] = None    # affected table (full name)
    column:    Optional[str] = None    # affected column (if applicable)
    detail:    Optional[str] = None    # extra context
    fix:       Optional[str] = None    # suggested fix

    def to_dict(self) -> dict:
        d: dict = {
            'code': self.code, 'severity': self.severity,
            'category': self.category, 'message': self.message,
        }
        if self.table:  d['table']  = self.table
        if self.column: d['column'] = self.column
        if self.detail: d['detail'] = self.detail
        if self.fix:    d['fix']    = self.fix
        return d


# ─────────────────────────────────────────────
# REPORT
# ─────────────────────────────────────────────

@dataclass
class InsightsReport:
    version:     str
    fingerprint: str
    findings:    list[Finding] = field(default_factory=list)

    # ── Accessors ──────────────────────────────────────────────────────

    def errors(self)   -> list[Finding]: return [f for f in self.findings if f.severity == 'error']
    def warnings(self) -> list[Finding]: return [f for f in self.findings if f.severity == 'warning']
    def infos(self)    -> list[Finding]: return [f for f in self.findings if f.severity == 'info']
    def by_code(self, code: str) -> list[Finding]: return [f for f in self.findings if f.code == code]
    def by_table(self, full: str) -> list[Finding]: return [f for f in self.findings if f.table == full]

    def is_healthy(self) -> bool:
        return len(self.errors()) == 0 and len(self.warnings()) == 0

    def summary(self) -> str:
        e, w, i = len(self.errors()), len(self.warnings()), len(self.infos())
        status   = '✓ healthy' if self.is_healthy() else ('✖ issues found' if e else '⚠ warnings found')
        return (f'Schema V{self.version} — {status}  '
                f'({e} errors, {w} warnings, {i} info)')

    # ── Serialisation ──────────────────────────────────────────────────

    def to_dict(self) -> dict:
        by_sev: dict[str, list[dict]] = {s: [] for s in SEVERITIES}
        for f in self.findings:
            by_sev.get(f.severity, by_sev['info']).append(f.to_dict())
        return {
            'version':     self.version,
            'fingerprint': self.fingerprint,
            'summary':     {
                'errors':   len(self.errors()),
                'warnings': len(self.warnings()),
                'infos':    len(self.infos()),
                'total':    len(self.findings),
                'healthy':  self.is_healthy(),
            },
            'findings':    by_sev,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_text(self) -> str:
        lines: list[str] = []
        a = lines.append

        a('\n╔══════════════════════════════════════════╗')
        a('║          SCHEMA INSIGHTS                 ║')
        a('╚══════════════════════════════════════════╝\n')
        a(f'  {self.summary()}')
        a(f'  Fingerprint: {self.fingerprint}\n')

        icons = {'error': '✖', 'warning': '⚠', 'info': 'ℹ'}

        for severity in SEVERITIES:
            group = [f for f in self.findings if f.severity == severity]
            if not group:
                continue
            label = severity.upper()
            a(f'  {"─" * 44}')
            a(f'  {icons[severity]}  {label}S ({len(group)})')
            a(f'  {"─" * 44}')
            for f in group:
                table_tag  = f'  [{f.table}]' if f.table else ''
                column_tag = f'.{f.column}' if f.column else ''
                a(f'\n  [{f.code}]{table_tag}{column_tag}')
                a(f'  {f.message}')
                if f.detail: a(f'  Detail : {f.detail}')
                if f.fix:    a(f'  Fix    : {f.fix}')
            a('')

        if not self.findings:
            a('  No issues detected — schema looks healthy!')
            a('')

        return '\n'.join(lines)


# ─────────────────────────────────────────────
# GRAPH UTILITIES (for island / cycle detection)
# ─────────────────────────────────────────────

def _build_adjacency(state: SchemaState) -> dict[str, set[str]]:
    """Undirected adjacency list for connectivity analysis."""
    adj: dict[str, set[str]] = defaultdict(set)
    for t in state.tables:
        adj[t]  # ensure all nodes present
    for r in state.relationships:
        adj[r.from_table].add(r.to_table)
        adj[r.to_table].add(r.from_table)
    return dict(adj)


def _connected_components(adj: dict[str, set[str]]) -> list[set[str]]:
    """Union-find connected components."""
    visited: set[str] = set()
    components: list[set[str]] = []
    for node in adj:
        if node in visited:
            continue
        component: set[str] = set()
        stack = [node]
        while stack:
            n = stack.pop()
            if n in visited:
                continue
            visited.add(n)
            component.add(n)
            stack.extend(adj.get(n, set()) - visited)
        components.append(component)
    return components


def _has_cycle(adj_directed: dict[str, set[str]]) -> list[list[str]]:
    """Detect cycles in the directed FK graph. Returns list of cycles found."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in adj_directed}
    parent: dict[str, Optional[str]] = {n: None for n in adj_directed}
    cycles: list[list[str]] = []

    def dfs(node: str) -> None:
        color[node] = GRAY
        for nb in adj_directed.get(node, set()):
            if nb not in color:
                continue
            if color[nb] == GRAY:
                # Found a cycle — reconstruct it
                cycle = [nb, node]
                cur   = node
                while parent.get(cur) and parent[cur] != nb:
                    cur = parent[cur]  # type: ignore[assignment]
                    cycle.append(cur)
                cycles.append(list(reversed(cycle)))
            elif color[nb] == WHITE:
                parent[nb] = node
                dfs(nb)
        color[node] = BLACK

    for node in list(adj_directed.keys()):
        if color[node] == WHITE:
            dfs(node)

    return cycles


# ─────────────────────────────────────────────
# INSIGHTS ENGINE
# ─────────────────────────────────────────────

# Heuristic thresholds
_WIDE_TABLE_COLS   = 20    # columns
_ID_SUFFIX_PATTERN = re.compile(r'(?:_id|_key|_fk|_ref)$', re.I)
_VARCHAR_TYPES     = {'VARCHAR', 'VARCHAR2', 'CHAR', 'NVARCHAR', 'NCHAR', 'TEXT'}
_NUMBER_TYPES      = {'NUMBER', 'INTEGER', 'INT', 'NUMERIC', 'DECIMAL', 'BIGINT', 'SMALLINT'}


class InsightsEngine:
    """Stateless analyser — call InsightsEngine.analyse(state)."""

    @staticmethod
    def analyse(state: SchemaState) -> InsightsReport:
        report = InsightsReport(version=state.version, fingerprint=state.fingerprint)
        add    = report.findings.append

        rel_tables_out = defaultdict(list)   # from_table → [rels]
        rel_tables_in  = defaultdict(list)   # to_table   → [rels]
        for r in state.relationships:
            rel_tables_out[r.from_table].append(r)
            rel_tables_in[r.to_table].append(r)

        known_tables = set(state.tables.keys())

        # ── Directed adjacency for cycle detection ──────────────────────
        dir_adj: dict[str, set[str]] = defaultdict(set)
        for r in state.relationships:
            dir_adj[r.from_table].add(r.to_table)

        # ── Undirected adjacency for island detection ───────────────────
        undir_adj = _build_adjacency(state)

        # ── Per-table FK column set ─────────────────────────────────────
        fk_col_map: dict[str, set[str]] = defaultdict(set)
        for r in state.relationships:
            for c in r.from_columns:
                fk_col_map[r.from_table].add(c.upper())

        # ═══════════════════════════════════════
        # STRUCTURAL
        # ═══════════════════════════════════════

        for full, t in state.tables.items():
            out = rel_tables_out[full]
            inn = rel_tables_in[full]

            # ORPHAN_TABLE
            if not out and not inn:
                add(Finding(
                    code='ORPHAN_TABLE', severity='warning', category='structural',
                    table=full,
                    message=f'Table {t.name} has no FK relationships in or out.',
                    detail='It is disconnected from the rest of the schema.',
                    fix='Add a FK to or from a related table, or confirm this is intentional.',
                ))

            # NO_PK
            if not t.has_pk:
                add(Finding(
                    code='NO_PK', severity='error', category='structural',
                    table=full,
                    message=f'Table {t.name} has no PRIMARY KEY constraint.',
                    fix='Add a PRIMARY KEY constraint to uniquely identify rows.',
                ))

            # NO_INDEXES (excluding tables where PK implies index)
            non_pk_indexes = [i for i in t.indexes]
            if not non_pk_indexes and len(t.columns) > 2:
                add(Finding(
                    code='NO_INDEXES', severity='info', category='structural',
                    table=full,
                    message=f'Table {t.name} has no explicit indexes.',
                    detail='Only the implicit PK index exists.',
                    fix='Consider adding indexes on frequently queried or FK columns.',
                ))

            # WIDE_TABLE
            if t.column_count > _WIDE_TABLE_COLS:
                add(Finding(
                    code='WIDE_TABLE', severity='info', category='structural',
                    table=full,
                    message=f'Table {t.name} has {t.column_count} columns (>{_WIDE_TABLE_COLS} threshold).',
                    detail='Wide tables may indicate a design that could benefit from vertical splitting.',
                    fix='Consider splitting into multiple related tables.',
                ))

            # EMPTY_TABLE_COMMENT
            if not t.comment:
                add(Finding(
                    code='EMPTY_TABLE_COMMENT', severity='info', category='structural',
                    table=full,
                    message=f'Table {t.name} has no COMMENT ON TABLE.',
                    fix=f"Add: COMMENT ON TABLE {full} IS '...'",
                ))

        # ═══════════════════════════════════════
        # REFERENTIAL INTEGRITY
        # ═══════════════════════════════════════

        for full, t in state.tables.items():
            fk_cols = fk_col_map[full]

            for col in t.columns:
                # MISSING_FK_CANDIDATE
                if _ID_SUFFIX_PATTERN.search(col.name) and col.name not in fk_cols:
                    # Don't flag PK columns
                    if not col.is_pk:
                        add(Finding(
                            code='MISSING_FK_CANDIDATE', severity='warning',
                            category='referential',
                            table=full, column=col.name,
                            message=(f'{t.name}.{col.name} looks like a FK column '
                                     f'but has no FOREIGN KEY constraint.'),
                            detail=f'Column type: {col.data_type}',
                            fix=(f'Add: CONSTRAINT fk_{t.name.lower()}_{col.name.lower()} '
                                 f'FOREIGN KEY ({col.name}) REFERENCES <target_table>(<pk>)'),
                        ))

                # NULLABLE_FK
                if col.is_fk and col.nullable:
                    add(Finding(
                        code='NULLABLE_FK', severity='info', category='referential',
                        table=full, column=col.name,
                        message=(f'{t.name}.{col.name} is a FK column but is nullable.'),
                        detail='NULL FK values mean "no relationship" — ensure this is intentional.',
                        fix='Add NOT NULL if every row must reference a parent.',
                    ))

            # UNRESOLVED_FK — FK pointing to a table not in the schema
            for con in t.constraints:
                if con.type == 'foreign_key' and con.ref_table:
                    if con.ref_table not in known_tables:
                        add(Finding(
                            code='UNRESOLVED_FK', severity='error', category='referential',
                            table=full,
                            message=(f'{t.name} has a FK to {con.ref_table} '
                                     f'which is not in the schema.'),
                            detail=f'Constraint: {con.name or "unnamed"}, columns: {con.columns}',
                            fix='Ensure the referenced table is included in the migration set.',
                        ))

            # NULLABLE_PK
            for col in t.columns:
                if col.is_pk and col.nullable:
                    add(Finding(
                        code='NULLABLE_PK', severity='error', category='modelling',
                        table=full, column=col.name,
                        message=f'{t.name}.{col.name} is part of the PK but is nullable.',
                        fix='Add NOT NULL to all PK columns.',
                    ))

        # CIRCULAR_FK
        cycles = _has_cycle(dict(dir_adj))
        seen_cycles: set[frozenset] = set()
        for cycle in cycles:
            key = frozenset(cycle)
            if key in seen_cycles:
                continue
            seen_cycles.add(key)
            cycle_str = ' → '.join(cycle)
            add(Finding(
                code='CIRCULAR_FK', severity='warning', category='referential',
                message=f'Circular FK reference detected: {cycle_str}',
                detail='Circular FKs can complicate inserts, deletes, and cascade operations.',
                fix='Consider breaking the cycle with a nullable FK or a junction table.',
            ))

        # ═══════════════════════════════════════
        # DATA MODELLING
        # ═══════════════════════════════════════

        for full, t in state.tables.items():
            # VARCHAR_ID — ID/key column using a string type
            for col in t.columns:
                if (_ID_SUFFIX_PATTERN.search(col.name)
                        and col.raw_type.upper() in _VARCHAR_TYPES
                        and not col.is_pk):
                    add(Finding(
                        code='VARCHAR_ID', severity='warning', category='modelling',
                        table=full, column=col.name,
                        message=(f'{t.name}.{col.name} is an ID/key column '
                                 f'using {col.raw_type} instead of a numeric type.'),
                        detail='String IDs have slower joins and index performance than integers.',
                        fix='Consider NUMBER or INTEGER unless the ID is intentionally alphanumeric.',
                    ))

            # DUPLICATE_INDEX — two indexes covering the exact same columns
            idx_sig: dict[tuple, list[str]] = defaultdict(list)
            for idx in t.indexes:
                sig = tuple(sorted(idx.columns))
                idx_sig[sig].append(idx.name)
            for sig, names in idx_sig.items():
                if len(names) > 1:
                    add(Finding(
                        code='DUPLICATE_INDEX', severity='warning', category='modelling',
                        table=full,
                        message=(f'{t.name} has {len(names)} indexes on the same '
                                 f'column set ({", ".join(sig)}): {", ".join(names)}'),
                        fix=f'Drop all but one of: {", ".join(names)}',
                    ))

            # UNIQUE_WITHOUT_INDEX — UNIQUE constraint with no backing index
            unique_col_sets = [
                frozenset(c.columns)
                for c in t.constraints if c.type == 'unique'
            ]
            indexed_col_sets = [
                frozenset(i.columns)
                for i in t.indexes
            ]
            for uc_set in unique_col_sets:
                if uc_set and uc_set not in indexed_col_sets:
                    cols_str = ', '.join(sorted(uc_set))
                    add(Finding(
                        code='UNIQUE_WITHOUT_INDEX', severity='info', category='modelling',
                        table=full,
                        message=(f'{t.name} has a UNIQUE constraint on ({cols_str}) '
                                 f'with no explicit backing index.'),
                        detail='Oracle/Postgres auto-creates an index for UNIQUE constraints; '
                               'explicit index may still be useful for query plans.',
                        fix=f'Add: CREATE UNIQUE INDEX ... ON {full}({cols_str})',
                    ))

        # ORPHAN_SEQUENCE — sequence with no table sharing its name prefix
        table_name_set = {t.name.upper() for t in state.tables.values()}
        for full, seq in state.sequences.items():
            sname = seq.name.upper()
            # Strip common prefixes: SEQ_, S_, SQ_
            stripped = re.sub(r'^(SEQ_|S_|SQ_)', '', sname)
            # Check if any table name is a substring
            matched = any(
                stripped.startswith(tname) or tname.startswith(stripped)
                for tname in table_name_set
            )
            if not matched:
                add(Finding(
                    code='ORPHAN_SEQUENCE', severity='info', category='modelling',
                    message=f'Sequence {seq.full_name} has no obvious associated table.',
                    detail=f'No table name matches the sequence name pattern "{stripped}".',
                    fix='Verify this sequence is still in use or drop it.',
                ))

        # ═══════════════════════════════════════
        # CONNECTIVITY — ISLANDS
        # ═══════════════════════════════════════

        components = _connected_components(undir_adj)
        # Only flag as islands if there are multiple non-trivial connected components
        non_trivial = [c for c in components if len(c) > 1]
        if len(non_trivial) > 1:
            for idx, comp in enumerate(sorted(non_trivial, key=len, reverse=True)):
                if idx == 0:
                    continue  # largest component is the "main" schema — not an island
                tables_str = ', '.join(sorted(comp))
                add(Finding(
                    code='ISLAND', severity='warning', category='connectivity',
                    message=(f'Island detected: {len(comp)} tables are connected '
                             f'to each other but isolated from the main schema.'),
                    detail=f'Island tables: {tables_str}',
                    fix='Check whether these tables should reference main-schema tables via FK.',
                ))

        # Sort: errors first, then warnings, then info; within severity by table name
        sev_order = {'error': 0, 'warning': 1, 'info': 2}
        report.findings.sort(key=lambda f: (sev_order[f.severity], f.table or '', f.code))

        return report