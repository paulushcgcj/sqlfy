import { useState, useCallback } from 'react';

import type { FC } from 'react';

import { IS_TAURI, runGraphExport } from '@/bridge/cli';

import type { GraphExportOptions, GraphFormat } from '@/bridge/cli';
import type { MigrationFile } from '@/core/types';

import './index.scss';

// ── Constants ────────────────────────────────────────────────────────────────

const CLI_AVAILABLE = IS_TAURI || import.meta.env.DEV;
const CLI_MODE_LABEL = IS_TAURI ? '⚡ Tauri CLI' : import.meta.env.DEV ? '⚡ Dev CLI' : null;

interface FormatMeta {
  label: string;
  desc: string;
  ext: string;
  mime: string;
  badge?: string;
}

const FORMAT_META: Record<GraphFormat, FormatMeta> = {
  mermaid: {
    label: 'Mermaid ERD',
    desc: 'GitHub Markdown compatible',
    ext: 'mmd',
    mime: 'text/plain',
    badge: '★ GitHub',
  },
  dot: { label: 'Graphviz DOT', desc: 'Render with dot -Tsvg', ext: 'dot', mime: 'text/plain' },
  excalidraw: {
    label: 'Excalidraw',
    desc: 'Hand-drawn aesthetic, editable',
    ext: 'excalidraw',
    mime: 'application/json',
    badge: '✏ Editable',
  },
  drawio: {
    label: 'Draw.io',
    desc: 'Professional diagrams, editable',
    ext: 'drawio',
    mime: 'application/xml',
    badge: '✏ Editable',
  },
  summary: {
    label: 'Summary',
    desc: 'LLM-friendly text format',
    ext: 'txt',
    mime: 'text/plain',
  },
  json: {
    label: 'JSON',
    desc: 'NetworkX node-link format',
    ext: 'json',
    mime: 'application/json',
  },
  html: {
    label: 'Interactive HTML',
    desc: 'Standalone vis.js visualisation',
    ext: 'html',
    mime: 'text/html',
    badge: '⚡ Interactive',
  },
  report: {
    label: 'Report',
    desc: 'Human-readable Markdown report',
    ext: 'md',
    mime: 'text/markdown',
  },
};

const FORMATS = Object.keys(FORMAT_META) as GraphFormat[];

// ── Props ────────────────────────────────────────────────────────────────────

/** Props for the {@link GraphExportPanel} component. */
export interface GraphExportPanelProps {
  /** Migration files used as CLI input. */
  readonly files: MigrationFile[];
}

// ── Component ────────────────────────────────────────────────────────────────

/**
 * Graph Export panel — runs `sqlfy graph --format <fmt>` and shows the result.
 *
 * Supports all 8 CLI export formats: Mermaid, DOT, Excalidraw, Draw.io,
 * Summary, JSON, Interactive HTML, and Markdown Report.
 *
 * Requires the Python CLI (Tauri desktop or Vite dev server). Shows a notice
 * when the CLI is unavailable (pure-browser mode).
 *
 * @component
 * @param props - {@link GraphExportPanelProps}
 */
