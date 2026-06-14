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

  ── Migration-specific ──────────────────────────────────────────────
  ADD_NOT_NULL_NO_DEFAULT     ALTER TABLE ADD column NOT NULL without DEFAULT
  DROP_COLUMN_IN_USE          DROP COLUMN referenced by views/triggers
  SELECT_STAR_VIEW            CREATE VIEW with SELECT * pattern
  LARGE_DELETE_NO_WHERE       DELETE/TRUNCATE without WHERE clause
  TRIGGER_WITH_BUSINESS_LOGIC Complex trigger with business logic

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
from .query import QueryEngine


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
# GOD-TABLE FINDING
# ─────────────────────────────────────────────

@dataclass
class GodTableFinding:
    table_name: str
    degree: int
    in_degree: int
    out_degree: int
    community_id: Optional[int] = None
    community_label: Optional[str] = None

    def to_dict(self) -> dict:
        d: dict = {
            'tableName': self.table_name,
            'degree': self.degree,
            'inDegree': self.in_degree,
            'outDegree': self.out_degree,
        }
        if self.community_id is not None:
            d['communityId'] = self.community_id
        if self.community_label is not None:
            d['communityLabel'] = self.community_label
        return d


# ─────────────────────────────────────────────
# SURPRISING JOIN FINDING
# ─────────────────────────────────────────────

@dataclass
class SurprisingJoinFinding:
    from_table: str
    to_table: str
    via_column: str
    from_community: Optional[int] = None
    to_community: Optional[int] = None
    from_community_label: Optional[str] = None
    to_community_label: Optional[str] = None
    surprise_score: float = 0.0

    def to_dict(self) -> dict:
        d: dict = {
            'fromTable': self.from_table,
            'toTable': self.to_table,
            'viaColumn': self.via_column,
            'surpriseScore': self.surprise_score,
        }
        if self.from_community is not None:
            d['fromCommunity'] = self.from_community
        if self.to_community is not None:
            d['toCommunity'] = self.to_community
        if self.from_community_label is not None:
            d['fromCommunityLabel'] = self.from_community_label
        if self.to_community_label is not None:
            d['toCommunityLabel'] = self.to_community_label
        return d


# ─────────────────────────────────────────────
# REPORT
# ─────────────────────────────────────────────

@dataclass
class InsightsReport:
    version:     str
    fingerprint: str
    findings:    list[Finding] = field(default_factory=list)
    god_tables:  list[GodTableFinding] = field(default_factory=list)
    surprising_joins: list[SurprisingJoinFinding] = field(default_factory=list)

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
            'godTables':   [g.to_dict() for g in self.god_tables],
            'surprisingJoins': [s.to_dict() for s in self.surprising_joins],
        }

    def to_json(self, indent: int = 2) -> str:
        from ..models import (
            InsightsResult as _InsightsResult,
            InsightsSummary as _InsightsSummary,
            InsightFinding as _InsightFinding,
            Findings as _Findings,
            InsightSeverity as _InsightSeverity,
            GodTableFinding as _GodTableFinding,
            SurprisingJoinFinding as _SurprisingJoinFinding,
        )
        def _finding(f: Finding) -> _InsightFinding:
            return _InsightFinding(
                code=f.code,
                severity=_InsightSeverity(f.severity),
                category=f.category,
                message=f.message,
                detail=f.detail,
                fix=f.fix,
                table=f.table,
                column=f.column,
            )
        def _god(g: GodTableFinding) -> _GodTableFinding:
            return _GodTableFinding(
                table_name=g.table_name,
                degree=g.degree,
                in_degree=g.in_degree,
                out_degree=g.out_degree,
                community_id=g.community_id,
                community_label=g.community_label,
            )
        def _surprising(s: SurprisingJoinFinding) -> _SurprisingJoinFinding:
            return _SurprisingJoinFinding(
                from_table=s.from_table,
                to_table=s.to_table,
                via_column=s.via_column,
                from_community=s.from_community,
                to_community=s.to_community,
                from_community_label=s.from_community_label,
                to_community_label=s.to_community_label,
                surprise_score=s.surprise_score,
            )
        model = _InsightsResult(
            version=self.version,
            fingerprint=self.fingerprint,
            summary=_InsightsSummary(
                errors=len(self.errors()),
                warnings=len(self.warnings()),
                infos=len(self.infos()),
                total=len(self.findings),
                healthy=self.is_healthy(),
            ),
            findings=_Findings(
                error=[_finding(f) for f in self.errors()],
                warning=[_finding(f) for f in self.warnings()],
                info=[_finding(f) for f in self.infos()],
            ),
            god_tables=[_god(g) for g in self.god_tables],
            surprising_joins=[_surprising(s) for s in self.surprising_joins],
        )
        return model.model_dump_json(by_alias=True, indent=indent)

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

        # ── God Tables ─────────────────────────────────────────────────
        if self.god_tables:
            a(f'  {"━" * 44}')
            a(f'  ♛  GOD TABLES (top {len(self.god_tables)})')
            a(f'  {"━" * 44}')
            for g in self.god_tables:
                tag = f'  [{g.community_label}]' if g.community_label else ''
                a(f'\n  {g.table_name}{tag}')
                a(f'  degree={g.degree}  (in={g.in_degree} out={g.out_degree})')
            a('')

        # ── Surprising Cross-Domain Joins ──────────────────────────────
        if self.surprising_joins:
            a(f'  {"━" * 44}')
            a(f'  ⚡  SURPRISING CROSS-DOMAIN JOINS (top {len(self.surprising_joins)})')
            a(f'  {"━" * 44}')
            for s in self.surprising_joins:
                from_label = s.from_community_label or str(s.from_community) if s.from_community is not None else '?'
                to_label   = s.to_community_label   or str(s.to_community)   if s.to_community   is not None else '?'
                a(f'\n  {s.from_table}.{s.via_column}  →  {s.to_table}')
                a(f'  surprise={s.surprise_score:.2f}  ({from_label} → {to_label})')
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
                while True:
                    next_cur = parent.get(cur)
                    if not next_cur or next_cur == nb:
                        break
                    cur = next_cur
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
# GOD-TABLE DETECTION
# ─────────────────────────────────────────────

