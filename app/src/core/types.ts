// AUTO-GENERATED — do not edit by hand.
// Source of truth: schema/types.json
// Regenerate with: cd app && npm run codegen
/**
 * Severity of a schema insight finding.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "InsightSeverity".
 */
export type InsightSeverity = 'error' | 'warning' | 'info';
/**
 * Qualitative health grade.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "HealthGrade".
 */
export type HealthGrade = 'excellent' | 'good' | 'warning' | 'critical';

/**
 * JSON shapes produced by the SQLfy CLI as command output. Every property name is the camelCase alias that Pydantic emits via model_dump_json(by_alias=True).
 */
export interface SQLfyCLIResponseTypes {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [k: string]: any;
}
/**
 * One entry in a migration history list.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "MigrationHistory".
 */
export interface MigrationHistory {
  /**
   * Migration version string.
   */
  version: string;
  /**
   * Human-readable description.
   */
  description: string;
}
/**
 * One chunk from sqlfy chunks --format json.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "VectorChunk".
 */
export interface VectorChunk {
  /**
   * Unique chunk ID.
   */
  id: string;
  /**
   * Chunk type (table, etc.).
   */
  type: string;
  /**
   * Short title.
   */
  title: string;
  /**
   * Full text for embedding.
   */
  content: string;
  /**
   * Arbitrary metadata.
   */
  metadata: {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    [k: string]: any;
  };
  /**
   * RAG retrieval hint.
   */
  hint: string;
}
/**
 * One finding from sqlfy insights --format json.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "InsightFinding".
 */
export interface InsightFinding {
  /**
   * Rule code (e.g. ORPHAN_TABLE).
   */
  code: string;
  /**
   * Severity level.
   */
  severity: 'error' | 'warning' | 'info';
  /**
   * Category grouping.
   */
  category: string;
  /**
   * Human-readable description.
   */
  message: string;
  /**
   * Extended explanation.
   */
  detail?: string;
  /**
   * Suggested SQL/action.
   */
  fix?: string;
  /**
   * Affected table name.
   */
  table?: string;
  /**
   * Affected column name.
   */
  column?: string;
}
/**
 * Aggregated finding counts inside InsightsResult.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "InsightsSummary".
 */
export interface InsightsSummary {
  /**
   * Error count.
   */
  errors: number;
  /**
   * Warning count.
   */
  warnings: number;
  /**
   * Info count.
   */
  infos: number;
  /**
   * Total count.
   */
  total: number;
  /**
   * True when no errors/warnings.
   */
  healthy: boolean;
}
/**
 * Full response from sqlfy insights --format json.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "InsightsResult".
 */
export interface InsightsResult {
  /**
   * Schema version.
   */
  version: string;
  /**
   * State fingerprint.
   */
  fingerprint: string;
  summary: InsightsSummary1;
  /**
   * Findings grouped by severity.
   */
  findings: {
    /**
     * Error findings.
     */
    error: InsightFinding[];
    /**
     * Warning findings.
     */
    warning: InsightFinding[];
    /**
     * Info findings.
     */
    info: InsightFinding[];
  };
}
/**
 * Aggregated counts.
 */
export interface InsightsSummary1 {
  /**
   * Error count.
   */
  errors: number;
  /**
   * Warning count.
   */
  warnings: number;
  /**
   * Info count.
   */
  infos: number;
  /**
   * Total count.
   */
  total: number;
  /**
   * True when no errors/warnings.
   */
  healthy: boolean;
}
/**
 * Per-migration safety row inside HealthResult.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "HealthMigrationStatus".
 */
export interface HealthMigrationStatus {
  /**
   * Migration filename.
   */
  filename: string;
  /**
   * safe | unsafe | irreversible.
   */
  status: 'safe' | 'unsafe' | 'irreversible';
  /**
   * Error count.
   */
  errors: number;
  /**
   * Warning count.
   */
  warnings: number;
  /**
   * Contains DROP TABLE.
   */
  hasDropTable: boolean;
  /**
   * Contains DROP COLUMN.
   */
  hasDropColumn: boolean;
}
/**
 * Score component breakdown inside HealthScore.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "HealthScoreBreakdown".
 */
