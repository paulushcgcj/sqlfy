/**
 * HealthDashboard — comprehensive health score and migration safety overview.
 *
 * Calls `sqlfy health --format json` via the Tauri CLI or Vite dev-server proxy.
 * Requires an active CLI connection — pure-browser mode is not supported
 * and displays a clear "CLI required" message.
 *
 *  • Score gauge with grade badge
 *  • Summary stats cards (total, safe, unsafe, irreversible migrations)
 *  • Findings breakdown (errors, warnings, infos + top issue codes)
 *  • Per-migration status table with error/warning counts
 *  • Score breakdown waterfall (base → penalties → final)
 *  • Recommendation callout
 */

import { useState, useCallback } from 'react';

import type { MigrationFile } from '@/core/types';
import type { FC } from 'react';

import { CLI_AVAILABLE, CLI_MODE_LABEL, runHealth, type HealthResult } from '@/bridge/cli';
import './index.scss';

// ─── Types ────────────────────────────────────────────────────────────────────

/** Props for the {@link HealthDashboard} component. */
export interface HealthDashboardProps {
  /** Raw migration files passed to the CLI. */
  readonly files: MigrationFile[];
}

// ─── Constants ────────────────────────────────────────────────────────────────

const GRADE_LABEL: Record<string, string> = {
  excellent: '✓ Excellent',
  good: '✓ Good',
  warning: '⚠ Warning',
  critical: '✕ Critical',
};

const GRADE_COLOR: Record<string, string> = {
  excellent: '#22c55e',
  good: '#3b82f6',
  warning: '#f59e0b',
  critical: '#ef4444',
};

const STATUS_LABEL: Record<string, string> = {
  safe: '✓ Safe',
  unsafe: '⚠ Unsafe',
  irreversible: '🔴 Irreversible',
};

// STATUS_COLOR is kept for reference; currently using data attributes for styling
// const STATUS_COLOR: Record<string, string> = {
//   safe: '#22c55e',
//   unsafe: '#f59e0b',
//   irreversible: '#ef4444',
// };

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Render a circular score gauge using SVG.
 * @param score - Score from 0-100
 * @param color - RGB/hex color for the filled arc
 */