def _detect_god_tables(
    state: SchemaState,
    top_n: int = 10,
    communities: dict[int, list[str]] | None = None,
) -> list[GodTableFinding]:
    """Find tables with abnormally high FK degree (>2σ above mean)."""
    if not state.tables:
        return []

    # Build community lookup
    node_to_community: dict[str, int] = {}
    if communities:
        for cid, tables in communities.items():
            for t in tables:
                node_to_community[t] = cid

    # Compute degree per table from relationships
    in_degree: dict[str, int] = defaultdict(int)
    out_degree: dict[str, int] = defaultdict(int)
    for r in state.relationships:
        out_degree[r.from_table] += 1
        in_degree[r.to_table] += 1

    degrees: dict[str, int] = {}
    for t in state.tables:
        degrees[t] = in_degree.get(t, 0) + out_degree.get(t, 0)

    if not degrees:
        return []

    # Compute mean and std dev
    vals = list(degrees.values())
    n = len(vals)
    mean = sum(vals) / n
    variance = sum((v - mean) ** 2 for v in vals) / n
    std_dev = variance ** 0.5

    # Filter: > 2σ above mean, or top_n when std_dev is 0
    threshold = mean + 2 * std_dev if std_dev > 0 else float('inf')

    candidates = [(t, d) for t, d in degrees.items() if d > threshold]
    candidates.sort(key=lambda x: x[1], reverse=True)

    if std_dev == 0 and candidates:
        # All degrees are the same — just take top_n
        pass
    elif not candidates and std_dev == 0:
        # Uniform degree — take top_n by degree descending
        candidates = sorted(degrees.items(), key=lambda x: x[1], reverse=True)

    if not candidates:
        return []

    results: list[GodTableFinding] = []
    for table_name, degree in candidates[:top_n]:
        comm_id = node_to_community.get(table_name)
        results.append(GodTableFinding(
            table_name=table_name,
            degree=degree,
            in_degree=in_degree.get(table_name, 0),
            out_degree=out_degree.get(table_name, 0),
            community_id=comm_id,
        ))

    return results


# ─────────────────────────────────────────────
# SURPRISING JOIN DETECTION
# ─────────────────────────────────────────────