export interface HealthScoreBreakdown {
  /**
   * Base score.
   */
  base: number;
  /**
   * Error deduction.
   */
  errorPenalty: number;
  /**
   * Warning deduction.
   */
  warningPenalty: number;
  /**
   * Irreversible deduction.
   */
  irreversiblePenalty: number;
}
/**
 * Health score inside HealthResult.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "HealthScore".
 */
export interface HealthScore {
  /**
   * Score 0-100.
   */
  score: number;
  /**
   * Qualitative grade.
   */
  grade: 'excellent' | 'good' | 'warning' | 'critical';
  breakdown: HealthScoreBreakdown1;
}
/**
 * Per-factor breakdown.
 */
export interface HealthScoreBreakdown1 {
  /**
   * Base score.
   */
  base: number;
  /**
   * Error deduction.
   */
  errorPenalty: number;
  /**
   * Warning deduction.
   */
  warningPenalty: number;
  /**
   * Irreversible deduction.
   */
  irreversiblePenalty: number;
}
/**
 * Migration folder stats inside HealthResult.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "HealthSummary".
 */
export interface HealthSummary {
  /**
   * Total count.
   */
  totalMigrations: number;
  /**
   * Safe count.
   */
  safeMigrations: number;
  /**
   * Unsafe count.
   */
  unsafeMigrations: number;
  /**
   * Irreversible count.
   */
  irreversibleMigrations: number;
  /**
   * Percent safe 0-100.
   */
  safePercentage: number;
}
/**
 * Aggregated finding counts inside HealthResult.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "HealthFindings".
 */
export interface HealthFindings {
  /**
   * Total error count.
   */
  errors: number;
  /**
   * Total warning count.
   */
  warnings: number;
  /**
   * Total info count.
   */
  infos: number;
  /**
   * Counts by rule code.
   */
  byCode: {
    [k: string]: number;
  };
}
/**
 * Full response from sqlfy health --format json.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "HealthResult".
 */
export interface HealthResult {
  /**
   * Migrations folder path.
   */
  folder: string;
  /**
   * ISO-8601 report timestamp.
   */
  timestamp: string;
  summary: HealthSummary1;
  findings: HealthFindings1;
  /**
   * Per-migration rows.
   */
  migrations: HealthMigrationStatus[];
  healthScore: HealthScore1;
  /**
   * Human-readable recommendation.
   */
  recommendation: string;
}
/**
 * Migration stats.
 */
export interface HealthSummary1 {
  /**
   * Total count.
   */
  totalMigrations: number;
  /**
   * Safe count.
   */
  safeMigrations: number;
  /**
   * Unsafe count.
   */
  unsafeMigrations: number;
  /**
   * Irreversible count.
   */
  irreversibleMigrations: number;
  /**
   * Percent safe 0-100.
   */
  safePercentage: number;
}
/**
 * Finding counts.
 */
export interface HealthFindings1 {
  /**
   * Total error count.
   */
  errors: number;
  /**
   * Total warning count.
   */
  warnings: number;
  /**
   * Total info count.
   */
  infos: number;
  /**
   * Counts by rule code.
   */
  byCode: {
    [k: string]: number;
  };
}
/**
 * Health score.
 */
export interface HealthScore1 {
  /**
   * Score 0-100.
   */
  score: number;
  /**
   * Qualitative grade.
   */
  grade: 'excellent' | 'good' | 'warning' | 'critical';
  breakdown: HealthScoreBreakdown1;
}
/**
 * Change count summary inside DiffResult and SimulateResult.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "DiffStats".
 */