const GraphExportPanel: FC<GraphExportPanelProps> = ({ files }) => {
  const [format, setFormat] = useState<GraphFormat>('mermaid');
  const [title, setTitle] = useState('');
  const [resolution, setResolution] = useState<'low' | 'medium' | 'high'>('medium');
  const [noSplit, setNoSplit] = useState(false);
  const [atVersion, setAtVersion] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [loading, setLoading] = useState(false);
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleSelectFormat = useCallback((f: GraphFormat) => {
    setFormat(f);
    setContent(null);
    setError(null);
    setCopied(false);
  }, []);

  const handleGenerate = useCallback(async () => {
    setLoading(true);
    setError(null);
    setContent(null);
    setCopied(false);
    try {
      const opts: GraphExportOptions = { format, resolution };
      if (title.trim()) opts.title = title.trim();
      if (noSplit) opts.noSplit = true;
      const ver = parseInt(atVersion, 10);
      if (!isNaN(ver) && ver > 0) opts.atVersion = ver;
      const result = await runGraphExport(files, opts);
      setContent(result);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [files, format, title, resolution, noSplit, atVersion]);

  const handleDownload = useCallback(() => {
    if (!content) return;
    const meta = FORMAT_META[format];
    const blob = new Blob([content], { type: meta.mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `schema-graph.${meta.ext}`;
    a.click();
    URL.revokeObjectURL(url);
  }, [content, format]);

  const handleCopy = useCallback(async () => {
    if (!content) return;
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [content]);

  const handleOpenInTab = useCallback(() => {
    if (!content) return;
    const blob = new Blob([content], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');
    // Revoke after the tab has had time to load
    setTimeout(() => URL.revokeObjectURL(url), 15_000);
  }, [content]);

  // ── No-CLI notice ──────────────────────────────────────────────────────────

  if (!CLI_AVAILABLE) {
    return (
      <div className="gep">
        <div className="gep__no-cli">
          <p>Graph export requires the Python CLI.</p>
          <p>
            Run via <code>npx tauri dev</code> or start the Vite dev server with the CLI installed.
          </p>
        </div>
      </div>
    );
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="gep">
      {/* Header */}
      <div className="gep__header">
        <h2 className="gep__title">Graph Export</h2>
        {CLI_MODE_LABEL && <span className="gep__cli-badge">{CLI_MODE_LABEL}</span>}
      </div>

      {/* Format grid */}
      <div className="gep__formats">
        {FORMATS.map((f) => {
          const meta = FORMAT_META[f];
          return (
            <button
              key={f}
              className={`gep__fmt-btn${f === format ? ' active' : ''}`}
              onClick={() => handleSelectFormat(f)}
            >
              <span className="gep__fmt-label">{meta.label}</span>
              {meta.badge && <span className="gep__fmt-badge">{meta.badge}</span>}
              <span className="gep__fmt-desc">{meta.desc}</span>
            </button>
          );
        })}
      </div>

      {/* Advanced options */}
      <div className="gep__advanced">
        <button
          className="gep__adv-toggle"
          onClick={() => setShowAdvanced((p) => !p)}
          aria-expanded={showAdvanced}
        >
          {showAdvanced ? '▾' : '▸'} Advanced options
        </button>
        {showAdvanced && (
          <div className="gep__adv-body">
            <label className="gep__adv-row">
              <span>Title</span>
              <input
                className="gep__adv-input"
                type="text"
                placeholder="Diagram title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </label>
            <label className="gep__adv-row">
              <span>Resolution</span>
              <select
                className="gep__adv-select"
                value={resolution}
                onChange={(e) => setResolution(e.target.value as 'low' | 'medium' | 'high')}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </label>
            <label className="gep__adv-row">
              <span>At version</span>
              <input
                className="gep__adv-input"
                type="number"
                placeholder="e.g. 2"
                value={atVersion}
                min={1}
                onChange={(e) => setAtVersion(e.target.value)}
              />
            </label>
            <label className="gep__adv-row gep__adv-check">
              <input
                type="checkbox"
                checked={noSplit}
                onChange={(e) => setNoSplit(e.target.checked)}
              />
              <span>Don&apos;t split into subgraphs</span>
            </label>
          </div>
        )}
      </div>

      {/* Generate */}
      <button className="gep__run-btn" onClick={handleGenerate} disabled={loading}>
        {loading ? '⏳ Generating…' : `▶ Generate ${FORMAT_META[format].label}`}
      </button>

      {/* Error */}
      {error && <div className="gep__error">⚠ {error}</div>}

      {/* Loading hint */}
      {loading && <div className="gep__loading">Running CLI…</div>}

      {/* Result */}
      {content !== null && !loading && (
        <div className="gep__result">
          {/* Action bar */}
          <div className="gep__actions">
            <button className="gep__action-btn" onClick={handleCopy}>
              {copied ? '✓ Copied' : '⎘ Copy'}
            </button>
            <button className="gep__action-btn" onClick={handleDownload}>
              ↓ Download .{FORMAT_META[format].ext}
            </button>
            {format === 'html' && (
              <button className="gep__action-btn" onClick={handleOpenInTab}>
                ↗ Open in new tab
              </button>
            )}
            {format === 'mermaid' && (
              <a
                className="gep__action-btn"
                href="https://mermaid.live"
                target="_blank"
                rel="noopener noreferrer"
              >
                ↗ Preview on mermaid.live
              </a>
            )}
            {format === 'excalidraw' && (
              <a
                className="gep__action-btn"
                href="https://excalidraw.com"
                target="_blank"
                rel="noopener noreferrer"
              >
                ↗ Open Excalidraw (import file)
              </a>
            )}
            {format === 'drawio' && (
              <a
                className="gep__action-btn"
                href="https://app.diagrams.net"
                target="_blank"
                rel="noopener noreferrer"
              >
                ↗ Open Draw.io (import file)
              </a>
            )}
          </div>

          {/* Preview */}
          {format === 'html' ? (
            <iframe
              className="gep__html-preview"
              srcDoc={content}
              sandbox="allow-scripts"
              title="Schema graph interactive preview"
            />
          ) : (
            <pre className="gep__code">{content}</pre>
          )}
        </div>
      )}

      {/* Idle */}
      {content === null && !loading && !error && (
        <div className="gep__idle">
          Select a format and click <strong>Generate</strong> to export the schema graph.
        </div>
      )}
    </div>
  );
};

export default GraphExportPanel;
