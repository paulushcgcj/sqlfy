import { useState } from 'react';

import { runDiff, CLI_AVAILABLE } from '@/bridge/cli';
import type { MigrationFile, SchemaGraph } from '@/core/types';
import type { DiffVersionsResult } from '@/bridge/cli';

import './index.scss';

interface DiffPanelProps {
  files: MigrationFile[];
  graph: SchemaGraph | null;
}

export default function DiffPanel({ files, graph }: DiffPanelProps) {
  const [baseVersion, setBaseVersion] = useState('');
  const [targetVersion, setTargetVersion] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DiffVersionsResult | null>(null);

  async function handleDiff() {
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const res = await runDiff(files, {
        fromVersion: baseVersion || undefined,
        toVersion: targetVersion || undefined,
      });
      setResult(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const versions = graph?.migHist ?? [];
  const canRun = CLI_AVAILABLE && !loading;

  return (
    <div className="diff-panel">
      <p className="diff-panel__intro">Compare two schema states or migration versions and inspect structural changes.</p>

      <div className="diff-panel__controls">
        <label>
          Base version
          <select value={baseVersion} onChange={(e) => setBaseVersion(e.target.value)} className="diff-version-select">
            <option value="">Current state</option>
            {versions.map((m) => (
              <option key={m.version} value={m.version}>
                V{m.version}: {m.description}
              </option>
            ))}
          </select>
        </label>

        <label>
          Target version
          <select value={targetVersion} onChange={(e) => setTargetVersion(e.target.value)} className="diff-version-select">
            <option value="">Current state</option>
            {versions.map((m) => (
              <option key={m.version} value={m.version}>
                V{m.version}: {m.description}
              </option>
            ))}
          </select>
        </label>

        <button className="diff-run-btn" onClick={handleDiff} disabled={!canRun} aria-busy={loading}>
          {loading ? '⏳ Diffing…' : '▶ Diff'}
        </button>
      </div>

      {!CLI_AVAILABLE && (
        <div className="diff-panel__no-cli" role="alert">
          Diff requires the Python CLI — not available in pure-browser mode. Run the app in Tauri or the Vite dev server.
        </div>
      )}

      {error && (
        <div className="diff-panel__error" role="alert">
          ⚠ {error}
        </div>
      )}

      {result && (
        <div className="diff-results">
          <h4>
            V{result.version_a} → V{result.version_b}
          </h4>
          <div className="diff-stats-grid">
            <div>Tables added</div>
            <div>{result.stats.tables_added}</div>
            <div>Tables removed</div>
            <div>{result.stats.tables_removed}</div>
            <div>Tables modified</div>
            <div>{result.stats.tables_modified}</div>
            <div>Columns added</div>
            <div>{result.stats.columns_added}</div>
            <div>Columns removed</div>
            <div>{result.stats.columns_removed}</div>
            <div>Columns modified</div>
            <div>{result.stats.columns_modified}</div>
            <div>Sequences added</div>
            <div>{result.stats.sequences_added}</div>
            <div>Sequences removed</div>
            <div>{result.stats.sequences_removed}</div>
            <div>Relationships added</div>
            <div>{result.stats.relationships_added}</div>
            <div>Relationships removed</div>
            <div>{result.stats.relationships_removed}</div>
          </div>

          {result.stats.is_breaking ? (
            <div className="diff-results__breaking">⚠ Breaking changes detected</div>
          ) : (
            <div className="diff-results__safe">✓ No breaking removals detected</div>
          )}
        </div>
      )}
    </div>
  );
}

