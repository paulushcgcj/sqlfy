"""
sqlfy.grapher
=============
Graph representation generator.

Produces two formats from a SchemaState:
  - Graphviz DOT   → render with `dot -Tsvg out.dot -o out.svg`
  - Mermaid ERD    → paste into any Mermaid renderer

Both formats capture:
  - Tables as nodes (with columns, types, PK/FK badges)
  - FK relationships as edges (with ON DELETE annotation)
  - Orphan tables visually separated from the connected cluster
  - Sequences noted in DOT subgraph

Usage
-----
    from cli.grapher import Grapher

    state = SchemaStateBuilder.from_graph(reconstruct(files))

    dot     = Grapher.to_dot(state)
    mermaid = Grapher.to_mermaid(state)
"""

from __future__ import annotations

from ..domain.schema_state import SchemaState, TableState


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _dot_id(full_name: str) -> str:
    """Safe DOT node identifier — strip dots and special chars."""
    return full_name.replace('.', '_').replace('-', '_')


def _mermaid_id(full_name: str) -> str:
    """Safe Mermaid entity identifier."""
    return full_name.replace('.', '_').replace('-', '_')


def _col_badge(col) -> str:
    """One-letter badges for DOT column rows."""
    badges = []
    if col.is_pk:     badges.append('PK')
    if col.is_fk:     badges.append('FK')
    if col.is_unique: badges.append('UQ')
    return ','.join(badges)


def _html_escape(s: str) -> str:
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


# ─────────────────────────────────────────────
# GRAPHER
# ─────────────────────────────────────────────

