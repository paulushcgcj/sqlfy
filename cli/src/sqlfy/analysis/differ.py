"""
sqlfy.differ
============
Schema State Differ.

Compares two SchemaState snapshots and produces a structured diff
describing every addition, removal, and modification between them.

Diff categories
---------------
  tables_added       Tables present in B but not A
  tables_removed     Tables present in A but not B
  tables_modified    Tables present in both, with column/constraint/index changes
  sequences_added    Sequences present in B but not A
  sequences_removed  Sequences present in A but not B
  relationships_added    FK edges in B but not A
  relationships_removed  FK edges in A but not B

For modified tables, per-column changes are classified as:
  column_added     Column present in B but not A
  column_removed   Column present in A but not B
  column_modified  Column present in both, with type/nullability/default changes

Usage
-----
    from cli.schema_state import SchemaStateBuilder
    from cli.differ import SchemaDiffer, DiffResult

    state_a = SchemaStateBuilder.from_graph(reconstruct(files_v1))
    state_b = SchemaStateBuilder.from_graph(reconstruct(files_v2))

    result = SchemaDiffer.diff(state_a, state_b)

    print(result.to_text())      # human-readable
    print(result.to_json())      # machine-readable
    print(result.is_breaking())  # True if any removal or incompatible modification
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from ..domain.schema_state import (
    SchemaState, TableState, ColumnState,
    ConstraintState, IndexState, SequenceState, RelationshipState, MigrationStep,
)


# ─────────────────────────────────────────────
# CHANGE PRIMITIVES
# ─────────────────────────────────────────────

@dataclass
class ColumnChange:
    name:       str
    change:     str        # added | removed | modified
    before:     Optional[dict] = None   # None for added
    after:      Optional[dict] = None   # None for removed
    field_diffs: list[str] = field(default_factory=list)  # e.g. ["type: NUMBER→VARCHAR"]

    def is_breaking(self) -> bool:
        """True if this change could break existing queries/code."""
        if self.change == 'removed':
            return True
        if self.change == 'modified':
            # Type change or nullable→not-null is potentially breaking
            return any(
                'type' in d or 'nullable: True→False' in d
                for d in self.field_diffs
            )
        return False


@dataclass
class ConstraintChange:
    name:   Optional[str]
    change: str            # added | removed
    type:   str
    columns: list[str]


@dataclass
class IndexChange:
    name:   str
    change: str            # added | removed
    columns: list[str]
    unique: bool


@dataclass
class TableChange:
    full_name:         str
    change:            str   # added | removed | modified
    column_changes:    list[ColumnChange]    = field(default_factory=list)
    constraint_changes: list[ConstraintChange] = field(default_factory=list)
    index_changes:     list[IndexChange]     = field(default_factory=list)
    comment_changed:   bool                  = False
    comment_before:    Optional[str]         = None
    comment_after:     Optional[str]         = None

    def is_breaking(self) -> bool:
        if self.change == 'removed':
            return True
        return any(c.is_breaking() for c in self.column_changes)

    def is_empty(self) -> bool:
        """True if no actual changes despite being in 'modified' bucket."""
        return (not self.column_changes and not self.constraint_changes
                and not self.index_changes and not self.comment_changed)


@dataclass
class RelationshipChange:
    id:     str
    change: str   # added | removed
    from_table:   str
    from_columns: list[str]
    to_table:     str
    to_columns:   list[str]
    on_delete:    Optional[str]


@dataclass
class SequenceChange:
    full_name: str
    change:    str    # added | removed | modified
    field_diffs: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────
# DIFF RESULT
# ─────────────────────────────────────────────

@dataclass
class DiffResult:
    version_a:     str
    version_b:     str
    fingerprint_a: str
    fingerprint_b: str

    table_changes:        list[TableChange]       = field(default_factory=list)
    sequence_changes:     list[SequenceChange]    = field(default_factory=list)
    relationship_changes: list[RelationshipChange] = field(default_factory=list)

    # ── Summary helpers ──────────────────────────────────────────────────

    def tables_added(self)    -> list[TableChange]:
        return [c for c in self.table_changes if c.change == 'added']

    def tables_removed(self)  -> list[TableChange]:
        return [c for c in self.table_changes if c.change == 'removed']

    def tables_modified(self) -> list[TableChange]:
        return [c for c in self.table_changes if c.change == 'modified']

    def is_breaking(self) -> bool:
        return any(c.is_breaking() for c in self.table_changes)

    def is_empty(self) -> bool:
        return (not self.table_changes and not self.sequence_changes
                and not self.relationship_changes)

    def stats(self) -> dict:
        col_adds = col_removes = col_mods = 0
        for tc in self.tables_modified():
            for cc in tc.column_changes:
                if cc.change == 'added':   col_adds    += 1
                elif cc.change == 'removed': col_removes += 1
                else:                      col_mods    += 1
        return {
            'tables_added':        len(self.tables_added()),
            'tables_removed':      len(self.tables_removed()),
            'tables_modified':     len(self.tables_modified()),
            'columns_added':       col_adds,
            'columns_removed':     col_removes,
            'columns_modified':    col_mods,
            'sequences_added':     sum(1 for s in self.sequence_changes if s.change == 'added'),
            'sequences_removed':   sum(1 for s in self.sequence_changes if s.change == 'removed'),
            'relationships_added': sum(1 for r in self.relationship_changes if r.change == 'added'),
            'relationships_removed': sum(1 for r in self.relationship_changes if r.change == 'removed'),
            'is_breaking':         self.is_breaking(),
        }

    # ── Serialisation ────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        def col_change_d(c: ColumnChange) -> dict:
            d: dict = {'name': c.name, 'change': c.change}
            if c.before:      d['before'] = c.before
            if c.after:       d['after']  = c.after
            if c.field_diffs: d['diffs']  = c.field_diffs
            d['breaking'] = c.is_breaking()
            return d

        def con_change_d(c: ConstraintChange) -> dict:
            return {'name': c.name, 'change': c.change, 'type': c.type, 'columns': c.columns}

        def idx_change_d(i: IndexChange) -> dict:
            return {'name': i.name, 'change': i.change, 'columns': i.columns, 'unique': i.unique}

        def tbl_change_d(t: TableChange) -> dict:
            d: dict = {'full_name': t.full_name, 'change': t.change, 'breaking': t.is_breaking()}
            if t.column_changes:    d['column_changes']    = [col_change_d(c) for c in t.column_changes]
            if t.constraint_changes: d['constraint_changes'] = [con_change_d(c) for c in t.constraint_changes]
            if t.index_changes:     d['index_changes']     = [idx_change_d(i) for i in t.index_changes]
            if t.comment_changed:
                d['comment'] = {'before': t.comment_before, 'after': t.comment_after}
            return d

        def rel_change_d(r: RelationshipChange) -> dict:
            return {'change': r.change, 'from': r.from_table, 'from_cols': r.from_columns,
                    'to': r.to_table, 'to_cols': r.to_columns, 'on_delete': r.on_delete}

        def seq_change_d(s: SequenceChange) -> dict:
            d: dict = {'full_name': s.full_name, 'change': s.change}
            if s.field_diffs: d['diffs'] = s.field_diffs
            return d

        return {
            'version_a':     self.version_a,
            'version_b':     self.version_b,
            'fingerprint_a': self.fingerprint_a,
            'fingerprint_b': self.fingerprint_b,
            'stats':         self.stats(),
            'table_changes':        [tbl_change_d(t) for t in self.table_changes],
            'sequence_changes':     [seq_change_d(s) for s in self.sequence_changes],
            'relationship_changes': [rel_change_d(r) for r in self.relationship_changes],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_text(self) -> str:
        lines: list[str] = []
        a = lines.append

        st = self.stats()
        breaking = '⚠  BREAKING CHANGES DETECTED' if st['is_breaking'] else '✓  No breaking changes'

        a('\n╔══════════════════════════════════════════╗')
        a('║          SCHEMA STATE DIFF               ║')
        a('╚══════════════════════════════════════════╝\n')
        a(f'  A → B   V{self.version_a} ({self.fingerprint_a}) → V{self.version_b} ({self.fingerprint_b})')
        a(f'  {breaking}\n')
        a('  Summary:')
        for k, v in st.items():
            if k != 'is_breaking' and v:
                a(f'    {k:<28} {v}')

        # ── Tables ─────────────────────────────────────────────────────
        if self.tables_added():
            a('\n  ✚ TABLES ADDED:')
            for t in self.tables_added():
                a(f'    + {t.full_name}')

        if self.tables_removed():
            a('\n  ✖ TABLES REMOVED:')
            for t in self.tables_removed():
                brk = '  ⚠ BREAKING' if t.is_breaking() else ''
                a(f'    - {t.full_name}{brk}')

        if self.tables_modified():
            a('\n  ✎ TABLES MODIFIED:')
            for t in self.tables_modified():
                brk = '  ⚠' if t.is_breaking() else ''
                a(f'\n    ┌─ {t.full_name}{brk}')
                if t.comment_changed:
                    a(f'    │  comment:  "{t.comment_before}" → "{t.comment_after}"')
                for cc in t.column_changes:
                    sym = '+' if cc.change == 'added' else ('-' if cc.change == 'removed' else '~')
                    brk2 = '  ⚠' if cc.is_breaking() else ''
                    if cc.change == 'modified':
                        a(f'    │  {sym} {cc.name}:  {", ".join(cc.field_diffs)}{brk2}')
                    else:
                        detail = cc.after if cc.change == 'added' else cc.before
                        dt = detail.get('data_type', '') if detail else ''
                        a(f'    │  {sym} {cc.name}  {dt}{brk2}')
                for con in t.constraint_changes:
                    sym = '+' if con.change == 'added' else '-'
                    a(f'    │  {sym} CONSTRAINT {con.name or "unnamed"} ({con.type}) on ({", ".join(con.columns)})')
                for idx in t.index_changes:
                    sym = '+' if idx.change == 'added' else '-'
                    uq = ' UNIQUE' if idx.unique else ''
                    a(f'    │  {sym} INDEX {idx.name} ({", ".join(idx.columns)}){uq}')
                a(f'    └{"─" * 44}')

        # ── Sequences ──────────────────────────────────────────────────
        seq_added   = [s for s in self.sequence_changes if s.change == 'added']
        seq_removed = [s for s in self.sequence_changes if s.change == 'removed']
        seq_modified = [s for s in self.sequence_changes if s.change == 'modified']
        if seq_added:
            a('\n  ✚ SEQUENCES ADDED:')
            for s in seq_added: a(f'    + {s.full_name}')
        if seq_removed:
            a('\n  ✖ SEQUENCES REMOVED:')
            for s in seq_removed: a(f'    - {s.full_name}')
        if seq_modified:
            a('\n  ✎ SEQUENCES MODIFIED:')
            for s in seq_modified: a(f'    ~ {s.full_name}:  {", ".join(s.field_diffs)}')

        # ── Relationships ──────────────────────────────────────────────
        rel_added   = [r for r in self.relationship_changes if r.change == 'added']
        rel_removed = [r for r in self.relationship_changes if r.change == 'removed']
        if rel_added:
            a('\n  ✚ RELATIONSHIPS ADDED:')
            for r in rel_added:
                a(f'    + {r.from_table}.{r.from_columns} → {r.to_table}.{r.to_columns}')
        if rel_removed:
            a('\n  ✖ RELATIONSHIPS REMOVED:')
            for r in rel_removed:
                a(f'    - {r.from_table}.{r.from_columns} → {r.to_table}.{r.to_columns}')

        if self.is_empty():
            a('\n  (no changes detected)')

        a('')
        return '\n'.join(lines)


# ─────────────────────────────────────────────
# DIFFER
# ─────────────────────────────────────────────

class SchemaDiffer:
    """Stateless differ — call SchemaDiffer.diff(state_a, state_b)."""

    @staticmethod
    def diff(state_a: SchemaState, state_b: SchemaState) -> DiffResult:
        result = DiffResult(
            version_a=state_a.version,
            version_b=state_b.version,
            fingerprint_a=state_a.fingerprint,
            fingerprint_b=state_b.fingerprint,
        )

        # ── Tables ─────────────────────────────────────────────────────
        keys_a = set(state_a.tables.keys())
        keys_b = set(state_b.tables.keys())

        for key in sorted(keys_b - keys_a):
            result.table_changes.append(TableChange(full_name=key, change='added'))

        for key in sorted(keys_a - keys_b):
            result.table_changes.append(TableChange(full_name=key, change='removed'))

        for key in sorted(keys_a & keys_b):
            tc = SchemaDiffer._diff_table(state_a.tables[key], state_b.tables[key])
            if not tc.is_empty():
                result.table_changes.append(tc)

        # ── Sequences ──────────────────────────────────────────────────
        seqs_a = set(state_a.sequences.keys())
        seqs_b = set(state_b.sequences.keys())

        for key in sorted(seqs_b - seqs_a):
            result.sequence_changes.append(SequenceChange(full_name=key, change='added'))

        for key in sorted(seqs_a - seqs_b):
            result.sequence_changes.append(SequenceChange(full_name=key, change='removed'))

        for key in sorted(seqs_a & seqs_b):
            sa, sb = state_a.sequences[key], state_b.sequences[key]
            diffs: list[str] = []
            if sa.start_with   != sb.start_with:   diffs.append(f'start_with: {sa.start_with}→{sb.start_with}')
            if sa.increment_by != sb.increment_by: diffs.append(f'increment_by: {sa.increment_by}→{sb.increment_by}')
            if diffs:
                result.sequence_changes.append(SequenceChange(full_name=key, change='modified', field_diffs=diffs))

        # ── Relationships ──────────────────────────────────────────────
        rels_a = {r.id: r for r in state_a.relationships}
        rels_b = {r.id: r for r in state_b.relationships}

        for rid in sorted(set(rels_b) - set(rels_a)):
            r = rels_b[rid]
            result.relationship_changes.append(RelationshipChange(
                id=rid, change='added',
                from_table=r.from_table, from_columns=r.from_columns,
                to_table=r.to_table, to_columns=r.to_columns, on_delete=r.on_delete,
            ))

        for rid in sorted(set(rels_a) - set(rels_b)):
            r = rels_a[rid]
            result.relationship_changes.append(RelationshipChange(
                id=rid, change='removed',
                from_table=r.from_table, from_columns=r.from_columns,
                to_table=r.to_table, to_columns=r.to_columns, on_delete=r.on_delete,
            ))

        return result

    # ── Table-level diff ────────────────────────────────────────────────

    @staticmethod
    def _diff_table(ta: TableState, tb: TableState) -> TableChange:
        tc = TableChange(full_name=ta.full_name, change='modified')

        # Comment
        if ta.comment != tb.comment:
            tc.comment_changed = True
            tc.comment_before  = ta.comment
            tc.comment_after   = tb.comment

        # Columns
        cols_a = {c.name: c for c in ta.columns}
        cols_b = {c.name: c for c in tb.columns}

        for name in sorted(set(cols_b) - set(cols_a)):
            col = cols_b[name]
            tc.column_changes.append(ColumnChange(
                name=name, change='added',
                after=SchemaDiffer._col_dict(col),
            ))

        for name in sorted(set(cols_a) - set(cols_b)):
            col = cols_a[name]
            tc.column_changes.append(ColumnChange(
                name=name, change='removed',
                before=SchemaDiffer._col_dict(col),
            ))

        for name in sorted(set(cols_a) & set(cols_b)):
            ca, cb = cols_a[name], cols_b[name]
            diffs = SchemaDiffer._diff_column(ca, cb)
            if diffs:
                tc.column_changes.append(ColumnChange(
                    name=name, change='modified',
                    before=SchemaDiffer._col_dict(ca),
                    after=SchemaDiffer._col_dict(cb),
                    field_diffs=diffs,
                ))

        # Constraints
        cons_a = {(c.type, tuple(sorted(c.columns)), c.name): c for c in ta.constraints}
        cons_b = {(c.type, tuple(sorted(c.columns)), c.name): c for c in tb.constraints}

        for key in sorted(set(cons_b) - set(cons_a)):
            c = cons_b[key]
            tc.constraint_changes.append(ConstraintChange(
                name=c.name, change='added', type=c.type, columns=list(c.columns)
            ))

        for key in sorted(set(cons_a) - set(cons_b)):
            c = cons_a[key]
            tc.constraint_changes.append(ConstraintChange(
                name=c.name, change='removed', type=c.type, columns=list(c.columns)
            ))

        # Indexes
        idxs_a = {i.name: i for i in ta.indexes}
        idxs_b = {i.name: i for i in tb.indexes}

        for name in sorted(set(idxs_b) - set(idxs_a)):
            i = idxs_b[name]
            tc.index_changes.append(IndexChange(name=name, change='added', columns=i.columns, unique=i.unique))

        for name in sorted(set(idxs_a) - set(idxs_b)):
            i = idxs_a[name]
            tc.index_changes.append(IndexChange(name=name, change='removed', columns=i.columns, unique=i.unique))

        return tc

    # ── Column-level diff ───────────────────────────────────────────────

    @staticmethod
    def _diff_column(ca: ColumnState, cb: ColumnState) -> list[str]:
        diffs: list[str] = []
        if ca.data_type != cb.data_type:
            diffs.append(f'type: {ca.data_type}→{cb.data_type}')
        if ca.nullable != cb.nullable:
            diffs.append(f'nullable: {ca.nullable}→{cb.nullable}')
        if ca.default != cb.default:
            diffs.append(f'default: {ca.default!r}→{cb.default!r}')
        if ca.is_pk != cb.is_pk:
            diffs.append(f'primary_key: {ca.is_pk}→{cb.is_pk}')
        if ca.is_unique != cb.is_unique:
            diffs.append(f'unique: {ca.is_unique}→{cb.is_unique}')
        if ca.comment != cb.comment:
            diffs.append(f'comment: {ca.comment!r}→{cb.comment!r}')
        return diffs

    @staticmethod
    def _col_dict(c: ColumnState) -> dict:
        return {
            'data_type': c.data_type,
            'nullable':  c.nullable,
            'default':   c.default,
            'is_pk':     c.is_pk,
            'is_fk':     c.is_fk,
            'is_unique': c.is_unique,
            'comment':   c.comment,
        }


# ─────────────────────────────────────────────
# CONVENIENCE — diff two state JSON files
# ─────────────────────────────────────────────

def diff_files(path_a: str, path_b: str) -> DiffResult:
    """
    Load two Schema State JSON files (produced by `sqlfy dump`) and diff them.

    Example:
        result = diff_files('state_v2.json', 'state_v5.json')
        print(result.to_text())
    """
    def load(path: str) -> SchemaState:
        raw = json.loads(Path(path).read_text(encoding='utf-8'))
        tables = {}
        for full, t in raw.get('tables', {}).items():
            columns = [ColumnState(**c) for c in t.get('columns', [])]
            constraints = [ConstraintState(**c) for c in t.get('constraints', [])]
            indexes = [IndexState(**i) for i in t.get('indexes', [])]
            tables[full] = TableState(
                schema=t.get('schema'), name=t['name'], full_name=t['full_name'],
                columns=columns, constraints=constraints, indexes=indexes,
                comment=t.get('comment'), created_in=t.get('created_in', ''),
                modified_in=t.get('modified_in', []),
                column_count=t.get('column_count', len(columns)),
                has_pk=t.get('has_pk', False), pk_columns=t.get('pk_columns', []),
            )
        sequences = {}
        for full, s in raw.get('sequences', {}).items():
            sequences[full] = SequenceState(**s)
        relationships = [
            RelationshipState(**r) for r in raw.get('relationships', [])
        ]
        mig_hist = [MigrationStep(**m) for m in raw.get('migration_history', [])]
        return SchemaState(
            version=raw['version'], generated_at=raw['generated_at'],
            fingerprint=raw['fingerprint'], dialect=raw.get('dialect', 'oracle'),
            tables=tables, sequences=sequences, relationships=relationships,
            migration_history=mig_hist, stats=raw.get('stats', {}),
        )

    return SchemaDiffer.diff(load(path_a), load(path_b))