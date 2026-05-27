import type { MigrationFile } from '@/core/types';
import type { FC } from 'react';

import { useEffect, useState } from 'react';

import { runHealth, CLI_AVAILABLE, type HealthResult, type HealthGrade } from '@/bridge/cli';
import { writeFile, folderLabel, type FolderHandle } from '@/bridge/folder';
import { validateMigrations, type ValidationResult } from '@/utils/validateMigrations';
import './index.scss';

/** Props for the {@link MigrationsTab} component. */
export interface MigrationsTabProps {
  /** The list of SQL migration files currently loaded. */
  readonly files: MigrationFile[];
  /** Callback to update the migration file list (add, edit, or remove). */
  readonly onChange: (files: MigrationFile[]) => void;
  /**
   * When set, new migrations added via the button are also written to this folder.
   * @default null
   */
  readonly folderHandle?: FolderHandle | null;
  /**
   * Called when the user clicks "Load from folder".
   * App-level responsibility: opens picker, reads files, updates state.
   * @default undefined
   */
  readonly onLoadFolder?: () => Promise<void>;
}

// ── Health grade helpers ──────────────────────────────────────────────────────

const GRADE_LABEL: Record<HealthGrade, string> = {
  excellent: '✓ Excellent',
  good: '✓ Good',
  warning: '⚠ Warning',
  critical: '✕ Critical',
};

const GRADE_CLASS: Record<HealthGrade, string> = {
  excellent: 'health-grade--excellent',
  good: 'health-grade--good',
  warning: 'health-grade--warning',
  critical: 'health-grade--critical',
};

/**
 * Migration files editor panel.
 *
 * Auto-validates migration file ordering whenever the file list changes and displays
 * inline error/warning banners. When a folder is loaded and CLI is available, a
 * health score badge is shown in the toolbar with an expandable breakdown panel.
 *
 * @component
 * @param props - {@link MigrationsTabProps}
 * @returns An editable list of SQL migration file blocks.
 */
