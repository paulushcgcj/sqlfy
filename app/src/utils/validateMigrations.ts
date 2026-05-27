import type { MigrationFile } from '@/core/types';

/** Severity of a validation issue. */
export type ValidationSeverity = 'error' | 'warning';

/** A single ordering / naming issue found in the migration set. */
export interface ValidationIssue {
  readonly severity: ValidationSeverity;
  readonly type: 'out_of_order' | 'duplicate_version' | 'version_gap' | 'invalid_format';
  readonly message: string;
  /** The filename that triggered this issue (optional). */
  readonly filename?: string;
  /** A concrete suggestion for resolving the issue (optional). */
  readonly suggestion?: string;
}

/** Aggregate result from {@link validateMigrations}. */
export interface ValidationResult {
  readonly total: number;
  readonly hasErrors: boolean;
  readonly hasWarnings: boolean;
  readonly issues: ValidationIssue[];
}

// ── Internal helpers ──────────────────────────────────────────────────────────

/** Parsed representation of a Flyway migration filename. */
interface ParsedMigration {
  readonly original: string;
  readonly type: 'versioned' | 'repeatable' | 'undo' | 'invalid';
  /** Numeric version parts, e.g. [1,2,3] for V1.2.3__ */
  readonly versionParts: number[];
  /** Version string as it appears in the filename, e.g. "1.2.3" */
  readonly versionStr: string;
}

// Matches: V1__, V1.2__, V1.2.3__, V1_2_3__ (version separators: . or _)
const VERSIONED_RE = /^[Vv](\d+(?:[._]\d+)*)__/;
// Matches: R__description.sql
const REPEATABLE_RE = /^[Rr]__/;
// Matches: U1__description.sql
const UNDO_RE = /^[Uu](\d+(?:[._]\d+)*)__/;

function parseMigration(filename: string): ParsedMigration {
  const vMatch = filename.match(VERSIONED_RE);
  if (vMatch) {
    const raw = vMatch[1];
    const parts = raw.split(/[._]/).map(Number);
    return { original: filename, type: 'versioned', versionParts: parts, versionStr: raw };
  }
  if (REPEATABLE_RE.test(filename)) {
    return { original: filename, type: 'repeatable', versionParts: [], versionStr: '' };
  }
  const uMatch = filename.match(UNDO_RE);
  if (uMatch) {
    const raw = uMatch[1];
    const parts = raw.split(/[._]/).map(Number);
    return { original: filename, type: 'undo', versionParts: parts, versionStr: raw };
  }
  return { original: filename, type: 'invalid', versionParts: [], versionStr: '' };
}

/** Compare two version-part arrays lexicographically. */
function compareVersions(a: number[], b: number[]): number {
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i++) {
    const ai = a[i] ?? 0;
    const bi = b[i] ?? 0;
    if (ai !== bi) return ai - bi;
  }
  return 0;
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Validate the ordering and naming of a set of Flyway migration files.
 *
 * Checks performed (in order):
 * 1. Invalid filename format — does not match any known Flyway pattern
 * 2. Duplicate version numbers — two `V1__` migrations
 * 3. Out-of-order versions — filename sort ≠ version sort
 * 4. Version gaps — e.g. V1, V2, V4 (missing V3)
 *
 * Runs entirely in the browser with no CLI dependency.
 *
 * @param files - Migration files currently loaded in the editor
 * @returns Typed validation result with all detected issues
 */
export function validateMigrations(files: MigrationFile[]): ValidationResult {
  const issues: ValidationIssue[] = [];

  const parsed = files.map((f) => parseMigration(f.filename));

  // ── 1. Invalid filename formats ──────────────────────────────────────────
  for (const p of parsed) {
    if (p.type === 'invalid') {
      issues.push({
        severity: 'warning',
        type: 'invalid_format',
        filename: p.original,
        message: `"${p.original}" does not match a recognised Flyway filename pattern.`,
        suggestion: 'Rename to V{version}__{description}.sql, e.g. V1__create_users.sql',
      });
    }
  }

  // Only check ordering/gaps for versioned migrations
  const versioned = parsed.filter((p) => p.type === 'versioned');

  // ── 2. Duplicate versions ────────────────────────────────────────────────
  const seen = new Map<string, string>(); // normalized versionStr → first filename
  for (const p of versioned) {
    const key = p.versionParts.join('.');
    if (seen.has(key)) {
      issues.push({
        severity: 'error',
        type: 'duplicate_version',
        filename: p.original,
        message: `Duplicate version "${p.versionStr}" — "${seen.get(key)}" and "${p.original}" share the same version number.`,
        suggestion: `Renumber one of the two files to use a distinct version.`,
      });
    } else {
      seen.set(key, p.original);
    }
  }

  // ── 3. Out-of-order versions ─────────────────────────────────────────────
  // Expected: versions should be ascending in file-name order
  const fileOrder = versioned.map((p) => p.versionParts);
  const sortedOrder = [...fileOrder].sort(compareVersions);
  for (let i = 0; i < fileOrder.length; i++) {
    if (compareVersions(fileOrder[i], sortedOrder[i]) !== 0) {
      const p = versioned[i];
      issues.push({
        severity: 'error',
        type: 'out_of_order',
        filename: p.original,
        message: `"${p.original}" is out of order — version ${p.versionStr} appears at position ${i + 1} but should be later.`,
        suggestion: 'Sort migration files by version number before applying.',
      });
    }
  }

  // ── 4. Version gaps (integers only — simple V1, V2, V3 sequence) ────────
  const simpleVersions = versioned.filter((p) => p.versionParts.length === 1);
  if (simpleVersions.length >= 2) {
    const nums = simpleVersions.map((p) => p.versionParts[0]).sort((a, b) => a - b);
    for (let i = 1; i < nums.length; i++) {
      const prev = nums[i - 1];
      const curr = nums[i];
      if (curr - prev > 1) {
        const missing = [];
        for (let v = prev + 1; v < curr; v++) missing.push(`V${v}`);
        issues.push({
          severity: 'warning',
          type: 'version_gap',
          message: `Version gap between V${prev} and V${curr} — missing: ${missing.join(', ')}.`,
          suggestion: `Create the missing migration file(s) or verify the gap is intentional.`,
        });
      }
    }
  }

  return {
    total: files.length,
    hasErrors: issues.some((i) => i.severity === 'error'),
    hasWarnings: issues.some((i) => i.severity === 'warning'),
    issues,
  };
}
