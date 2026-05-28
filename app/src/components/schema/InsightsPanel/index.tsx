/**
 * InsightsPanel — dedicated schema quality analysis panel.
 *
 * Calls `sqlfy insights --format json` via the Tauri CLI or Vite dev-server
 * proxy. Requires an active CLI connection — pure-browser mode is not supported
 * and displays a clear "CLI required" message.
 *
 *  • Summary header with health score and grade
 *  • Severity filter checkboxes (Error / Warning / Info)
 *  • Category filter dropdown
 *  • Keyword search box
 *  • Expandable finding cards with full details and suggested fix
 */

import { useState, useCallback, useMemo } from 'react';

import type { InsightFinding, InsightsResult, InsightsOptions } from '@/bridge/cli';
import type { MigrationFile } from '@/core/types';
import type { FC } from 'react';

import { CLI_AVAILABLE, CLI_MODE_LABEL, runInsights } from '@/bridge/cli';
import './index.scss';

// ─── Types ────────────────────────────────────────────────────────────────────

type Severity = 'error' | 'warning' | 'info';

/** Props for the {@link InsightsPanel} component. */
export interface InsightsPanelProps {
  /** Raw migration files passed to the CLI. */
  readonly files: MigrationFile[];
}

// ─── Constants ────────────────────────────────────────────────────────────────

const ALL_SEVERITIES: Severity[] = ['error', 'warning', 'info'];

const SEV_LABEL: Record<Severity, string> = {
  error: '🔴 Error',
  warning: '🟡 Warning',
  info: '🔵 Info',
};

