import { useState } from 'react';

import { CLI_AVAILABLE, runSimulate } from '@/bridge/cli';
import type { MigrationFile } from '@/core/types';
import type { SimulateResult } from '@/bridge/cli';

import './index.scss';

// ── Stat rows shown in the diff summary ────────────────────────────────────
interface DiffRow {
  label: string;
  addedKey: keyof import('@/bridge/cli').SimulateDiffStats;
  removedKey: keyof import('@/bridge/cli').SimulateDiffStats;
}

const DIFF_ROWS: DiffRow[] = [
  { label: 'Tables', addedKey: 'tables_added', removedKey: 'tables_removed' },
  { label: 'Columns', addedKey: 'columns_added', removedKey: 'columns_removed' },
  { label: 'Sequences', addedKey: 'sequences_added', removedKey: 'sequences_removed' },
  { label: 'Relationships', addedKey: 'relationships_added', removedKey: 'relationships_removed' },
];

// ── Component ───────────────────────────────────────────────────────────────

interface SimulatePanelProps {
  files: MigrationFile[];
}

export default function SimulatePanel({ files }: SimulatePanelProps) {
  const [sql, setSql] = useState('');
  const [atVersion, setAtVersion] = useState('');
  const [result, setResult] = useState<SimulateResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSimulate() {
    const trimmedSql = sql.trim();
    if (!trimmedSql || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const opts = atVersion.trim() ? { atVersion: parseInt(atVersion, 10) } : undefined;
      const res = await runSimulate(files, trimmedSql, opts);
      setResult(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const canRun = CLI_AVAILABLE && sql.trim().length > 0 && !loading;

  return (
    <div className="sim-panel">
      <p className="sim-panel__intro">
        Test hypothetical DDL changes against your current schema. The simulation applies your SQL
        on top of the migration state and reports safety, breaking changes, and schema diff —
        without modifying any files.
      </p>

      {/* SQL editor */}
      <div className="sim-panel__editor">
        <label className="sim-panel__label" htmlFor="sim-sql-input">
          SQL to simulate
        </label>
        <textarea
          id="sim-sql-input"
          className="sim-panel__textarea"
          placeholder="-- e.g. ALTER TABLE APP.USERS ADD (email VARCHAR2(255));"
          value={sql}
          onChange={e => setSql(e.target.value)}
          rows={6}
          spellCheck={false}
        />
      </div>

      {/* Options row */}
      <div className="sim-panel__options">
        <label className="sim-panel__label sim-panel__version-label" htmlFor="sim-at-version">
          Base version
          <span className="sim-panel__hint">(optional — defaults to latest)</span>
        </label>
        <input
          id="sim-at-version"
          className="sim-panel__version-input"
          type="number"
          min={1}
          placeholder="latest"
          value={atVersion}
          onChange={e => setAtVersion(e.target.value)}
        />

        <button
          className="sim-panel__run-btn"
          onClick={handleSimulate}
          disabled={!canRun}
          aria-busy={loading}
        >
          {loading ? '⏳ Simulating…' : '▶ Simulate'}
        </button>
      </div>

      {/* No-CLI notice */}
      {!CLI_AVAILABLE && (
        <div className="sim-panel__no-cli" role="alert">
          Simulation requires the Python CLI — not available in pure-browser mode. Run the app in
          Tauri or the Vite dev server.
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="sim-panel__error" role="alert">
          ⚠ {error}
        </div>
      )}

      {/* Results */}
      {result && <SimulateResults result={result} />}
    </div>
  );
}

// ── Results sub-component ───────────────────────────────────────────────────

function SimulateResults({ result }: { result: SimulateResult }) {
  const { is_safe, is_breaking, health, errors, warnings, diff, base_version } = result;

  const hasDiffChanges = diff
    ? DIFF_ROWS.some(r => diff.stats[r.addedKey] > 0 || diff.stats[r.removedKey] > 0)
    : false;

  const modified =
    diff?.stats.tables_modified || diff?.stats.columns_modified
      ? diff.stats.tables_modified + diff.stats.columns_modified
      : 0;

  return (
    <div className="sim-results">
      {/* Status badges */}
      <div className="sim-results__badges">
        <span className={`sim-badge sim-badge--${is_safe ? 'safe' : 'unsafe'}`}>
          {is_safe ? '✓ Safe' : '✕ Unsafe'}
        </span>

        {is_breaking && <span className="sim-badge sim-badge--breaking">⚠ Breaking Changes</span>}

        <span className={`sim-badge sim-badge--health-${health.grade}`}>
          Health {health.score}/100 · {health.grade}
        </span>
      </div>

      <p className="sim-results__meta">
        Simulated at base version <strong>V{base_version}</strong>
      </p>

      {/* Errors */}
      {errors.length > 0 && (
        <div className="sim-results__errors">
          <h4 className="sim-results__section-title">
            Errors ({errors.length})
          </h4>
          <ul className="sim-results__list">
            {errors.map((e, i) => (
              <li key={i} className="sim-results__list-item sim-results__list-item--error">
                {e}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Diff stats */}
      {hasDiffChanges && (
        <div className="sim-results__diff">
          <h4 className="sim-results__section-title">Schema Changes</h4>
          <table className="sim-diff-table">
            <thead>
              <tr>
                <th>Object</th>
                <th className="sim-diff-table__added">Added</th>
                <th className="sim-diff-table__removed">Removed</th>
                {modified > 0 && <th className="sim-diff-table__modified">Modified</th>}
              </tr>
            </thead>
            <tbody>
              {DIFF_ROWS.map(({ label, addedKey, removedKey }) => {
                const added = diff!.stats[addedKey] as number;
                const removed = diff!.stats[removedKey] as number;
                if (added === 0 && removed === 0) return null;
                return (
                  <tr key={label}>
                    <td>{label}</td>
                    <td className="sim-diff-table__added">{added > 0 ? `+${added}` : '—'}</td>
                    <td className="sim-diff-table__removed">{removed > 0 ? `-${removed}` : '—'}</td>
                    {modified > 0 && <td className="sim-diff-table__modified">—</td>}
                  </tr>
                );
              })}
              {modified > 0 && (
                <tr>
                  <td>Modified</td>
                  <td className="sim-diff-table__added">—</td>
                  <td className="sim-diff-table__removed">—</td>
                  <td className="sim-diff-table__modified">{modified}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {!hasDiffChanges && !is_breaking && (
        <p className="sim-results__no-changes">No structural changes detected.</p>
      )}

      {/* Warnings */}
      {warnings.length > 0 && (
        <details className="sim-results__warnings">
          <summary className="sim-results__warnings-summary">
            {warnings.length} warning{warnings.length !== 1 ? 's' : ''}
          </summary>
          <ul className="sim-results__list">
            {warnings.map((w, i) => (
              <li key={i} className="sim-results__list-item sim-results__list-item--warning">
                {w}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
