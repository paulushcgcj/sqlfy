/**
 * App-internal TypeScript types.
 *
 * These types are used by the React app and the in-browser TypeScript core
 * (core.ts) but are NOT part of the CLI JSON response contract.
 * CLI response types live in the auto-generated ./types.ts.
 */

// ─── Migration input ──────────────────────────────────────────────────────────

/** A single Flyway-style SQL migration file (input to the app, not CLI output). */
export interface MigrationFile {
  /** Flyway migration filename, e.g. V1__create_users.sql. */
  filename: string;
  /** Raw SQL content of the migration file. */
  sql: string;
}

// ─── Schema graph primitives ───────────────────────────────────────────────────

/** A column-level foreign key reference target. */
export interface ColumnReference {
  /** Fully-qualified target table name (e.g. APP.USERS). */
  table: string;
  /** Target column name. */
  column: string;
}

/** The kind of a table constraint. */
export type ConstraintType = 'primary_key' | 'unique' | 'foreign_key' | 'check';

/** Foreign key constraint reference details. */
export interface ConstraintReference {
  /** Fully-qualified referenced table name. */
  table: string;
  /** Referenced column names. */
  columns: string[];
  /** ON DELETE action (e.g. CASCADE, SET_NULL). Null if not defined. */
  onDelete?: string | null;
}

/** A single column in a database table (in-memory representation). */
export interface Column {
  /** Column name (uppercased). */
  name: string;
  /** Base data type name, e.g. NUMBER, VARCHAR2, DATE. */
  type: string;
  /** Numeric precision. Null when not applicable. */
  precision: number | null;
  /** Numeric scale. Null when not applicable. */
  scale: number | null;
  /** Whether the column accepts NULL values. */
  nullable: boolean;
  /** Default value expression. Null if none. */
  default: string | null;
  /** Whether this column is part of the primary key. */
  primaryKey: boolean;
  /** Whether this column has a unique constraint. */
  unique: boolean;
  /** FK reference target if this column has an inline REFERENCES clause. Null otherwise. */
  references: ColumnReference | null;
}

/** A table-level constraint (PK, FK, UNIQUE, CHECK). */
export interface Constraint {
  /** Constraint name. Null if unnamed. */
  name: string | null;
  /** Constraint kind. */
  type: ConstraintType;
  /** Column names involved in this constraint. */
  columns: string[];
  /** FK reference details. Present only for foreign_key constraints. */
  references?: ConstraintReference;
  /** CHECK constraint expression. Present only for check constraints. */
  checkExpr?: string;
}

/** An index on a database table. */
export interface Index {
  /** Index name. */
  name: string;
  /** Column names covered by the index. */
  columns: string[];
  /** Whether this is a unique index. */
  unique: boolean;
  /** Migration version in which this index was created. */
  createdIn: string;
}

/** A fully reconstructed database table (in-memory representation). */
export interface Table {
  /** Fully-qualified table identifier (e.g. APP.USERS). */
  id: string;
  /** Schema/owner name. Null for default schema. */
  schema: string | null;
  /** Table name (uppercased, no schema prefix). */
  name: string;
  /** Fully-qualified table name (SCHEMA.TABLE). */
  full: string;
  /** Ordered list of columns. */
  columns: Column[];
  /** All constraints on this table. */
  constraints: Constraint[];
  /** All indexes on this table. */
  indexes: Index[];
  /** COMMENT ON TABLE/COLUMN values keyed by column name; __table__ for the table comment. */
  comments: Record<string, string>;
  /** Migration version that created this table. */
  createdIn: string;
  /** Migration versions that modified this table, in order. */
  modifiedIn: string[];
}

/** A database sequence (in-memory representation). */
export interface Sequence {
  /** Sequence name (uppercased). */
  name: string;
  /** Schema/owner name. Null for default schema. */
  schema: string | null;
  /** Fully-qualified sequence name. */
  full: string;
  /** START WITH value. */
  startWith: number;
  /** INCREMENT BY value. */
  incrementBy: number;
  /** Migration version that created this sequence. */
  createdIn: string;
}

/** A foreign-key edge in the schema graph. */
export interface Edge {
  /** Unique edge identifier. */
  id: string;
  /** Fully-qualified source table name. */
  fromTable: string;
  /** Source column names. */
  fromCols: string[];
  /** Fully-qualified target table name. */
  toTable: string;
  /** Target column names. */
  toCols: string[];
  /** FK constraint name. Null if unnamed. */
  constraintName: string | null;
  /** ON DELETE action. Null if not specified. */
  onDelete: string | null;
}

/** The fully-parsed in-memory schema graph (app-internal, uses Maps). */
export interface SchemaGraph {
  /** Tables keyed by fully-qualified name. */
  tables: Map<string, Table>;
  /** Sequences keyed by fully-qualified name. */
  seqs: Map<string, Sequence>;
  /** All FK edges. */
  edges: Edge[];
  /** Ordered migration history. */
  migHist: { version: string; description: string }[];
}

// ─── UI helpers ───────────────────────────────────────────────────────────────

/** A 2D layout coordinate for graph visualisation. */
export interface LayoutPoint {
  /** Horizontal position. */
  x: number;
  /** Vertical position. */
  y: number;
}
