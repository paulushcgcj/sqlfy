/**
 * sqlfy — src/components/schema/AskPanel/index.tsx
 *
 * Schema context assembler for AI assistants.
 *
 * Runs client-side BM25 retrieval to find the most relevant schema chunks
 * for a question, formats a ready-to-paste prompt, and copies it to the
 * clipboard. No API keys, no external calls, works fully offline.
 *
 * Paste the result into VS Code Copilot Chat, Claude.ai, ChatGPT, or any
 * other AI assistant.
 *
 * Features
 * --------
 *  - BM25 keyword retrieval (title/hint 3× boosted) over schema chunks
 *  - Prompt preview with scrollable formatted output
 *  - Copy-to-clipboard with confirmation
 *  - Example question prompts
 *  - Keyboard shortcut: Enter to assemble, Shift+Enter for newline
 */

import { useState, useRef } from 'react';

import type { VectorChunk } from '@/core/types';
import type { FC, KeyboardEvent } from 'react';
import './index.scss';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Source {
  id: string;
  title: string;
  score: number;
}

interface Hit {
  id: string;
  title: string;
  score: number;
  content: string;
  hint: string;
}

/** Props for the {@link AskPanel} component. */
export interface AskPanelProps {
  /**
   * Precomputed retrieval chunks from the app-level `chunks` state.
   * When empty, the panel renders an empty-state prompt to parse first.
   */
  readonly chunks: VectorChunk[];
}

// ─── BM25 retrieval ───────────────────────────────────────────────────────────

const _STOP = new Set([
  'a',
  'an',
  'the',
  'is',
  'are',
  'was',
  'be',
  'have',
  'has',
  'do',
  'does',
  'to',
  'of',
  'in',
  'on',
  'at',
  'by',
  'for',
  'with',
  'from',
  'and',
  'or',
  'not',
  'this',
  'that',
  'what',
  'which',
  'how',
  'table',
  'column',
]);

function _tokenise(text: string): string[] {
  return (
    text
      .toLowerCase()
      .match(/[a-z][a-z0-9_]*/g)
      ?.filter((t) => !_STOP.has(t) && t.length > 1) ?? []
  );
}

function retrieve(question: string, chunks: VectorChunk[], k = 6): Hit[] {
  const qTokens = _tokenise(question);
  const N = chunks.length;

  const docs = chunks.map((c) => {
    const text = `${c.title} ${c.hint} ${c.title} ${c.hint} ${c.content}`;
    const tokens = _tokenise(text);
    const tf: Record<string, number> = {};
    tokens.forEach((t) => {
      tf[t] = (tf[t] ?? 0) + 1;
    });
    return { tf, length: Math.max(tokens.length, 1) };
  });

  const avgLen = docs.reduce((s, d) => s + d.length, 0) / Math.max(N, 1);

  const df: Record<string, number> = {};
  docs.forEach((d) =>
    Object.keys(d.tf).forEach((t) => {
      df[t] = (df[t] ?? 0) + 1;
    }),
  );

  const K1 = 1.5,
    B = 0.75;
  const scores = docs.map((doc, i) => {
    let score = 0;
    qTokens.forEach((t) => {
      if (!doc.tf[t]) return;
      const tf = doc.tf[t];
      const idf = Math.log((N - (df[t] ?? 0) + 0.5) / ((df[t] ?? 0) + 0.5) + 1);
      score += (idf * (tf * (K1 + 1))) / (tf + K1 * (1 - B + (B * doc.length) / avgLen));
    });
    return { score, i };
  });

  return scores
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, k)
    .map((s) => ({
      id: chunks[s.i].id,
      title: chunks[s.i].title,
      score: Math.round(s.score * 1000) / 1000,
      content: chunks[s.i].content,
      hint: chunks[s.i].hint,
    }));
}

// ─── Prompt builder ───────────────────────────────────────────────────────────

const _INSTRUCTIONS = `You are a database schema expert. \
Answer the question based only on the schema context provided below. \
Do not invent tables, columns, or relationships that are not in the context. \
Use backticks for table/column names and always use the fully-qualified name \
(e.g. \`APP.USERS\`). If the answer cannot be determined from the context, say so.`;

function buildPrompt(question: string, hits: Hit[]): string {
  const ctx = hits
    .map((h, i) => `### Context ${i + 1}: ${h.title}\n*${h.hint}*\n\`\`\`\n${h.content}\n\`\`\``)
    .join('\n\n');

  return [
    _INSTRUCTIONS,
    '',
    '## Schema Context',
    '',
    ctx,
    '',
    '---',
    '',
    '## Question',
    '',
    question,
  ].join('\n');
}

