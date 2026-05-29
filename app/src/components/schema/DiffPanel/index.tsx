import { useState } from 'react';

import type { DiffVersionsResult } from '@/bridge/cli';
import type { MigrationFile } from '@/core/local-types';
import type { SchemaGraph } from '@/core/types';

import { runDiff, CLI_AVAILABLE } from '@/bridge/cli';

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
      <p className="diff-panel__intro">
        Compare two schema states or migration versions and inspect structural changes.
      </p>

      <div className="diff-panel__controls">
        <label>
          Base version
          <select
            value={baseVersion}
            onChange={(e) => setBaseVersion(e.target.value)}
            className="diff-version-select"
          >
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
          <select
            value={targetVersion}
            onChange={(e) => setTargetVersion(e.target.value)}
            className="diff-version-select"
          >
            <option value="">Current state</option>
            {versions.map((m) => (
              <option key={m.version} value={m.version}>
                V{m.version}: {m.description}
              </option>
            ))}
          </select>
        </label>

        <button
          className="diff-run-btn"
          onClick={handleDiff}
          disabled={!canRun}
          aria-busy={loading}
        >
          {loading ? '⏳ Diffing…' : '▶ Diff'}
        </button>
      </div>

      {!CLI_AVAILABLE && (
        <div className="diff-panel__no-cli" role="alert">
          Diff requires the Python CLI — not available in pure-browser mode. Run the app in Tauri or
          the Vite dev server.
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
            V{result.versionA} → V{result.versionB}
          </h4>
          <div className="diff-stats-grid">
            <div>Tables added</div>
            <div>{result.stats.tablesAdded}</div>
            <div>Tables removed</div>
            <div>{result.stats.tablesRemoved}</div>
            <div>Tables modified</div>
            <div>{result.stats.tablesModified}</div>
            <div>Columns added</div>
            <div>{result.stats.columnsAdded}</div>
            <div>Columns removed</div>
            <div>{result.stats.columnsRemoved}</div>
            <div>Columns modified</div>
            <div>{result.stats.columnsModified}</div>
            <div>Sequences added</div>
            <div>{result.stats.sequencesAdded}</div>
            <div>Sequences removed</div>
            <div>{result.stats.sequencesRemoved}</div>
            <div>Relationships added</div>
            <div>{result.stats.relationshipsAdded}</div>
            <div>Relationships removed</div>
            <div>{result.stats.relationshipsRemoved}</div>
          </div>

          {result.stats.isBreaking ? (
            <div className="diff-results__breaking">⚠ Breaking changes detected</div>
          ) : (
            <div className="diff-results__safe">✓ No breaking removals detected</div>
          )}
        </div>
      )}
    </div>
  );
}