class Grapher:

    # ── DOT output ──────────────────────────────────────────────────────

    @staticmethod
    def to_dot(state: SchemaState, title: str = '') -> str:
        """
        Produce a Graphviz DOT graph from a SchemaState.

        Render with:
            dot -Tsvg schema.dot -o schema.svg
            dot -Tpng schema.dot -o schema.png
            dot -Tpdf schema.dot -o schema.pdf
        """
        rel_tables = {r.from_table for r in state.relationships} | \
                     {r.to_table   for r in state.relationships}
        orphans    = [t for t in state.tables.values() if t.full_name not in rel_tables]
        connected  = [t for t in state.tables.values() if t.full_name in rel_tables]

        lines = [
            f'// sqlfy schema graph — V{state.version}  fingerprint={state.fingerprint}',
            f'digraph schema {{',
            f'  graph [',
            f'    label="{_html_escape(title or f"Schema V{state.version}")}",',
            f'    labelloc=t, fontname="Helvetica", fontsize=14,',
            f'    rankdir=TB, splines=ortho, nodesep=0.6, ranksep=0.9,',
            f'    bgcolor="#f8f8f8"',
            f'  ]',
            f'  node  [shape=none, margin=0, fontname="Helvetica", fontsize=11]',
            f'  edge  [fontname="Helvetica", fontsize=9, color="#d97706", arrowhead=vee]',
            '',
        ]

        def table_node(t: TableState, bg: str = '#ffffff') -> list[str]:
            tid = _dot_id(t.full_name)
            rows = []
            # Header row
            comment_title = f' — {_html_escape(t.comment)}' if t.comment else ''
            rows.append(
                f'    <TR><TD COLSPAN="3" BGCOLOR="#ede9fe" BORDER="0" ALIGN="LEFT">'
                f'<B>{_html_escape(t.full_name)}</B>'
                f'<FONT COLOR="#9ca3af">{_html_escape(comment_title)}</FONT>'
                f'</TD></TR>'
            )
            rows.append(
                f'    <TR>'
                f'<TD BORDER="0" BGCOLOR="#f3f0ff"><FONT COLOR="#7c3aed" POINT-SIZE="9">COLUMN</FONT></TD>'
                f'<TD BORDER="0" BGCOLOR="#f3f0ff"><FONT COLOR="#7c3aed" POINT-SIZE="9">TYPE</FONT></TD>'
                f'<TD BORDER="0" BGCOLOR="#f3f0ff"><FONT COLOR="#7c3aed" POINT-SIZE="9">FLAGS</FONT></TD>'
                f'</TR>'
            )
            for col in t.columns:
                badge     = _col_badge(col)
                badge_col = '#7c3aed' if 'PK' in badge else ('#d97706' if 'FK' in badge else '#6b7280')
                nn_mark   = ' <FONT COLOR="#dc2626">*</FONT>' if not col.nullable else ''
                rows.append(
                    f'    <TR>'
                    f'<TD BORDER="0" ALIGN="LEFT">{_html_escape(col.name)}{nn_mark}</TD>'
                    f'<TD BORDER="0" ALIGN="LEFT"><FONT COLOR="#0891b2">{_html_escape(col.data_type)}</FONT></TD>'
                    f'<TD BORDER="0" ALIGN="LEFT"><FONT COLOR="{badge_col}" POINT-SIZE="9">{badge}</FONT></TD>'
                    f'</TR>'
                )
            node = [
                f'  {tid} [label=<',
                f'    <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" BGCOLOR="{bg}" COLOR="#d1d5db">',
            ]
            node.extend(rows)
            node.append(f'    </TABLE>>]')
            return node

        # Connected tables
        if connected:
            lines.append('  subgraph cluster_connected {')
            lines.append('    label="" style=invis')
            for t in connected:
                lines.extend(table_node(t, bg='#ffffff'))
            lines.append('  }')
            lines.append('')

        # Orphan tables
        if orphans:
            lines.append('  subgraph cluster_orphans {')
            lines.append('    label="Orphan tables (no FK)" style=dashed color="#e5e7eb" fontcolor="#9ca3af" fontsize=10')
            for t in orphans:
                lines.extend(table_node(t, bg='#fafafa'))
            lines.append('  }')
            lines.append('')

        # Sequences
        if state.sequences:
            lines.append('  subgraph cluster_sequences {')
            lines.append('    label="Sequences" style=dashed color="#d1fae5" fontcolor="#059669" fontsize=10')
            lines.append('    node [shape=note style=filled fillcolor="#f0fdf4" color="#059669" fontsize=10]')
            for s in state.sequences.values():
                sid = _dot_id(s.full_name)
                lines.append(f'    {sid} [label="{_html_escape(s.full_name)}\\nSTART {s.start_with} INC {s.increment_by}"]')
            lines.append('  }')
            lines.append('')

        # Edges
        for rel in state.relationships:
            fid = _dot_id(rel.from_table)
            tid = _dot_id(rel.to_table)
            from_cols = ', '.join(rel.from_columns)
            to_cols   = ', '.join(rel.to_columns)
            od_label  = f'\\nON DELETE {rel.on_delete}' if rel.on_delete else ''
            con_label = rel.constraint_name or ''
            label     = _html_escape(f'{from_cols} → {to_cols}{od_label}')
            lines.append(
                f'  {fid} -> {tid} ['
                f'label="{label}", '
                f'tooltip="{_html_escape(con_label)}", '
                f'penwidth=1.2]'
            )

        lines.append('}')
        return '\n'.join(lines)

    # ── Mermaid output ──────────────────────────────────────────────────

    @staticmethod
    def to_mermaid(state: SchemaState, title: str = '') -> str:
        """
        Produce a Mermaid ERD diagram from a SchemaState.

        Paste into:
          - Any Markdown file (GitHub, GitLab, Notion, Obsidian)
          - https://mermaid.live
          - VSCode Mermaid Preview extension
        """
        rel_tables = {r.from_table for r in state.relationships} | \
                     {r.to_table   for r in state.relationships}
        orphans    = [t for t in state.tables.values() if t.full_name not in rel_tables]
        connected  = [t for t in state.tables.values() if t.full_name in rel_tables]

        lines: list[str] = []

        if title:
            lines.append(f'---')
            lines.append(f'title: {title}')
            lines.append(f'---')

        lines.append('erDiagram')
        lines.append(f'  %% sqlfy schema graph — V{state.version}  fp={state.fingerprint}')
        lines.append('')

        def mermaid_type(data_type: str) -> str:
            """Mermaid only allows simple type identifiers — strip parens."""
            import re
            return re.sub(r'\(.*\)', '', data_type).replace(' ', '_').upper()

        def table_block(t: TableState, comment: str = '') -> list[str]:
            mid = _mermaid_id(t.full_name)
            block = []
            if comment:
                block.append(f'  %% {comment}')
            block.append(f'  {mid} {{')
            for col in t.columns:
                badges: list[str] = []
                if col.is_pk: badges.append('PK')
                if col.is_fk: badges.append('FK')
                if col.is_unique: badges.append('UK')
                badge_str  = ' '.join(badges)
                comment_str = f'"{col.comment}"' if col.comment else ''
                nn          = '' if col.nullable else '~NN~'  # Mermaid doesn't have NN — use comment
                parts = [mermaid_type(col.data_type), col.name]
                if badge_str:  parts.append(badge_str)
                if comment_str: parts.append(comment_str)
                block.append(f'    {" ".join(parts)}')
            block.append(f'  }}')
            return block

        # Connected tables
        if connected:
            lines.append('  %% ── Connected tables ──────────────────────')
            for t in connected:
                lines.extend(table_block(t, comment=t.comment or ''))
                lines.append('')

        # Orphan tables
        if orphans:
            lines.append('  %% ── Orphan tables (no FK relationships) ───')
            for t in orphans:
                lines.extend(table_block(t, comment=f'ORPHAN — {t.comment or "no FK"}'))
                lines.append('')

        # Relationships
        if state.relationships:
            lines.append('  %% ── Relationships ─────────────────────────')
        for rel in state.relationships:
            fid = _mermaid_id(rel.from_table)
            tid = _mermaid_id(rel.to_table)
            # Cardinality notation
            if rel.cardinality == 'one_to_one':
                card = '||--||'
            else:
                card = '}o--||'   # many-to-one (child FK → parent PK)
            from_cols = ', '.join(rel.from_columns)
            to_cols   = ', '.join(rel.to_columns)
            od        = f' ON DELETE {rel.on_delete}' if rel.on_delete else ''
            label     = f'{from_cols} -> {to_cols}{od}'
            lines.append(f'  {fid} {card} {tid} : "{label}"')

        return '\n'.join(lines)

    # ── Summary text ────────────────────────────────────────────────────

    @staticmethod
    def to_summary(state: SchemaState) -> str:
        """
        Compact ASCII adjacency-list representation.
        Useful for pasting into LLM prompts or commit messages.
        """
        rel_tables = {r.from_table for r in state.relationships} | \
                     {r.to_table   for r in state.relationships}
        orphans    = {t.full_name for t in state.tables.values() if t.full_name not in rel_tables}

        lines: list[str] = [
            f'Schema graph — V{state.version}  ({len(state.tables)} tables, {len(state.relationships)} FK edges)',
            '',
        ]

        # Adjacency list
        for t in state.tables.values():
            out = [r for r in state.relationships if r.from_table == t.full_name]
            inn = [r for r in state.relationships if r.to_table   == t.full_name]
            orphan_tag = '  [orphan]' if t.full_name in orphans else ''
            lines.append(f'{t.full_name}{orphan_tag}')
            for r in out:
                od = f' ON DELETE {r.on_delete}' if r.on_delete else ''
                lines.append(f'  ──FK──▶  {r.to_table} via {r.from_columns}{od}')
            for r in inn:
                lines.append(f'  ◀──FK──  {r.from_table} via {r.from_columns}')
            if not out and not inn:
                lines.append('  (no FK relationships)')

        return '\n'.join(lines)