export interface DiffStats {
  /**
   * Tables added.
   */
  tablesAdded: number;
  /**
   * Tables removed.
   */
  tablesRemoved: number;
  /**
   * Tables modified.
   */
  tablesModified: number;
  /**
   * Columns added.
   */
  columnsAdded: number;
  /**
   * Columns removed.
   */
  columnsRemoved: number;
  /**
   * Columns modified.
   */
  columnsModified: number;
  /**
   * Sequences added.
   */
  sequencesAdded: number;
  /**
   * Sequences removed.
   */
  sequencesRemoved: number;
  /**
   * FK relationships added.
   */
  relationshipsAdded: number;
  /**
   * FK relationships removed.
   */
  relationshipsRemoved: number;
  /**
   * Any breaking change.
   */
  isBreaking: boolean;
}
/**
 * Column-level change inside DiffTableChange.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "DiffColumnChange".
 */
export interface DiffColumnChange {
  /**
   * Column name.
   */
  name: string;
  /**
   * added | removed | modified.
   */
  change: 'added' | 'removed' | 'modified';
  /**
   * Column state before (absent for added).
   */
  before?: {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    [k: string]: any;
  };
  /**
   * Column state after (absent for removed).
   */
  after?: {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    [k: string]: any;
  };
  /**
   * Field change descriptions.
   */
  diffs?: string[];
  /**
   * Could break existing code.
   */
  breaking: boolean;
}
/**
 * Constraint-level change inside DiffTableChange.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "DiffConstraintChange".
 */
export interface DiffConstraintChange {
  /**
   * Constraint name. Null if unnamed.
   */
  name: string | null;
  /**
   * added | removed.
   */
  change: 'added' | 'removed';
  /**
   * Constraint kind.
   */
  type: string;
  /**
   * Columns in the constraint.
   */
  columns: string[];
}
/**
 * Index-level change inside DiffTableChange.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "DiffIndexChange".
 */
export interface DiffIndexChange {
  /**
   * Index name.
   */
  name: string;
  /**
   * added | removed.
   */
  change: 'added' | 'removed';
  /**
   * Columns in the index.
   */
  columns: string[];
  /**
   * Whether unique.
   */
  unique: boolean;
}
/**
 * Table-level change inside DiffResult.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "DiffTableChange".
 */
export interface DiffTableChange {
  /**
   * Fully-qualified table name.
   */
  fullName: string;
  /**
   * added | removed | modified.
   */
  change: 'added' | 'removed' | 'modified';
  /**
   * Is this change breaking.
   */
  breaking: boolean;
  /**
   * Column changes.
   */
  columnChanges?: DiffColumnChange[];
  /**
   * Constraint changes.
   */
  constraintChanges?: DiffConstraintChange[];
  /**
   * Index changes.
   */
  indexChanges?: DiffIndexChange[];
}
/**
 * Sequence-level change inside DiffResult.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "DiffSequenceChange".
 */
export interface DiffSequenceChange {
  /**
   * Fully-qualified sequence name.
   */
  fullName: string;
  /**
   * added | removed | modified.
   */
  change: 'added' | 'removed' | 'modified';
  /**
   * Field change descriptions.
   */
  diffs?: string[];
}
/**
 * FK relationship change inside DiffResult.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "DiffRelationshipChange".
 */
export interface DiffRelationshipChange {
  /**
   * added | removed.
   */
  change: 'added' | 'removed';
  /**
   * Source table name.
   */
  from: string;
  /**
   * Source column names.
   */
  fromCols: string[];
  /**
   * Target table name.
   */
  to: string;
  /**
   * Target column names.
   */
  toCols: string[];
  /**
   * ON DELETE action. Null if none.
   */
  onDelete: string | null;
}
/**
 * Full response from sqlfy diff-versions --format json.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "DiffResult".
 */
export interface DiffResult {
  /**
   * Source version.
   */
  versionA: string;
  /**
   * Target version.
   */
  versionB: string;
  /**
   * Source SHA-256 fingerprint.
   */
  fingerprintA: string;
  /**
   * Target SHA-256 fingerprint.
   */
  fingerprintB: string;
  stats: DiffStats1;
  /**
   * Table changes.
   */
  tableChanges: DiffTableChange[];
  /**
   * Sequence changes.
   */
  sequenceChanges: DiffSequenceChange[];
  /**
   * FK changes.
   */
  relationshipChanges: DiffRelationshipChange[];
}
/**
 * Change counts.
 */
