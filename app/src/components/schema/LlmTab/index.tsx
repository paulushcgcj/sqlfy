import { useState } from 'react';

import type { VectorChunk } from '@/core/types';
import type { FC } from 'react';

import { downloadBlob, copyToClipboard } from '@/utils/io';
import './index.scss';

/** Props for the {@link LlmTab} component. */
export interface LlmTabProps {
  /** The vector chunks generated from the parsed schema. */
  readonly chunks: VectorChunk[];
}

/**
 * LLM context tab for browsing and exporting vector chunks.
 *
 * Presents a sidebar list of schema chunks and a detail panel with copyable content.
 * Supports bulk JSON export for external embedding pipelines.
 *
 * @component
 * @example
 * ```tsx
 * <LlmTab chunks={chunks} />
 * ```
 * @param props - {@link LlmTabProps}
 * @returns A split-panel layout with chunk list and detail view.
 */
const LlmTab: FC<LlmTabProps> = ({ chunks }) => {
  const [selected, setSelected] = useState<VectorChunk>(chunks[0]);
  const [copied, setCopied] = useState(false);

  function exportJson() {
    const json = JSON.stringify(
      chunks.map((c) => ({
        id: c.id,
        type: c.type,
        title: c.title,
        content: c.content,
        metadata: c.meta,
      })),
      null,
      2,
    );
    downloadBlob(json, 'schema_vector_chunks.json', 'application/json');
  }

  async function copyContent() {
    const ok = await copyToClipboard(selected.content);
    if (!ok) return;
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  return (
    <div className="split">
      {/* Sidebar */}
      <div className="sidebar">
        <button className="export-btn" onClick={exportJson}>
          ⬇ Export all JSON
        </button>
        <div className="sbar-sect">Chunks ({chunks.length})</div>
        {chunks.map((chunk) => (
          <button
            key={chunk.id}
            className={`sbar-item${chunk.id === selected?.id ? ' active' : ''}`}
            onClick={() => setSelected(chunk)}
          >
            {chunk.title}
            <div className="sub">
              {chunk.type} · {chunk.content.length} chars
            </div>
          </button>
        ))}
      </div>

      {/* Main */}
      <div className="main">
        {selected && (
          <>
            <div className="chunk-hdr">
              <span className="chunk-title">{selected.title}</span>
              <span className="chunk-type-badge">{selected.type}</span>
              <button className={`copy-btn${copied ? ' ok' : ''}`} onClick={copyContent}>
                {copied ? 'Copied!' : 'Copy content'}
              </button>
            </div>
            <div style={{ padding: '14px 20px' }}>
              <div className="chunk-hint">💡 {selected.hint}</div>
              <div className="chunk-content">{selected.content}</div>
              <div className="chunk-meta-label">Metadata</div>
              <div className="chunk-meta">{JSON.stringify(selected.meta, null, 2)}</div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default LlmTab;
