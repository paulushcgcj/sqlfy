// ─────────────────────────────────────────────
// sqlfy — src/core/types.ts
// Shared type definitions for the schema graph engine
// ─────────────────────────────────────────────

export interface MigrationFile {
  filename: string;
  sql: string;
}

export interface Column {
  name: string;
  type: string;
  precision: number | null;
  scale: number | null;
  nullable: boolean;
  default: string | null;
  primaryKey: boolean;
  unique: boolean;
  references: { table: string; column: string } | null;
}

export type ConstraintType = 'primary_key' | 'unique' | 'foreign_key' | 'check';

export interface Constraint {
  name: string | null;
  type: ConstraintType;
  columns: string[];
  references?: {
    table: string;
    columns: string[];
    onDelete: string | null;
  };
  checkExpr?: string;
}

export interface Index {
  name: string;
  columns: string[];
  unique: boolean;
  createdIn: string;
}

export interface Table {
  id: string;
  schema: string | null;
  name: string;
  full: string;
  columns: Column[];
  constraints: Constraint[];
  indexes: Index[];
  comments: Record<string, string>;
  createdIn: string;
  modifiedIn: string[];
}

export interface Sequence {
  name: string;
  schema: string | null;
  full: string;
  startWith: number;
  incrementBy: number;
  createdIn: string;
}

export interface Edge {
  id: string;
  fromTable: string;
  fromCols: string[];
  toTable: string;
  toCols: string[];
  constraintName: string | null;
  onDelete: string | null;
}

export interface MigrationHistory {
  version: string;
  description: string;
}

export interface SchemaGraph {
  tables: Map<string, Table>;
  seqs: Map<string, Sequence>;
  edges: Edge[];
  migHist: MigrationHistory[];
}

export interface VectorChunk {
  id: string;
  type: string;
  title: string;
  content: string;
  meta: Record<string, unknown>;
  hint: string;
}

export interface LayoutPoint {
  x: number;
  y: number;
}