export interface DiffStats1 {
  /**
   * Tables added.
   */
  tablesAdded: number;
  /**
   * Tables removed.
   */
  tablesRemoved: number;
  /**
   * Tables modified.
   */
  tablesModified: number;
  /**
   * Columns added.
   */
  columnsAdded: number;
  /**
   * Columns removed.
   */
  columnsRemoved: number;
  /**
   * Columns modified.
   */
  columnsModified: number;
  /**
   * Sequences added.
   */
  sequencesAdded: number;
  /**
   * Sequences removed.
   */
  sequencesRemoved: number;
  /**
   * FK relationships added.
   */
  relationshipsAdded: number;
  /**
   * FK relationships removed.
   */
  relationshipsRemoved: number;
  /**
   * Any breaking change.
   */
  isBreaking: boolean;
}
/**
 * Health snapshot nested inside SimulateResult.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "SimulateHealth".
 */
export interface SimulateHealth {
  /**
   * Score 0-100.
   */
  score: number;
  /**
   * Qualitative grade.
   */
  grade: 'excellent' | 'good' | 'warning' | 'critical';
  /**
   * Error insight count.
   */
  errors: number;
  /**
   * Warning insight count.
   */
  warnings: number;
}
/**
 * Diff section nested inside SimulateResult.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "SimulateDiff".
 */
export interface SimulateDiff {
  stats: DiffStats2;
  /**
   * Any breaking change.
   */
  isBreaking: boolean;
}
/**
 * Change counts.
 */
export interface DiffStats2 {
  /**
   * Tables added.
   */
  tablesAdded: number;
  /**
   * Tables removed.
   */
  tablesRemoved: number;
  /**
   * Tables modified.
   */
  tablesModified: number;
  /**
   * Columns added.
   */
  columnsAdded: number;
  /**
   * Columns removed.
   */
  columnsRemoved: number;
  /**
   * Columns modified.
   */
  columnsModified: number;
  /**
   * Sequences added.
   */
  sequencesAdded: number;
  /**
   * Sequences removed.
   */
  sequencesRemoved: number;
  /**
   * FK relationships added.
   */
  relationshipsAdded: number;
  /**
   * FK relationships removed.
   */
  relationshipsRemoved: number;
  /**
   * Any breaking change.
   */
  isBreaking: boolean;
}
/**
 * Full response from sqlfy simulate --format json.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "SimulateResult".
 */
export interface SimulateResult {
  /**
   * ISO-8601 simulation timestamp.
   */
  timestamp: string;
  /**
   * Base migration version.
   */
  baseVersion: string;
  /**
   * The simulated DDL.
   */
  sql: string;
  /**
   * Applied without parse errors.
   */
  success: boolean;
  /**
   * No destructive operations.
   */
  isSafe: boolean;
  /**
   * At least one breaking change detected.
   */
  isBreaking: boolean;
  /**
   * Parse/validation errors.
   */
  errors: string[];
  /**
   * Advisory warnings.
   */
  warnings: string[];
  diff: SimulateDiff1;
  health: SimulateHealth1;
}
/**
 * Structural diff.
 */
export interface SimulateDiff1 {
  stats: DiffStats2;
  /**
   * Any breaking change.
   */
  isBreaking: boolean;
}
/**
 * Health snapshot.
 */
export interface SimulateHealth1 {
  /**
   * Score 0-100.
   */
  score: number;
  /**
   * Qualitative grade.
   */
  grade: 'excellent' | 'good' | 'warning' | 'critical';
  /**
   * Error insight count.
   */
  errors: number;
  /**
   * Warning insight count.
   */
  warnings: number;
}
/**
 * Full response from sqlfy impact --format json.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "ImpactResult".
 */