// ─── Component ────────────────────────────────────────────────────────────────

const EXAMPLES = [
  'Which tables have cascading deletes?',
  'What indexes exist across all tables?',
  'Which columns are nullable foreign keys?',
  'What tables have no primary key?',
  'How are the main tables related to each other?',
];

/**
 * Schema Q&A panel that assembles a ready-to-paste AI prompt.
 *
 * Runs BM25 retrieval over schema chunks to select relevant context, then
 * formats a structured prompt for any AI assistant. Fully offline — no API calls.
 *
 * @component
 * @example
 * ```tsx
 * <AskPanel graph={graph} />
 * ```
 * @param props - {@link AskPanelProps}
 * @returns The Q&A panel, or an empty-state prompt if `graph` is `null`.
 */
const AskPanel: FC<AskPanelProps> = ({ chunks }) => {
  const [input, setInput] = useState('');
  const [sources, setSources] = useState<Source[]>([]);
  const [prompt, setPrompt] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  if (!chunks || chunks.length === 0) {
    return (
      <div className="no-data" style={{ height: '100%' }}>
        <svg width="24" height="24" fill="none" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="10" stroke="var(--border)" strokeWidth="1.2" />
          <path
            d="M12 8v4M12 16h.01"
            stroke="var(--border)"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
        Parse your migrations first to enable schema queries.
      </div>
    );
  }

  function assemble() {
    const question = input.trim();
    if (!question) return;
    const hits = retrieve(question, chunks);
    const built = buildPrompt(question, hits);

    setSources(hits.map((h) => ({ id: h.id, title: h.title, score: h.score })));
    setPrompt(built);
    setCopied(false);
  }

  function copy() {
    if (!prompt) return;
    navigator.clipboard.writeText(prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      assemble();
    }
  }

  function reset() {
    setPrompt(null);
    setSources([]);
    setInput('');
    textareaRef.current?.focus();
  }

  return (
    <div className="ask-panel">
      {/* Header */}
      <div className="ask-header">
        <span className="ask-title">Schema Q&amp;A</span>
        <span className="ask-subtitle">Assembles a schema context prompt for any AI assistant</span>
      </div>

      {/* Input */}
      <div className="ask-input-row">
        <textarea
          ref={textareaRef}
          className="ask-textarea"
          placeholder="Ask a question about your schema… (Enter to assemble, Shift+Enter for newline)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
        />
        <button
          className="ask-send"
          onClick={assemble}
          disabled={!input.trim()}
          title="Assemble context prompt"
        >
          ▶
        </button>
      </div>

      {/* Empty state */}
      {!prompt && (
        <div className="ask-empty">
          <div className="ask-empty-icon">◆</div>
          <div className="ask-empty-title">Ask anything about your schema</div>
          <div className="ask-empty-hint">
            Retrieves the most relevant schema chunks and formats a prompt ready to paste into VS
            Code Copilot Chat, Claude.ai, or any AI assistant.
          </div>
          <div className="ask-empty-examples">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                className="ask-example"
                onClick={() => {
                  setInput(ex);
                  textareaRef.current?.focus();
                }}
              >
                {ex}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Result */}
      {prompt && (
        <div className="ask-result">
          {/* Source chips */}
          {sources.length > 0 && (
            <div className="ask-sources-row">
              <span className="ask-sources-label">
                Retrieved {sources.length} chunk{sources.length !== 1 ? 's' : ''}:
              </span>
              {sources.map((s) => (
                <span key={s.id} className="ask-source-tag" title={`relevance: ${s.score}`}>
                  {s.title}
                </span>
              ))}
            </div>
          )}

          {/* Prompt preview + actions */}
          <div className="ask-prompt-box">
            <div className="ask-prompt-header">
              <span className="ask-prompt-label">Ready-to-paste prompt</span>
              <div className="ask-prompt-actions">
                <button className={`ask-copy-btn${copied ? ' ok' : ''}`} onClick={copy}>
                  {copied ? '✓ Copied!' : 'Copy for AI'}
                </button>
                <button className="ask-reset-btn" onClick={reset}>
                  New question
                </button>
              </div>
            </div>
            <pre className="ask-prompt-preview">{prompt}</pre>
          </div>

          <div className="ask-hint">
            Paste into VS Code Copilot Chat, Claude.ai, ChatGPT, or any AI assistant.
          </div>
        </div>
      )}
    </div>
  );
};

export default AskPanel;