function ScoreGauge({ score, color }: { score: number; color: string }) {
  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  return (
    <svg viewBox="0 0 120 120" className="hd-gauge-svg">
      {/* Background circle */}
      <circle cx="60" cy="60" r={radius} fill="none" stroke="#e5e7eb" strokeWidth="6" />
      {/* Filled arc */}
      <circle
        cx="60"
        cy="60"
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth="6"
        strokeDasharray={circumference}
        strokeDashoffset={strokeDashoffset}
        strokeLinecap="round"
        className="hd-gauge-fill"
      />
      {/* Center text */}
      <text x="60" y="60" textAnchor="middle" dy="0.3em" className="hd-gauge-text">
        {score}
      </text>
    </svg>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

/**
 * Full-featured health dashboard with score gauge, summary stats,
 * findings breakdown, and per-migration status.
 *
 * Requires the Python CLI (Tauri or Vite dev-server). Pure-browser mode
 * is not supported — a "CLI required" notice is shown instead.
 *
 * @component
 * @param props - {@link HealthDashboardProps}
 */
const HealthDashboard: FC<HealthDashboardProps> = ({ files }) => {
  const [result, setResult] = useState<HealthResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Run health check ──

  const handleRun = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const healthResult = await runHealth(files);
      setResult(healthResult);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [files]);

  // ── No-CLI guard ──

  if (!CLI_AVAILABLE) {
    return (
      <div className="hd">
        <div className="hd__no-cli">
          <span className="hd__no-cli-icon">🔌</span>
          <p>
            <strong>CLI required</strong>
          </p>
          <p>
            Health dashboard requires the Python CLI. Run the app with <code>npx tauri dev</code> or{' '}
            <code>npm run dev</code> and ensure <code>sqlfy</code> is installed (
            <code>pip install -e cli/</code>).
          </p>
        </div>
      </div>
    );
  }

  // ── Render ──

  return (
    <div className="hd">
      {/* ── Header / controls ── */}
      <div className="hd__controls">
        <button className="hd__run-btn" onClick={handleRun} disabled={loading}>
          {loading ? '⏳ Checking…' : '▶ Run Health Check'}
        </button>
        {CLI_MODE_LABEL && <span className="hd__hint">{CLI_MODE_LABEL}</span>}
      </div>

      {/* ── Error ── */}
      {error && <div className="hd__error">⚠ {error}</div>}

      {/* ── Loading ── */}
      {loading && <div className="hd__loading">Running sqlfy health…</div>}

      {/* ── Result ── */}
      {result && !loading && (
        <div className="hd__result">
          {/* Score card */}
          <div className="hd__score-card" data-grade={result.healthScore.grade}>
            <div className="hd__score-gauge">
              <ScoreGauge
                score={result.healthScore.score}
                color={GRADE_COLOR[result.healthScore.grade]}
              />
            </div>
            <div className="hd__score-info">
              <div className="hd__score-label">Health Score</div>
              <div className="hd__score-grade">{GRADE_LABEL[result.healthScore.grade]}</div>
              <div className="hd__score-out-of">out of 100</div>
            </div>
          </div>

          {/* Summary cards */}
          <div className="hd__summary-grid">
            <div className="hd__summary-card" data-stat="total">
              <div className="hd__summary-icon">📊</div>
              <div className="hd__summary-value">{result.summary.totalMigrations}</div>
              <div className="hd__summary-label">Total Migrations</div>
            </div>
            <div className="hd__summary-card" data-stat="safe">
              <div className="hd__summary-icon">✓</div>
              <div className="hd__summary-value">{result.summary.safeMigrations}</div>
              <div className="hd__summary-label">Safe ({result.summary.safePercentage}%)</div>
            </div>
            <div className="hd__summary-card" data-stat="unsafe">
              <div className="hd__summary-icon">⚠</div>
              <div className="hd__summary-value">{result.summary.unsafeMigrations}</div>
              <div className="hd__summary-label">Unsafe</div>
            </div>
            <div className="hd__summary-card" data-stat="irreversible">
              <div className="hd__summary-icon">🔴</div>
              <div className="hd__summary-value">{result.summary.irreversibleMigrations}</div>
              <div className="hd__summary-label">Irreversible</div>
            </div>
          </div>

          {/* Findings breakdown */}
          <div className="hd__findings-card">
            <h3 className="hd__section-title">Findings Summary</h3>
            <div className="hd__findings-grid">
              <div className="hd__findings-stat" data-type="errors">
                <span className="hd__findings-count">{result.findings.errors}</span>
                <span className="hd__findings-label">Errors</span>
              </div>
              <div className="hd__findings-stat" data-type="warnings">
                <span className="hd__findings-count">{result.findings.warnings}</span>
                <span className="hd__findings-label">Warnings</span>
              </div>
              <div className="hd__findings-stat" data-type="infos">
                <span className="hd__findings-count">{result.findings.infos}</span>
                <span className="hd__findings-label">Infos</span>
              </div>
            </div>

            {Object.keys(result.findings.byCode).length > 0 && (
              <div className="hd__findings-codes">
                <h4 className="hd__findings-codes-title">Top Issue Codes</h4>
                <ul className="hd__findings-codes-list">
                  {Object.entries(result.findings.byCode)
                    .sort(([, a], [, b]) => b - a)
                    .slice(0, 5)
                    .map(([code, count]) => (
                      <li key={code} className="hd__findings-code-item">
                        <span className="hd__findings-code">{code}</span>
                        <span className="hd__findings-code-count">{count}</span>
                      </li>
                    ))}
                </ul>
              </div>
            )}
          </div>

          {/* Score breakdown */}
          <div className="hd__breakdown-card">
            <h3 className="hd__section-title">Score Breakdown</h3>
            <div className="hd__breakdown-rows">
              <div className="hd__breakdown-row" data-type="base">
                <span className="hd__breakdown-label">Base Score</span>
                <span className="hd__breakdown-value">+{result.healthScore.breakdown.base}</span>
              </div>
              {result.healthScore.breakdown.errorPenalty < 0 && (
                <div className="hd__breakdown-row" data-type="error-penalty">
                  <span className="hd__breakdown-label">Error Penalty</span>
                  <span className="hd__breakdown-value">
                    {result.healthScore.breakdown.errorPenalty}
                  </span>
                </div>
              )}
              {result.healthScore.breakdown.warningPenalty < 0 && (
                <div className="hd__breakdown-row" data-type="warning-penalty">
                  <span className="hd__breakdown-label">Warning Penalty</span>
                  <span className="hd__breakdown-value">
                    {result.healthScore.breakdown.warningPenalty}
                  </span>
                </div>
              )}
              {result.healthScore.breakdown.irreversiblePenalty < 0 && (
                <div className="hd__breakdown-row" data-type="irreversible-penalty">
                  <span className="hd__breakdown-label">Irreversible Penalty</span>
                  <span className="hd__breakdown-value">
                    {result.healthScore.breakdown.irreversiblePenalty}
                  </span>
                </div>
              )}
              <div className="hd__breakdown-row hd__breakdown-row--total" data-type="total">
                <span className="hd__breakdown-label">Final Score</span>
                <span className="hd__breakdown-value">{result.healthScore.score}</span>
              </div>
            </div>
          </div>

          {/* Migration status table */}
          {result.migrations.length > 0 && (
            <div className="hd__migrations-card">
              <h3 className="hd__section-title">Migration Status</h3>
              <div className="hd__migrations-table-wrapper">
                <table className="hd__migrations-table">
                  <thead>
                    <tr>
                      <th>Filename</th>
                      <th>Status</th>
                      <th>Errors</th>
                      <th>Warnings</th>
                      <th>Destructive</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.migrations.map((mig) => (
                      <tr key={mig.filename} data-status={mig.status}>
                        <td className="hd__mig-filename">{mig.filename}</td>
                        <td>
                          <span
                            className="hd__mig-status"
                            data-status={mig.status}
                            title={`Status: ${STATUS_LABEL[mig.status]}`}
                          >
                            {STATUS_LABEL[mig.status]}
                          </span>
                        </td>
                        <td className="hd__mig-count">{mig.errors}</td>
                        <td className="hd__mig-count">{mig.warnings}</td>
                        <td>
                          {mig.hasDropTable && <span title="Contains DROP TABLE">🗑️ TABLE</span>}
                          {mig.hasDropColumn && (
                            <span title="Contains DROP COLUMN">
                              {mig.hasDropTable ? ' ' : ''}🗑️ COLUMN
                            </span>
                          )}
                          {!mig.hasDropTable && !mig.hasDropColumn && <span>—</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Recommendation callout */}
          <div className="hd__recommendation" data-grade={result.healthScore.grade}>
            <span className="hd__recommendation-icon">💡</span>
            <span className="hd__recommendation-text">{result.recommendation}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default HealthDashboard;