export interface ImpactResult {
  /**
   * Analyzed schema object.
   */
  objectId: string;
  /**
   * Directly affected objects (depth 1).
   */
  direct: string[];
  /**
   * Transitively affected objects (depth > 1).
   */
  transitive: string[];
  /**
   * Object ID to traversal depth.
   */
  depthMap: {
    [k: string]: number;
  };
  /**
   * Affected objects grouped by type.
   */
  byType: {
    [k: string]: string[];
  };
  /**
   * Critical paths from source to leaves.
   */
  criticalPaths: string[][];
  /**
   * Maximum traversal depth reached.
   */
  maxDepth: number;
  /**
   * Total affected count excluding source.
   */
  totalCount: number;
}
/**
 * Rollback feasibility for one migration inside RollbackResult.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "RollbackAnalysis".
 */
export interface RollbackAnalysis {
  /**
   * Migration filename.
   */
  migration: string;
  /**
   * reversible | partial | irreversible.
   */
  feasibility: 'reversible' | 'partial' | 'irreversible';
  /**
   * Rollback difficulty score 0-100.
   */
  score: number;
  /**
   * Suggested rollback SQL. Null if irreversible.
   */
  rollbackScript: string | null;
  /**
   * Risk warnings.
   */
  warnings: string[];
  /**
   * Actionable recommendations.
   */
  recommendations: string[];
  /**
   * Detected SQL operations.
   */
  operations: string[];
}
/**
 * Full response from sqlfy rollback-analysis --format json.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "RollbackResult".
 */
export interface RollbackResult {
  /**
   * Counts by feasibility.
   */
  summary: {
    /**
     * Total migrations.
     */
    total: number;
    /**
     * Reversible count.
     */
    reversible: number;
    /**
     * Partial count.
     */
    partial: number;
    /**
     * Irreversible count.
     */
    irreversible: number;
  };
  /**
   * Per-migration analyses.
   */
  migrations: RollbackAnalysis[];
}
/**
 * High-level metadata from sqlfy manifest.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "SchemaManifest".
 */
export interface SchemaManifest {
  /**
   * Latest migration version.
   */
  schemaVersion: string;
  /**
   * SHA-256 fingerprint.
   */
  fingerprint: string;
  /**
   * SQL dialect.
   */
  dialect: string;
  /**
   * ISO-8601 timestamp.
   */
  generatedAt: string;
  /**
   * sqlfy tool version.
   */
  sqlfyVersion: string;
  /**
   * Graph node count.
   */
  nodeCount: number;
  /**
   * Graph edge count.
   */
  edgeCount: number;
  /**
   * Table count.
   */
  tableCount: number;
  /**
   * Column count.
   */
  columnCount: number;
  /**
   * Sequence count.
   */
  sequenceCount: number;
  /**
   * FK relationship count.
   */
  relationshipCount: number;
  /**
   * Index count.
   */
  indexCount: number;
  /**
   * Tables without primary key.
   */
  tablesWithoutPk: number;
  /**
   * Migration file count.
   */
  migrationCount: number;
  /**
   * Ordered migration list.
   */
  migrationHistory: MigrationHistory[];
}
/**
 * Column inside TableState (from sqlfy dump).
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "ColumnState".
 */
export interface ColumnState {
  /**
   * Column name.
   */
  name: string;
  /**
   * Rendered type e.g. NUMBER(10,2).
   */
  dataType: string;
  /**
   * Base type name e.g. NUMBER.
   */
  rawType: string;
  /**
   * Numeric precision. Null if N/A.
   */
  precision: number | null;
  /**
   * Numeric scale. Null if N/A.
   */
  scale: number | null;
  /**
   * Accepts NULL.
   */
  nullable: boolean;
  /**
   * Default expression. Null if none.
   */
  default: string | null;
  /**
   * Part of primary key.
   */
  isPk: boolean;
  /**
   * Part of foreign key.
   */
  isFk: boolean;
  /**
   * Has unique constraint.
   */
  isUnique: boolean;
  /**
   * Column comment. Null if none.
   */
  comment: string | null;
}
/**
 * Constraint inside TableState (from sqlfy dump).
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "ConstraintState".
 */