const MigrationsTab: FC<MigrationsTabProps> = ({ files, onChange, folderHandle, onLoadFolder }) => {
  // ── Validation (pure TS, runs on every files change) ─────────────────────
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [validationDismissed, setValidationDismissed] = useState(false);

  useEffect(() => {
    if (files.length === 0) {
      setValidation(null);
      return;
    }
    setValidationDismissed(false);
    setValidation(validateMigrations(files));
  }, [files]);

  // ── Health (CLI, runs on demand or on folder load) ────────────────────────
  const [health, setHealth] = useState<HealthResult | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [healthExpanded, setHealthExpanded] = useState(false);

  async function handleRunHealth() {
    setHealthLoading(true);
    setHealthError(null);
    try {
      const result = await runHealth(files);
      setHealth(result);
      setHealthExpanded(true);
    } catch (e) {
      setHealthError(e instanceof Error ? e.message : 'Health check failed');
    } finally {
      setHealthLoading(false);
    }
  }

  // ── File operations ───────────────────────────────────────────────────────
  function updateFile(index: number, field: keyof MigrationFile, value: string) {
    const next = files.map((f, i) => (i === index ? { ...f, [field]: value } : f));
    onChange(next);
  }

  function removeFile(index: number) {
    onChange(files.filter((_, i) => i !== index));
  }

  async function addFile() {
    const filename = `V${files.length + 1}__new_migration.sql`;
    const sql = '-- Add your SQL here\n';
    if (folderHandle) {
      await writeFile(folderHandle, filename, sql);
    }
    onChange([...files, { filename, sql }]);
  }

  // ── Derived ───────────────────────────────────────────────────────────────
  const showValidation =
    !validationDismissed &&
    validation !== null &&
    (validation.hasErrors || validation.hasWarnings);

  const showHealthBtn = CLI_AVAILABLE && files.length > 0;

  return (
    <div className="panel">
      {/* Toolbar */}
      <div className="migrations-toolbar">
        <button className="migraton-btn add-btn" onClick={addFile}>
          + Add Migration File
        </button>
        {onLoadFolder && (
          <button className="migraton-btn load-folder-btn" onClick={onLoadFolder}>
            📁 Load from folder
          </button>
        )}
        {folderHandle && (
          <span
            className="folder-badge"
            title={folderHandle.type === 'tauri' ? folderHandle.path : folderHandle.dir.name}
          >
            {folderLabel(folderHandle)}
            <span className="folder-count">
              {files.length} file{files.length !== 1 ? 's' : ''}
            </span>
          </span>
        )}

        {/* Health score badge */}
        {health && !healthLoading && (
          <button
            className={`health-badge ${GRADE_CLASS[health.health_score.grade]}`}
            onClick={() => setHealthExpanded((v) => !v)}
            title="Click to toggle health breakdown"
            aria-expanded={healthExpanded}
          >
            {GRADE_LABEL[health.health_score.grade]} — {health.health_score.score}/100
          </button>
        )}

        {/* Health check button */}
        {showHealthBtn && (
          <button
            className="migraton-btn health-btn"
            onClick={handleRunHealth}
            disabled={healthLoading}
            title="Run migration folder health analysis"
          >
            {healthLoading ? '⏳ Checking…' : health ? '↺ Re-check Health' : '🩺 Health Check'}
          </button>
        )}
      </div>

      {/* Validation banner */}
      {showValidation && validation && (
        <div
          className={`validation-banner ${validation.hasErrors ? 'validation-banner--error' : 'validation-banner--warning'}`}
          role="alert"
        >
          <div className="validation-banner__hdr">
            <span className="validation-banner__title">
              {validation.hasErrors ? '✕ Migration Ordering Errors' : '⚠ Migration Ordering Warnings'}
            </span>
            <button
              className="validation-banner__dismiss"
              onClick={() => setValidationDismissed(true)}
              aria-label="Dismiss validation issues"
            >
              ×
            </button>
          </div>
          <ul className="validation-banner__list">
            {validation.issues.map((issue, i) => (
              <li key={i} className={`vissue vissue--${issue.severity}`}>
                <span className="vissue__msg">{issue.message}</span>
                {issue.suggestion && (
                  <span className="vissue__hint">💡 {issue.suggestion}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Health error */}
      {healthError && (
        <div className="validation-banner validation-banner--error" role="alert">
          <span>⚠ Health check failed: {healthError}</span>
        </div>
      )}

      {/* Health breakdown panel */}
      {healthExpanded && health && (
        <div className="health-panel">
          <div className="health-panel__hdr">
            <span className="health-panel__title">Migration Health Report</span>
            <button
              className="validation-banner__dismiss"
              onClick={() => setHealthExpanded(false)}
              aria-label="Close health panel"
            >
              ×
            </button>
          </div>

          <div className="health-panel__summary">
            <div className={`health-score-circle ${GRADE_CLASS[health.health_score.grade]}`}>
              <span className="health-score-circle__num">{health.health_score.score}</span>
              <span className="health-score-circle__label">/100</span>
            </div>
            <div className="health-panel__stats">
              <div className="hstat">
                <span className="hstat__val hstat__val--ok">{health.summary.safe_migrations}</span>
                <span className="hstat__lbl">Safe</span>
              </div>
              <div className="hstat">
                <span className="hstat__val hstat__val--warn">
                  {health.summary.unsafe_migrations}
                </span>
                <span className="hstat__lbl">Unsafe</span>
              </div>
              <div className="hstat">
                <span className="hstat__val hstat__val--err">
                  {health.summary.irreversible_migrations}
                </span>
                <span className="hstat__lbl">Irreversible</span>
              </div>
              <div className="hstat">
                <span className="hstat__val">{health.findings.errors}</span>
                <span className="hstat__lbl">Errors</span>
              </div>
              <div className="hstat">
                <span className="hstat__val">{health.findings.warnings}</span>
                <span className="hstat__lbl">Warnings</span>
              </div>
            </div>
          </div>

          {health.recommendation && (
            <p className="health-panel__rec">{health.recommendation}</p>
          )}

          {/* Per-migration status list */}
          <table className="health-migrations-table">
            <thead>
              <tr>
                <th>File</th>
                <th>Status</th>
                <th>Errors</th>
                <th>Warnings</th>
              </tr>
            </thead>
            <tbody>
              {health.migrations.map((m) => (
                <tr key={m.filename} className={`hrow hrow--${m.status}`}>
                  <td className="hrow__file">{m.filename}</td>
                  <td>
                    <span className={`hrow__status hrow__status--${m.status}`}>
                      {m.status === 'safe' ? '✓ safe' : m.status === 'irreversible' ? '⚠ irreversible' : '✕ unsafe'}
                    </span>
                  </td>
                  <td>{m.errors > 0 ? <span className="hrow__num hrow__num--err">{m.errors}</span> : '—'}</td>
                  <td>{m.warnings > 0 ? <span className="hrow__num hrow__num--warn">{m.warnings}</span> : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Migration file blocks */}
      {files.map((file, i) => (
        <div className="file-block" key={file.filename || `migration-${i}`}>
          <div className="file-hdr">
            <span className="file-v-badge">V</span>
            <input
              value={file.filename}
              onChange={(e) => updateFile(i, 'filename', e.target.value)}
            />
            {/* Per-file health status dot */}
            {health && (() => {
              const mh = health.migrations.find((m) => m.filename === file.filename);
              if (!mh) return null;
              return (
                <span
                  className={`file-health-dot file-health-dot--${mh.status}`}
                  title={`Health: ${mh.status}`}
                  aria-label={`Migration status: ${mh.status}`}
                />
              );
            })()}
            <button className="rm" onClick={() => removeFile(i)}>
              ×
            </button>
          </div>
          <textarea
            className="sql-area"
            rows={10}
            value={file.sql}
            onChange={(e) => updateFile(i, 'sql', e.target.value)}
          />
        </div>
      ))}
    </div>
  );
};

export default MigrationsTab;
