"""
sqlfy.chunker
=============
Build LLM-optimized vector chunks from schema graphs.

Converts SchemaGraph into semantic chunks for RAG/embedding-based retrieval.
"""

from __future__ import annotations

from ..domain.models import SchemaGraph, VectorChunk, Column, Table, Edge
from ..domain.utils import type_str as _type_str


def build_chunks(graph: SchemaGraph) -> list[VectorChunk]:
    """Build LLM-optimized chunks from schema graph.
    
    Args:
        graph: SchemaGraph from apply_migrations()
    
    Returns:
        List of VectorChunk objects ready for embedding/retrieval
    """
    tables   = graph.tables
    seqs     = graph.seqs
    edges    = graph.edges
    mig_hist = graph.mig_hist

    chunks: list[VectorChunk] = []

    def out_e(full: str) -> list[Edge]:
        return [e for e in edges if e.from_table == full]
    
    def in_e(full: str) -> list[Edge]:
        return [e for e in edges if e.to_table == full]

    # Build table chunks
    for t in tables.values():
        pk    = next((c for c in t.constraints if c.type == 'primary_key'), None)
        fks   = [c for c in t.constraints if c.type == 'foreign_key']
        uqs   = [c for c in t.constraints if c.type == 'unique']
        cks   = [c for c in t.constraints if c.type == 'check']
        out   = out_e(t.full)
        inn   = in_e(t.full)

        L: list[str] = []
        L.append(f'TABLE: {t.full}')
        if t.comments.get('__table__'):
            L.append(f'Description: {t.comments["__table__"]}')
        modified = f' | Modified: V{", V".join(t.modified_in)}' if t.modified_in else ''
        L.append(f'Schema: {t.schema or "default"} | Created: V{t.created_in}{modified}')
        L.append(''); L.append('COLUMNS:')

        for col in t.columns:
            flags: list[str] = []
            if pk and col.name in pk.columns:      flags.append('PK')
            if not col.nullable:                   flags.append('NOT NULL')
            if col.default:                        flags.append(f'DEFAULT {col.default}')
            if any(col.name in u.columns for u in uqs): flags.append('UNIQUE')
            if any(col.name in e.from_cols for e in out): flags.append('FK')
            comment  = t.comments.get(col.name, '')
            flag_str = f' [{", ".join(flags)}]' if flags else ''
            cmt_str  = f' -- {comment}' if comment else ''
            L.append(f'  {col.name}: {_type_str(col)}{flag_str}{cmt_str}')

        if out:
            L.append(''); L.append('REFERENCES (outgoing FK):')
            for e in out:
                od = f' ON DELETE {e.on_delete}' if e.on_delete else ''
                cn = f' [{e.constraint_name}]' if e.constraint_name else ''
                L.append(f'  {",".join(e.from_cols)} → {e.to_table}({",".join(e.to_cols)}){od}{cn}')
        if inn:
            L.append(''); L.append('REFERENCED BY:')
            for e in inn:
                L.append(f'  {e.from_table}.{",".join(e.from_cols)} → {",".join(e.to_cols)}')
        if t.indexes:
            L.append(''); L.append('INDEXES:')
            for idx in t.indexes:
                unique_str = "  UNIQUE" if idx.unique else ""
                L.append(f'  {idx.name}: ({", ".join(idx.columns)}){unique_str} [V{idx.created_in}]')
        if cks:
            L.append(''); L.append('CHECK CONSTRAINTS:')
            for ck in cks:
                L.append(f'  {ck.name or "unnamed"}: CHECK ({ck.check_expr})')

        # Action history for this table
        if t.actions:
            L.append(''); L.append('MIGRATION ACTIONS:')
            for a in t.actions:
                L.append(f'  V{a.version}: {a.action} {a.object_type} {a.object_name}')

        chunks.append(VectorChunk(
            id=f'table:{t.full}',
            type='table',
            title=f'Table: {t.name}',
            content='\n'.join(L),
            meta={
                'table_name': t.name,
                'schema': t.schema,
                'column_count': len(t.columns),
                'has_pk': pk is not None,
                'fk_count': len(fks),
                'referenced_by': len(inn),
                'index_count': len(t.indexes),
                'created_in': t.created_in,
                'pk_cols': pk.columns if pk else [],
                'actions': [{'action': a.action, 'version': a.version} for a in t.actions],
            },
            hint=f'Use for: queries about {t.name} table — columns, types, constraints, FK relationships.',
        ))

    # Schema summary chunk
    table_names = list(tables.keys())
    total_cols  = sum(len(t.columns) for t in tables.values())
    schemas     = list({t.schema for t in tables.values() if t.schema})
    
    sum_l = [
        'SCHEMA SUMMARY',
        f'DB Schemas: {", ".join(schemas)}',
        f'Tables: {len(table_names)} ({", ".join(table_names)})',
        f'Sequences: {len(seqs)} ({", ".join(seqs.keys())})',
        f'Total columns: {total_cols}',
        f'FK relationships: {len(edges)}',
        f'Migration history: {" → ".join(f"V{m.version} ({m.description})" for m in mig_hist)}',
        '',
        'RELATIONSHIP MAP:',
        *[f'  {e.from_table}.{",".join(e.from_cols)} → {e.to_table}.{",".join(e.to_cols)}'
          for e in edges],
        '',
        'TABLE ROLES:',
    ]
    
    # Determine table roles
    for t in tables.values():
        in_count = len(in_e(t.full))
        out_count = len(out_e(t.full))
        
        if in_count > 0 and out_count == 0:
            role = "root/parent entity"
        elif out_count > 0 and in_count > 0:
            role = "junction/child entity"
        elif out_count > 0:
            role = "leaf/detail entity"
        else:
            role = "standalone"
        
        sum_l.append(
            f'  {t.full}: {role} '
            f'(referenced by {in_count}, references {out_count})'
        )
    
    chunks.insert(0, VectorChunk(
        id='schema:summary',
        type='schema_summary',
        title='Schema Summary',
        content='\n'.join(sum_l),
        meta={
            'table_count': len(tables),
            'seq_count': len(seqs),
            'edge_count': len(edges),
            'column_count': total_cols,
            'schemas': schemas,
        },
        hint='Use for: high-level schema questions, table count, migration history, overall topology.',
    ))

    # Relationship graph chunk
    rel_l = ['RELATIONSHIP GRAPH (adjacency list)', '']
    for tname in table_names:
        out = out_e(tname)
        inn = in_e(tname)
        rel_l.append(f'{tname}:')
        for e in out:
            on_delete_str = f'  [ON DELETE {e.on_delete}]' if e.on_delete else ''
            rel_l.append(f'  ──FK──▶ {e.to_table} via {",".join(e.from_cols)}{on_delete_str}')
        for e in inn:
            rel_l.append(f'  ◀──FK── {e.from_table} via {",".join(e.from_cols)}')
        if not out and not inn:
            rel_l.append('  (no FK relationships)')
    
    chunks.append(VectorChunk(
        id='schema:relationships',
        type='relationship_map',
        title='Relationship Graph',
        content='\n'.join(rel_l),
        meta={
            'edges': [
                {
                    'from': e.from_table,
                    'to': e.to_table,
                    'via': e.from_cols,
                    'on_delete': e.on_delete
                }
                for e in edges
            ]
        },
        hint='Use for: JOIN path planning, cascade analysis, understanding table connectivity.',
    ))

    return chunks