export interface ConstraintState {
  /**
   * Name. Null if unnamed.
   */
  name: string | null;
  /**
   * primary_key|unique|foreign_key|check.
   */
  type: string;
  /**
   * Column names.
   */
  columns: string[];
  /**
   * Referenced table (FK only).
   */
  refTable?: string | null;
  /**
   * Referenced columns (FK only).
   */
  refColumns?: string[] | null;
  /**
   * ON DELETE action (FK only).
   */
  onDelete?: string | null;
  /**
   * CHECK expression (CHECK only).
   */
  checkExpr?: string | null;
}
/**
 * Index inside TableState (from sqlfy dump).
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "IndexState".
 */
export interface IndexState {
  /**
   * Index name.
   */
  name: string;
  /**
   * Columns in the index.
   */
  columns: string[];
  /**
   * Whether unique.
   */
  unique: boolean;
  /**
   * Created in migration ver.
   */
  createdIn: string;
}
/**
 * Table inside SchemaState (from sqlfy dump).
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "TableState".
 */
export interface TableState {
  /**
   * Schema/owner. Null for default.
   */
  schema: string | null;
  /**
   * Table name (uppercased).
   */
  name: string;
  /**
   * Fully-qualified name.
   */
  fullName: string;
  /**
   * Ordered columns.
   */
  columns: ColumnState[];
  /**
   * Constraints.
   */
  constraints: ConstraintState[];
  /**
   * Indexes.
   */
  indexes: IndexState[];
  /**
   * Table comment.
   */
  comment: string | null;
  /**
   * Created in migration ver.
   */
  createdIn: string;
  /**
   * Modified in migration versions.
   */
  modifiedIn: string[];
  /**
   * Number of columns.
   */
  columnCount: number;
  /**
   * Has a primary key.
   */
  hasPk: boolean;
  /**
   * PK column names.
   */
  pkColumns: string[];
}
/**
 * Sequence inside SchemaState (from sqlfy dump).
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "SequenceState".
 */
export interface SequenceState {
  /**
   * Schema/owner. Null for default.
   */
  schema: string | null;
  /**
   * Sequence name.
   */
  name: string;
  /**
   * Fully-qualified name.
   */
  fullName: string;
  /**
   * START WITH value.
   */
  startWith: number;
  /**
   * INCREMENT BY value.
   */
  incrementBy: number;
  /**
   * Created in migration ver.
   */
  createdIn: string;
}
/**
 * FK relationship inside SchemaState (from sqlfy dump).
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "RelationshipState".
 */
export interface RelationshipState {
  /**
   * Unique relationship ID.
   */
  id: string;
  /**
   * Source table.
   */
  fromTable: string;
  /**
   * Source columns.
   */
  fromColumns: string[];
  /**
   * Target table.
   */
  toTable: string;
  /**
   * Target columns.
   */
  toColumns: string[];
  /**
   * FK name. Null if unnamed.
   */
  constraintName: string | null;
  /**
   * ON DELETE action. Null if none.
   */
  onDelete: string | null;
  /**
   * many_to_one | one_to_one | unknown.
   */
  cardinality: string;
}
/**
 * Full response from sqlfy dump --format json.
 *
 * This interface was referenced by `SQLfyCLIResponseTypes`'s JSON-Schema
 * via the `definition` "SchemaState".
 */
export interface SchemaState {
  /**
   * Latest migration version.
   */
  version: string;
  /**
   * ISO-8601 generation timestamp.
   */
  generatedAt: string;
  /**
   * SHA-256 fingerprint.
   */
  fingerprint: string;
  /**
   * SQL dialect.
   */
  dialect: string;
  /**
   * Tables keyed by full name.
   */
  tables: {
    [k: string]: TableState;
  };
  /**
   * Sequences keyed by full name.
   */
  sequences: {
    [k: string]: SequenceState;
  };
  /**
   * All FK relationships.
   */
  relationships: RelationshipState[];
  /**
   * Ordered migration list.
   */
  migrationHistory: MigrationHistory[];
  /**
   * Summary counts.
   */
  stats: {
    [k: string]: number;
  };
}

// App-internal types (not CLI JSON output) — hand-written in local-types.ts
export * from './local-types';
