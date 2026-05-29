"""Shared utilities for sqlfy CLI commands."""

import sys
import json
from pathlib import Path

from ..domain.models import SchemaGraph, VectorChunk
from ..domain.schema_state import type_str
from ..migrations.loader import load_files as _migrations_load_files


def load_files(
    migrations_dir: str | None,
    json_input: str | None,
    use_cache: bool = True,
) -> list[dict]:
    """Load migration files. Delegates to sqlfy.migrations.loader."""
    return _migrations_load_files(migrations_dir, json_input, use_cache=use_cache)



def write_output(content: str, out: str | None) -> None:
    if out:
        Path(out).write_text(content, encoding="utf-8")
        print(f"Output written to {out}", file=sys.stderr)
    else:
        print(content)


def format_human_graph(graph: SchemaGraph) -> str:
    lines: list[str] = []
    a = lines.append
    a("\n╔══════════════════════════════════════════╗")
    a("║          SCHEMA GRAPH — SUMMARY          ║")
    a("╚══════════════════════════════════════════╝\n")
    a("Migration history:")
    for m in graph.mig_hist:
        a(f"  V{m.version}  {m.description}")
    a(f"\nTables ({len(graph.tables)}):")
    for t in graph.tables.values():
        pk = next((c for c in t.constraints if c.type == "primary_key"), None)
        out_e = [e for e in graph.edges if e.from_table == t.full]
        in_e = [e for e in graph.edges if e.to_table == t.full]
        mod = f"  Modified: V{', '.join(t.modified_in)}" if t.modified_in else ""
        a(f"\n  ┌─ {t.full} {'─' * max(0, 42 - len(t.full))}")
        if t.comments.get("__table__"):
            a(f"  │  {t.comments['__table__']}")
        a(f"  │  Created: V{t.created_in}{mod}")
        a("  │  Columns:")
        for col in t.columns:
            flags = []
            if pk and col.name in pk.columns:
                flags.append("PK")
            if not col.nullable:
                flags.append("NN")
            if col.default:
                flags.append(f"DEFAULT {col.default}")
            a(f"  │    {col.name:<24} {type_str(col):<18}  {' '.join(flags)}")
        if out_e:
            a("  │  References:")
            for e in out_e:
                a(f"  │    {','.join(e.from_cols)} → {e.to_table}({','.join(e.to_cols)})")
        if in_e:
            a("  │  Referenced by:")
            for e in in_e:
                a(f"  │    {e.from_table}")
        a(f"  └{'─' * 44}")
    if graph.seqs:
        a(f"\nSequences ({len(graph.seqs)}):")
        for s in graph.seqs.values():
            a(f"  {s.full:<30} START {s.start_with}  INCREMENT {s.increment_by}")
    a(f"\nRelationships ({len(graph.edges)}):")
    for e in graph.edges:
        od = f"  [ON DELETE {e.on_delete}]" if e.on_delete else ""
        a(f"  {e.from_table}.{','.join(e.from_cols)}  →  {e.to_table}.{','.join(e.to_cols)}{od}")
    a("")
    return "\n".join(lines)


def format_human_chunks(chunks: list[VectorChunk]) -> str:
    lines: list[str] = []
    a = lines.append
    a("\n╔══════════════════════════════════════════╗")
    a("║         LLM VECTOR CHUNKS                ║")
    a("╚══════════════════════════════════════════╝\n")
    for chunk in chunks:
        sep = "─" * max(0, 50 - len(chunk.title))
        a(f"━━━ [{chunk.type}] {chunk.title} {sep}")
        a(f"Hint: {chunk.hint}\n")
        a(chunk.content)
        a("\nMetadata:")
        a(json.dumps(chunk.meta, indent=2))
        a("")
    return "\n".join(lines)