const GRADE_THRESHOLDS: [number, string, string][] = [
  [90, 'A', 'excellent'],
  [75, 'B', 'good'],
  [50, 'C', 'warning'],
  [0, 'D', 'critical'],
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function calcHealthScore(result: InsightsResult): number {
  const score =
    100 - result.summary.errors * 20 - result.summary.warnings * 5 - result.summary.infos;
  return Math.max(0, Math.min(100, score));
}

function getGrade(score: number): [string, string] {
  for (const [threshold, letter, label] of GRADE_THRESHOLDS) {
    if (score >= threshold) return [letter, label];
  }
  return ['D', 'critical'];
}

// ─── CLI availability detection ───────────────────────────────────────────────

// `CLI_AVAILABLE` and `CLI_MODE_LABEL` are exported from the bridge module.

// ─── FindingCard ──────────────────────────────────────────────────────────────

interface FindingCardProps {
  readonly finding: InsightFinding;
  readonly expanded: boolean;
  readonly onToggle: () => void;
}

/** Individual expandable finding card. */
function FindingCard({ finding, expanded, onToggle }: FindingCardProps) {
  const affected = [finding.table, finding.column].filter(Boolean).join('.');

  return (
    <div className={`ip-card ip-card--${finding.severity}`} data-expanded={expanded}>
      <button className="ip-card__header" onClick={onToggle} aria-expanded={expanded}>
        <span className={`ip-badge ip-badge--${finding.severity}`}>{finding.severity}</span>
        <span className="ip-card__code">{finding.code}</span>
        <span className="ip-card__msg">{finding.message}</span>
        {affected && <span className="ip-card__target">{affected}</span>}
        <span className="ip-card__chevron" aria-hidden>
          {expanded ? '▲' : '▼'}
        </span>
      </button>

      {expanded && (
        <div className="ip-card__body">
          {finding.detail && <p className="ip-card__detail">{finding.detail}</p>}
          {finding.fix && (
            <div className="ip-card__fix">
              <span className="ip-card__fix-label">Suggested fix:</span>
              <code className="ip-card__fix-code">{finding.fix}</code>
            </div>
          )}
          <div className="ip-card__meta">
            <span>Category: {finding.category}</span>
            {finding.table && <span>Table: {finding.table}</span>}
            {finding.column && <span>Column: {finding.column}</span>}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

/**
 * Full-featured schema insights panel with filtering, health score,
 * and expandable finding cards.
 *
 * Requires the Python CLI (Tauri or Vite dev-server). Pure-browser mode
 * is not supported — a "CLI required" notice is shown instead.
 *
 * @component
 * @param props - {@link InsightsPanelProps}
 */
const InsightsPanel: FC<InsightsPanelProps> = ({ files }) => {
  const [result, setResult] = useState<InsightsResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeSeverities, setActiveSeverities] = useState<Set<Severity>>(new Set(ALL_SEVERITIES));
  const [activeCategory, setActiveCategory] = useState<string>('');
  const [search, setSearch] = useState('');
  const [expandedSet, setExpandedSet] = useState<Set<string>>(new Set());

  // ── Run analysis ──

  const handleRun = useCallback(async () => {
    setLoading(true);
    setError(null);
    setExpandedSet(new Set());
    try {
      const opts: InsightsOptions = {};
      const analysisResult = await runInsights(files, opts);
      setResult(analysisResult);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [files]);

  // ── Derived data ──

  const allFindings = useMemo<InsightFinding[]>(() => {
    if (!result) return [];
    return [...result.findings.error, ...result.findings.warning, ...result.findings.info];
  }, [result]);

  const categories = useMemo<string[]>(() => {
    const set = new Set(allFindings.map((f) => f.category));
    return [...set].sort();
  }, [allFindings]);

  const filteredFindings = useMemo<InsightFinding[]>(() => {
    return allFindings.filter((f) => {
      if (!activeSeverities.has(f.severity)) return false;
      if (activeCategory && f.category !== activeCategory) return false;
      if (search) {
        const q = search.toLowerCase();
        return (
          f.message.toLowerCase().includes(q) ||
          f.code.toLowerCase().includes(q) ||
          (f.table ?? '').toLowerCase().includes(q) ||
          (f.column ?? '').toLowerCase().includes(q) ||
          (f.detail ?? '').toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [allFindings, activeSeverities, activeCategory, search]);

  const healthScore = result ? calcHealthScore(result) : null;
  const [grade, gradeLabel] = healthScore !== null ? getGrade(healthScore) : ['—', ''];

  // ── Handlers ──

  function toggleSeverity(sev: Severity) {
    setActiveSeverities((prev) => {
      const next = new Set(prev);
      if (next.has(sev)) {
        if (next.size === 1) return prev; // keep at least one active
        next.delete(sev);
      } else {
        next.add(sev);
      }
      return next;
    });
  }

  function toggleExpanded(key: string) {
    setExpandedSet((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function clearFilters() {
    setActiveSeverities(new Set(ALL_SEVERITIES));
    setActiveCategory('');
    setSearch('');
  }

  // ── No-CLI guard ──

  if (!CLI_AVAILABLE) {
    return (
      <div className="ip">
        <div className="ip__no-cli">
          <span className="ip__no-cli-icon">🔌</span>
          <p>
            <strong>CLI required</strong>
          </p>
          <p>
            Insights analysis requires the Python CLI. Run the app with <code>npx tauri dev</code>{' '}
            or <code>npm run dev</code> and ensure <code>sqlfy</code> is installed (
            <code>pip install -e cli/</code>).
          </p>
        </div>
      </div>
    );
  }

  // ── Render ──

  return (
    <div className="ip">
      {/* ── Header / controls ── */}
      <div className="ip__controls">
        <button className="ip__run-btn" onClick={handleRun} disabled={loading}>
          {loading ? '⏳ Running…' : '▶ Run Insights'}
        </button>
        {CLI_MODE_LABEL && <span className="ip__hint">{CLI_MODE_LABEL}</span>}

        {result && (
          <div className="ip__summary">
            <div
              className="ip__grade"
              data-grade={gradeLabel}
              title={`Health score: ${healthScore}/100`}
            >
              {grade}
            </div>
            <div className="ip__score">
              Score: <strong>{healthScore}</strong>/100
            </div>
            <div className="ip__health-bar">
              <div
                className="ip__health-fill"
                style={{ width: `${healthScore}%` }}
                data-grade={gradeLabel}
              />
            </div>
            <div className="ip__counts">
              {result.summary.errors > 0 && (
                <span className="ip__count" data-sev="error">
                  {result.summary.errors} errors
                </span>
              )}
              {result.summary.warnings > 0 && (
                <span className="ip__count" data-sev="warning">
                  {result.summary.warnings} warnings
                </span>
              )}
              {result.summary.infos > 0 && (
                <span className="ip__count" data-sev="info">
                  {result.summary.infos} info
                </span>
              )}
              {result.summary.total === 0 && (
                <span className="ip__count ip__count--clean">✓ No issues</span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Error ── */}
      {error && <div className="ip__error">⚠ {error}</div>}

      {/* ── Loading ── */}
      {loading && <div className="ip__loading">Running sqlfy insights…</div>}

      {/* ── Filter bar ── */}
      {result && !loading && (
        <div className="ip__filters" role="group" aria-label="Filter findings">
          <span className="ip__filter-label">Severity:</span>
          {ALL_SEVERITIES.map((sev) => (
            <label
              key={sev}
              className={`ip__sev-toggle${activeSeverities.has(sev) ? ' active' : ''}`}
              data-sev={sev}
            >
              <input
                type="checkbox"
                checked={activeSeverities.has(sev)}
                onChange={() => toggleSeverity(sev)}
                aria-label={SEV_LABEL[sev]}
              />
              {SEV_LABEL[sev]}
            </label>
          ))}

          <span className="ip__filter-sep" aria-hidden />

          <label htmlFor="ip-category" className="ip__filter-label">
            Category:
          </label>
          <select
            id="ip-category"
            className="ip__category-select"
            value={activeCategory}
            onChange={(e) => setActiveCategory(e.target.value)}
          >
            <option value="">All</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>

          <span className="ip__filter-sep" aria-hidden />

          <label htmlFor="ip-search" className="ip__filter-label">
            Search:
          </label>
          <input
            id="ip-search"
            className="ip__search"
            type="search"
            placeholder="keyword…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search findings"
          />

          <button className="ip__clear-btn" onClick={clearFilters} title="Clear all filters">
            ✕ Clear
          </button>

          <span className="ip__filter-result">
            {filteredFindings.length} of {allFindings.length}
          </span>
        </div>
      )}

      {/* ── Findings list ── */}
      {result && !loading && (
        <div className="ip__list">
          {filteredFindings.length === 0 && allFindings.length === 0 ? (
            <div className="ip__empty">
              <span className="ip__empty-icon">✅</span>
              <p>No issues found. Your schema looks great!</p>
            </div>
          ) : filteredFindings.length === 0 ? (
            <div className="ip__empty">
              <p>No findings match the current filters.</p>
              <button className="ip__clear-btn" onClick={clearFilters}>
                Clear filters
              </button>
            </div>
          ) : (
            ALL_SEVERITIES.filter((sev) => activeSeverities.has(sev)).map((sev) => {
              const group = filteredFindings.filter((f) => f.severity === sev);
              if (group.length === 0) return null;
              return (
                <section key={sev} className="ip__group">
                  <h3 className="ip__group-heading" data-sev={sev}>
                    {SEV_LABEL[sev]} <span className="ip__group-count">({group.length})</span>
                  </h3>
                  {group.map((finding, idx) => {
                    const cardKey = `${finding.severity}-${finding.code}-${idx}`;
                    return (
                      <FindingCard
                        key={cardKey}
                        finding={finding}
                        expanded={expandedSet.has(cardKey)}
                        onToggle={() => toggleExpanded(cardKey)}
                      />
                    );
                  })}
                </section>
              );
            })
          )}
        </div>
      )}

      {/* ── Initial idle state ── */}
      {!result && !loading && !error && (
        <div className="ip__idle">
          <p>Run insights to analyse your schema for quality issues.</p>
        </div>
      )}
    </div>
  );
};

export default InsightsPanel;
