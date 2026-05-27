import { useState, useCallback } from 'react';
import type { FC } from 'react';

import type { DumpFormat, DumpOptions } from '@/bridge/cli';
import type { MigrationFile, SchemaGraph } from '@/core/types';

import { dumpWithOptions, CLI_AVAILABLE, CLI_MODE_LABEL } from '@/bridge/cli';
import { downloadBlob, copyToClipboard } from '@/utils/io';
import { browserDump, browserDumpYaml, browserDumpSummary } from './browser-fallbacks';
import './index.scss';

interface DumpPanelProps {
  files: MigrationFile[];
  graph: SchemaGraph;
}

const DumpPanel: FC<DumpPanelProps> = ({ files, graph }) => {
  const [dumpOutput, setDumpOutput] = useState<string | null>(null);
  const [dumpLoading, setDumpLoading] = useState(false);
  const [dumpError, setDumpError] = useState<string | null>(null);
  const [dumpCopied, setDumpCopied] = useState(false);
  const [dumpFormat, setDumpFormat] = useState<DumpFormat>('json');
  const [dumpAtVersion, setDumpAtVersion] = useState<number | undefined>(undefined);
  const isCliLocal = CLI_AVAILABLE;

  const handleDump = useCallback(async () => {
    setDumpLoading(true);
    setDumpError(null);
    try {
      let out: string;
      if (isCliLocal) {
        const options: DumpOptions = { format: dumpFormat };
        if (dumpAtVersion !== undefined) options.atVersion = dumpAtVersion;
        out = await dumpWithOptions(files, options);
      } else {
        if (dumpFormat === 'json') out = browserDump(graph);
        else if (dumpFormat === 'yaml') out = browserDumpYaml(graph);
        else out = browserDumpSummary(graph);
      }
      setDumpOutput(out);
    } catch (err) {
      setDumpError((err as Error).message);
      if (dumpFormat === 'json') setDumpOutput(browserDump(graph));
      else if (dumpFormat === 'yaml') setDumpOutput(browserDumpYaml(graph));
      else setDumpOutput(browserDumpSummary(graph));
    } finally {
      setDumpLoading(false);
    }
  }, [files, graph, dumpFormat, dumpAtVersion]);

  async function copyText(text: string, setCopied: (v: boolean) => void) {
    const ok = await copyToClipboard(text);
    if (!ok) return;
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  const extMap: Record<DumpFormat, string> = { json: 'json', yaml: 'yaml', summary: 'txt' };
  const mimeMap: Record<DumpFormat, string> = {
    json: 'application/json',
    yaml: 'application/x-yaml',
    summary: 'text/plain',
  };

  return (
    <div className="schema-panel">
      <div className="schema-panel-actions">
        <select
          className="schema-fmt-select"
          value={dumpFormat}
          onChange={(e) => {
            setDumpFormat(e.target.value as DumpFormat);
            setDumpOutput(null);
          }}
        >
          <option value="json">JSON</option>
          <option value="yaml">YAML</option>
          <option value="summary">Summary</option>
        </select>
        <select
          className="schema-version-select"
          value={dumpAtVersion ?? ''}
          onChange={(e) => {
            const val = e.target.value;
            setDumpAtVersion(val === '' ? undefined : parseInt(val, 10));
            setDumpOutput(null);
          }}
          title="Export state at specific migration version"
        >
          <option value="">Current state</option>
          {graph.migHist.map((m) => (
            <option key={m.version} value={m.version}>
              V{m.version}: {m.description}
            </option>
          ))}
        </select>
        <button className="schema-run-btn" onClick={handleDump} disabled={dumpLoading}>
          {dumpLoading ? '⏳ Running…' : '▶ Run dump'}
        </button>
        <button
          className={`schema-copy-btn${dumpCopied ? ' copied' : ''}`}
          onClick={() => dumpOutput && copyText(dumpOutput, setDumpCopied)}
          disabled={!dumpOutput}
        >
          {dumpCopied ? '✓ Copied' : '⎘ Copy'}
        </button>
        <button
          className="schema-dl-btn"
          onClick={() =>
            dumpOutput && downloadBlob(dumpOutput, `schema_state.${extMap[dumpFormat]}`, mimeMap[dumpFormat])
          }
          disabled={!dumpOutput}
        >
          ⬇ Download
        </button>
        <span className="schema-hint">{CLI_MODE_LABEL ?? (isCliLocal ? '⚡ CLI' : '🌐 Browser fallback')}</span>
      </div>

      {dumpError && <div className="schema-error">⚠ CLI error (showing browser fallback): {dumpError}</div>}

      {dumpLoading && <div className="schema-loading">Running sqlfy dump…</div>}

      {dumpOutput && !dumpLoading && (
        <div className="schema-output">
          <pre>{dumpOutput}</pre>
        </div>
      )}
    </div>
  );
};

export default DumpPanel;