def _detect_surprising_joins(
    state: SchemaState,
    communities: dict[int, list[str]] | None = None,
    top_n: int = 20,
) -> list[SurprisingJoinFinding]:
    """Find cross-community FK edges with surprise scores."""
    if not communities or not state.relationships:
        return []

    # Build node → community map
    node_to_community: dict[str, int] = {}
    for cid, tables in communities.items():
        for t in tables:
            node_to_community[t] = cid

    # Build neighbour sets per table for shared-neighbour computation
    neighbours: dict[str, set[str]] = defaultdict(set)
    for r in state.relationships:
        neighbours[r.from_table].add(r.to_table)
        neighbours[r.to_table].add(r.from_table)

    findings: list[SurprisingJoinFinding] = []

    for r in state.relationships:
        from_comm = node_to_community.get(r.from_table)
        to_comm   = node_to_community.get(r.to_table)

        # Skip if same community or missing community info
        if from_comm is None or to_comm is None or from_comm == to_comm:
            continue

        # Compute surprise score:
        #   1.0 - (shared_neighbours / total_neighbours)
        from_nbrs = neighbours.get(r.from_table, set()) - {r.to_table}
        to_nbrs   = neighbours.get(r.to_table, set()) - {r.from_table}
        total     = len(from_nbrs | to_nbrs)
        shared    = len(from_nbrs & to_nbrs)
        surprise  = 1.0 - (shared / total) if total > 0 else 1.0

        # Column name for the FK
        via_column = ', '.join(r.from_columns) if r.from_columns else '?'

        findings.append(SurprisingJoinFinding(
            from_table=r.from_table,
            to_table=r.to_table,
            via_column=via_column,
            from_community=from_comm,
            to_community=to_comm,
            surprise_score=round(surprise, 4),
        ))

    findings.sort(key=lambda f: f.surprise_score, reverse=True)
    return findings[:top_n]


# ─────────────────────────────────────────────
# INSIGHTS ENGINE
# ─────────────────────────────────────────────

# Heuristic thresholds
_WIDE_TABLE_COLS   = 20    # columns
_ID_SUFFIX_PATTERN = re.compile(r'(?:_id|_key|_fk|_ref)$', re.I)
_VARCHAR_TYPES     = {'VARCHAR', 'VARCHAR2', 'CHAR', 'NVARCHAR', 'NCHAR', 'TEXT'}
_NUMBER_TYPES      = {'NUMBER', 'INTEGER', 'INT', 'NUMERIC', 'DECIMAL', 'BIGINT', 'SMALLINT'}

# Migration-specific anti-pattern regexes — compiled once at module level (Fix #5)
_ALTER_ADD_PATTERN = re.compile(
    r'ALTER\s+TABLE\s+(\w+)\s+ADD\s+\(\s*(\w+)\s+([^;]+)\);',
    re.IGNORECASE | re.DOTALL,
)
_VIEW_PATTERN    = re.compile(r'CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+(\w+)', re.IGNORECASE)
_TRIGGER_PATTERN = re.compile(r'CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+(\w+)', re.IGNORECASE)
_DELETE_PATTERN  = re.compile(r'DELETE\s+FROM\s+(\w+)(?!\s+WHERE)', re.IGNORECASE | re.DOTALL)