def graph_to_dict(graph: SchemaGraph) -> dict:
    def col_d(c):
        return {
            "name": c.name, "type": c.type, "precision": c.precision,
            "scale": c.scale, "nullable": c.nullable, "default": c.default,
            "primary_key": c.primary_key, "unique": c.unique, "references": c.references,
        }

    def con_d(c):
        d = {"name": c.name, "type": c.type, "columns": c.columns}
        if c.references:
            d["references"] = c.references
        if c.check_expr:
            d["check_expr"] = c.check_expr
        return d

    return {
        "migration_history": [{"version": m.version, "description": m.description} for m in graph.mig_hist],
        "tables": {
            k: {
                "id": t.id, "schema": t.schema, "name": t.name, "full": t.full,
                "columns": [col_d(c) for c in t.columns],
                "constraints": [con_d(c) for c in t.constraints],
                "indexes": [
                    {"name": i.name, "columns": i.columns, "unique": i.unique, "created_in": i.created_in}
                    for i in t.indexes
                ],
                "comments": t.comments,
                "created_in": t.created_in,
                "modified_in": t.modified_in,
            }
            for k, t in graph.tables.items()
        },
        "sequences": {
            k: {
                "name": s.name, "schema": s.schema, "full": s.full,
                "start_with": s.start_with, "increment_by": s.increment_by, "created_in": s.created_in,
            }
            for k, s in graph.seqs.items()
        },
        "edges": [
            {
                "id": e.id, "from_table": e.from_table, "from_cols": e.from_cols,
                "to_table": e.to_table, "to_cols": e.to_cols,
                "constraint_name": e.constraint_name, "on_delete": e.on_delete,
            }
            for e in graph.edges
        ],
    }


def chunks_to_list(chunks: list[VectorChunk]) -> list[dict]:
    from ..models import VectorChunk as _VectorChunk
    return [
        json.loads(_VectorChunk(
            id=c.id, type=c.type, title=c.title,
            content=c.content, metadata=c.meta, hint=c.hint,
        ).model_dump_json(by_alias=True))
        for c in chunks
    ]


def format_state_summary(state) -> str:
    """Human-readable summary of the Schema State Dictionary."""
    lines: list[str] = []
    a = lines.append
    a("\n╔══════════════════════════════════════════╗")
    a("║        SCHEMA STATE DICTIONARY           ║")
    a("╚══════════════════════════════════════════╝\n")
    a(f"  Version     : {state.version}")
    a(f"  Fingerprint : {state.fingerprint}")
    a(f"  Generated   : {state.generated_at}")
    a(f"  Dialect     : {state.dialect}")
    a("")
    a("  Stats:")
    for k, v in state.stats.items():
        a(f"    {k:<25} {v}")
    a("\n  Migration history:")
    for m in state.migration_history:
        a(f"    V{m.version:<8} {m.description}")
    a(f"\n  Tables ({len(state.tables)}):")
    for t in state.tables.values():
        mod = f"  modified V{', '.join(t.modified_in)}" if t.modified_in else ""
        a(f"\n    ┌─ {t.full_name}  [created V{t.created_in}{mod}]")
        if t.comment:
            a(f'    │  "{t.comment}"')
        a(f"    │  PK: {t.pk_columns or 'none'}")
        for col in t.columns:
            badges = []
            if col.is_pk:
                badges.append("PK")
            if col.is_fk:
                badges.append("FK")
            if col.is_unique:
                badges.append("UQ")
            if not col.nullable:
                badges.append("NN")
            if col.default:
                badges.append(f"DEFAULT {col.default}")
            badge_str = f"  [{', '.join(badges)}]" if badges else ""
            cmt_str = f"  -- {col.comment}" if col.comment else ""
            a(f"    │  {col.name:<22} {col.data_type:<20}{badge_str}{cmt_str}")
        if t.indexes:
            for idx in t.indexes:
                uq = " UNIQUE" if idx.unique else ""
                a(f"    │  INDEX {idx.name} ({', '.join(idx.columns)}){uq}")
        a(f"    └{'─' * 46}")
    if state.sequences:
        a(f"\n  Sequences ({len(state.sequences)}):")
        for s in state.sequences.values():
            a(f"    {s.full_name:<30} START {s.start_with}  INCREMENT {s.increment_by}")
    a(f"\n  Relationships ({len(state.relationships)}):")
    for r in state.relationships:
        od = f"  ON DELETE {r.on_delete}" if r.on_delete else ""
        a(f"    {r.from_table}.{r.from_columns} → {r.to_table}.{r.to_columns}  [{r.cardinality}]{od}")
    orphans = state.orphan_tables()
    no_pk = state.tables_without_pk()
    if orphans or no_pk:
        a("\n  ⚠ Insights:")
        if orphans:
            a(f"    Orphan tables (no FK in/out) : {[t.name for t in orphans]}")
        if no_pk:
            a(f"    Tables without PK            : {[t.name for t in no_pk]}")
    a("")
    return "\n".join(lines)


def parse_bool(val: object) -> bool | None:
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    return str(val).lower() in ("1", "true", "yes")