class InsightsEngine:
    """Stateless analyser — call InsightsEngine.analyse(state)."""

    @staticmethod
    def analyse(
        state: SchemaState,
        files: list[dict] | None = None,
        communities: dict[int, list[str]] | None = None,
    ) -> InsightsReport:
        report = InsightsReport(version=state.version, fingerprint=state.fingerprint)
        add    = report.findings.append

        # Build QueryEngine once — reused for cycle and island detection (Fix #9).
        _engine = QueryEngine(state)

        rel_tables_out = defaultdict(list)   # from_table → [rels]
        rel_tables_in  = defaultdict(list)   # to_table   → [rels]
        for r in state.relationships:
            rel_tables_out[r.from_table].append(r)
            rel_tables_in[r.to_table].append(r)

        known_tables = set(state.tables.keys())

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

        # CIRCULAR_FK — delegate to QueryEngine.cycles() (Fix #7)
        cycles_result = _engine.cycles()
        for row in cycles_result.rows:
            # row['path'] is "A → B → C → A"; strip the loop-back for the message
            cycle_str = row['path'].rsplit(' → ', 1)[0]
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

        # ISLAND — use QueryEngine.islands() to avoid rebuilding adjacency (Fix #9)
        islands_result = _engine.islands()
        if islands_result.meta.get('component_count', 0) > 1:
            island_components: dict[str, list[str]] = defaultdict(list)
            for _row in islands_result.rows:
                if _row['is_island'] and _row.get('size', 1) > 1:
                    island_components[_row['component']].append(_row['table'])
            for comp_tables in island_components.values():
                tables_str = ', '.join(sorted(comp_tables))
                add(Finding(
                    code='ISLAND', severity='warning', category='connectivity',
                    message=(f'Island detected: {len(comp_tables)} tables are connected '
                             f'to each other but isolated from the main schema.'),
                    detail=f'Island tables: {tables_str}',
                    fix='Check whether these tables should reference main-schema tables via FK.',
                ))

        # ═══════════════════════════════════════
        # MIGRATION-SPECIFIC ANTI-PATTERNS
        # ═══════════════════════════════════════

        # MIGRATION-SPECIFIC — use 'files' parameter when provided; fall back to
        # state.source_files for backward-compatibility (Fix #10).
        _source_files = files if files is not None else state.source_files
        for file_entry in _source_files:
            sql = file_entry.get('sql', '')
            sql_upper = sql.upper()
            filename = file_entry.get('filename', 'unknown')

            # ADD_NOT_NULL_NO_DEFAULT — use module-level compiled pattern (Fix #5)
            for match in _ALTER_ADD_PATTERN.finditer(sql):
                table_name = match.group(1)
                col_name = match.group(2)
                col_def = match.group(3).upper()
                
                if 'NOT NULL' in col_def and 'DEFAULT' not in col_def:
                    full_table = next((f for f in state.tables if state.tables[f].name.upper() == table_name.upper()), table_name)
                    add(Finding(
                        code='ADD_NOT_NULL_NO_DEFAULT',
                        severity='error',
                        category='migrations',
                        table=full_table,
                        column=col_name,
                        message=f'{filename}: Adding NOT NULL column {col_name} without DEFAULT value.',
                        detail='This will fail if the table already contains data.',
                        fix=f'Add DEFAULT clause: ADD ({col_name} <type> DEFAULT <value> NOT NULL)',
                    ))

            # SELECT_STAR_VIEW
            if 'CREATE VIEW' in sql_upper and 'SELECT *' in sql_upper:
                match = _VIEW_PATTERN.search(sql)
                if match:
                    view_name = match.group(1)
                    add(Finding(
                        code='SELECT_STAR_VIEW',
                        severity='warning',
                        category='migrations',
                        message=f'{filename}: View {view_name} uses SELECT * pattern.',
                        detail='Views with SELECT * break when source table columns change.',
                        fix=f'Explicitly list columns in CREATE VIEW {view_name} definition.',
                    ))

            # TRIGGER_WITH_BUSINESS_LOGIC
            if 'CREATE TRIGGER' in sql_upper or 'CREATE OR REPLACE TRIGGER' in sql_upper:
                if ('IF ' in sql_upper or 'CASE ' in sql_upper) and len(sql) > 500:
                    match = _TRIGGER_PATTERN.search(sql)
                    if match:
                        trigger_name = match.group(1)
                        add(Finding(
                            code='TRIGGER_WITH_BUSINESS_LOGIC',
                            severity='warning',
                            category='migrations',
                            message=f'{filename}: Trigger {trigger_name} contains complex business logic.',
                            detail='Triggers with business logic are hard to test, debug, and maintain.',
                            fix='Consider moving business logic to application layer or stored procedures.',
                        ))

            # LARGE_DELETE_NO_WHERE
            for match in _DELETE_PATTERN.finditer(sql):
                table_name = match.group(1)
                # Skip if this is part of a longer statement (might have WHERE later)
                remaining = sql[match.end():match.end()+100].upper()
                if 'WHERE' not in remaining:
                    full_table = next((f for f in state.tables if state.tables[f].name.upper() == table_name.upper()), table_name)
                    add(Finding(
                        code='LARGE_DELETE_NO_WHERE',
                        severity='warning',
                        category='migrations',
                        table=full_table,
                        message=f'{filename}: DELETE FROM {table_name} without WHERE clause.',
                        detail='This will delete all rows from the table.',
                        fix='Add WHERE clause to limit deletion, or use TRUNCATE if intentional.',
                    ))

        # ═══════════════════════════════════════
        # GOD TABLES
        # ═══════════════════════════════════════

        report.god_tables = _detect_god_tables(state, communities=communities)
        for g in report.god_tables:
            tag = f'  [{g.community_label}]' if g.community_label else ''
            add(Finding(
                code='GOD_TABLE', severity='info', category='connectivity',
                table=g.table_name,
                message=f'Table {g.table_name} is a god table (degree={g.degree}).{tag}',
                detail=f'Total FK edges: in={g.in_degree} out={g.out_degree}',
                fix='Consider splitting this table or reviewing its excessive coupling.',
            ))

        # ═══════════════════════════════════════
        # SURPRISING CROSS-DOMAIN JOINS
        # ═══════════════════════════════════════

        report.surprising_joins = _detect_surprising_joins(state, communities=communities)
        for s in report.surprising_joins:
            add(Finding(
                code='SURPRISING_JOIN', severity='info', category='connectivity',
                message=f'{s.from_table}.{s.via_column} → {s.to_table} '
                        f'(surprise={s.surprise_score:.2f})',
                detail='Cross-community FK edge — verify this coupling is intentional.',
                fix='Consider whether these tables belong to the same domain.',
            ))

        # Sort: errors first, then warnings, then info; within severity by table name
        sev_order = {'error': 0, 'warning': 1, 'info': 2}
        report.findings.sort(key=lambda f: (sev_order[f.severity], f.table or '', f.code))

        return report