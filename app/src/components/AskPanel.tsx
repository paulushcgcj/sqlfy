/**
 * sqlfy — src/components/AskPanel.tsx
 *
 * Natural language schema query panel.
 *
 * In Tauri mode:   spawns the Python CLI  `sqlfy ask --json-input … <question> --format json`
 * In browser mode: calls the Anthropic API directly (same RAG pipeline in TypeScript)
 *
 * Features
 * --------
 *  - Single-question mode with source attribution
 *  - Multi-turn chat with history context
 *  - Streaming responses token by token
 *  - Copy answer to clipboard
 *  - Keyboard shortcut: Enter to send, Shift+Enter for newline
 */

import { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { IS_TAURI } from '../bridge/cli';
import type { SchemaGraph, MigrationFile } from '../core/types';
import { buildChunks } from '../core/core';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Source {
  id:    string;
  title: string;
  score: number;
}

interface Message {
  id:       string;
  role:     'user' | 'assistant';
  text:     string;
  sources?: Source[];
  loading?: boolean;
}

interface Props {
  graph:  SchemaGraph | null;
  files:  MigrationFile[];
}

// ─── Anthropic API (browser mode) ────────────────────────────────────────────

const SYSTEM_PROMPT = `You are a database schema expert assistant called sqlfy.

You have been given schema context chunks extracted from Flyway SQL migration files.

Rules:
- Answer ONLY based on the provided schema context. Do not invent tables, columns, or relationships.
- Be precise about column types, constraints (PK, FK, NOT NULL, UNIQUE), and FK relationships.
- If the answer cannot be determined from the context, say so clearly.
- Use backticks for table/column names. Use the fully-qualified name (e.g. \`APP.USERS\`).
- Keep answers concise — one to three paragraphs unless a detailed breakdown is requested.`;

async function* streamAsk(
  question:  string,
  chunks:    ReturnType<typeof buildChunks>,
  history:   { role: string; content: string }[],
  k = 6,
): AsyncGenerator<{ token?: string; sources?: Source[] }> {
  const apiKey = import.meta.env.VITE_ANTHROPIC_API_KEY as string | undefined;
  if (!apiKey) {
    throw new Error(
      'VITE_ANTHROPIC_API_KEY is not set. ' +
      'Add it to your .env file: VITE_ANTHROPIC_API_KEY=sk-ant-…'
    );
  }
  // ── Client-side BM25 retrieval ──────────────────────────────────────
  const stop = new Set([
    'a','an','the','is','are','was','be','have','has','do','does',
    'to','of','in','on','at','by','for','with','from','and','or',
    'not','this','that','what','which','how','table','column',
  ]);

  function tokenise(text: string): string[] {
    return text.toLowerCase().match(/[a-z][a-z0-9_]*/g)
      ?.filter(t => !stop.has(t) && t.length > 1) ?? [];
  }

  const qTokens = tokenise(question);
  const N = chunks.length;

  const docs = chunks.map(c => {
    const text = `${c.title} ${c.hint} ${c.title} ${c.hint} ${c.content}`;
    const tokens = tokenise(text);
    const tf: Record<string, number> = {};
    tokens.forEach(t => { tf[t] = (tf[t] ?? 0) + 1; });
    return { tf, length: Math.max(tokens.length, 1) };
  });

  const avgLen = docs.reduce((s, d) => s + d.length, 0) / Math.max(N, 1);

  const df: Record<string, number> = {};
  docs.forEach(d => Object.keys(d.tf).forEach(t => { df[t] = (df[t] ?? 0) + 1; }));

  const K1 = 1.5, B = 0.75;
  const scores = docs.map((doc, i) => {
    let score = 0;
    qTokens.forEach(t => {
      if (!doc.tf[t]) return;
      const tf  = doc.tf[t];
      const idf = Math.log((N - (df[t] ?? 0) + 0.5) / ((df[t] ?? 0) + 0.5) + 1);
      const num = tf * (K1 + 1);
      const den = tf + K1 * (1 - B + B * doc.length / avgLen);
      score    += idf * num / den;
    });
    return { score, i };
  });

  const hits = scores
    .filter(s => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, k)
    .map(s => ({
      id:    chunks[s.i].id,
      title: chunks[s.i].title,
      score: Math.round(s.score * 1000) / 1000,
      content: chunks[s.i].content,
      hint:    chunks[s.i].hint,
    }));

  yield { sources: hits.map(h => ({ id: h.id, title: h.title, score: h.score })) };

  // ── Build context prompt ────────────────────────────────────────────
  const ctxParts = hits.map((h, i) =>
    `### Context ${i + 1}: ${h.title}\n*${h.hint}*\n\`\`\`\n${h.content}\n\`\`\``
  );
  const userContent = `## Schema Context\n\n${ctxParts.join('\n\n')}\n\n---\n## Question\n\n${question}`;

  const messages = [
    ...history,
    { role: 'user', content: userContent },
  ];

  // ── Stream from Anthropic ───────────────────────────────────────────
  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type':      'application/json',
      'x-api-key':         apiKey,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model:      'claude-sonnet-4-20250514',
      max_tokens: 1024,
      system:     SYSTEM_PROMPT,
      messages,
      stream:     true,
    }),
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`API error ${response.status}: ${err}`);
  }

  const reader  = response.body!.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const lines = decoder.decode(value).split('\n');
    for (const line of lines) {
      if (!line.startsWith('data:')) continue;
      const data = line.slice(5).trim();
      if (data === '[DONE]') return;
      try {
        const event = JSON.parse(data);
        if (event.type === 'content_block_delta' &&
            event.delta?.type === 'text_delta') {
          yield { token: event.delta.text };
        }
      } catch { /* ignore malformed SSE lines */ }
    }
  }
}

// ─── Tauri mode: delegate to Python CLI ───────────────────────────────────────

async function askViaCli(
  question: string,
  files:    MigrationFile[],
): Promise<{ answer: string; sources: Source[] }> {
  const { Command }           = await import('@tauri-apps/plugin-shell');
  const { writeTextFile, remove } = await import('@tauri-apps/plugin-fs');
  const { tempDir, join }     = await import('@tauri-apps/api/path');

  const tmp = await join(await tempDir(), `sqlfy-input-${Date.now()}.json`);
  await writeTextFile(tmp, JSON.stringify(files));

  try {
    const output = await Command.create('python3', [
      '../cli/main.py', 'ask',
      '--json-input', tmp,
      '--format', 'json',
      '--no-sources',
      question,
    ]).execute();

    if (output.code !== 0) throw new Error(output.stderr);
    const result = JSON.parse(output.stdout);
    return {
      answer:  result.answer,
      sources: result.sources ?? [],
    };
  } finally {
    await remove(tmp).catch(() => {});
  }
}

// ─── Component ────────────────────────────────────────────────────────────────

export function AskPanel({ graph, files }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput]       = useState('');
  const [busy, setBusy]         = useState(false);
  const [copied, setCopied]     = useState<string | null>(null);
  const bottomRef               = useRef<HTMLDivElement>(null);
  const textareaRef             = useRef<HTMLTextAreaElement>(null);

  // History for multi-turn (browser mode)
  const historyRef = useRef<{ role: string; content: string }[]>([]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (!graph) {
    return (
      <div className="no-data" style={{ height: '100%' }}>
        <svg width="24" height="24" fill="none" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="10" stroke="var(--color-border-secondary)" strokeWidth="1.2"/>
          <path d="M12 8v4M12 16h.01" stroke="var(--color-border-secondary)" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
        Parse your migrations first to enable schema queries.
      </div>
    );
  }

  async function send() {
    const question = input.trim();
    if (!question || busy) return;

    setInput('');
    setBusy(true);

    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', text: question };
    const asstMsg: Message = { id: crypto.randomUUID(), role: 'assistant', text: '', loading: true };

    setMessages(prev => [...prev, userMsg, asstMsg]);

    try {
      if (IS_TAURI) {
        // Tauri: delegate to Python CLI
        const { answer, sources } = await askViaCli(question, files);
        setMessages(prev => prev.map(m =>
          m.id === asstMsg.id ? { ...m, text: answer, sources, loading: false } : m
        ));
      } else {
        // Browser: stream directly from Anthropic API
        let sources: Source[] | undefined;
        let text = '';

        const chunks = buildChunks(graph);
        for await (const chunk of streamAsk(question, chunks, historyRef.current)) {
          if (chunk.sources) {
            sources = chunk.sources;
            setMessages(prev => prev.map(m =>
              m.id === asstMsg.id ? { ...m, sources, loading: true } : m
            ));
          }
          if (chunk.token) {
            text += chunk.token;
            setMessages(prev => prev.map(m =>
              m.id === asstMsg.id ? { ...m, text, loading: true } : m
            ));
          }
        }

        setMessages(prev => prev.map(m =>
          m.id === asstMsg.id ? { ...m, text, sources, loading: false } : m
        ));

        // Append to multi-turn history
        historyRef.current = [
          ...historyRef.current,
          { role: 'user',      content: question },
          { role: 'assistant', content: text },
        ].slice(-20); // keep last 10 turns
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setMessages(prev => prev.map(m =>
        m.id === asstMsg.id ? { ...m, text: `⚠ Error: ${msg}`, loading: false } : m
      ));
    } finally {
      setBusy(false);
      textareaRef.current?.focus();
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  function copyMessage(text: string, id: string) {
    navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 1800);
  }

  function clearHistory() {
    setMessages([]);
    historyRef.current = [];
  }

  return (
    <div className="ask-panel">
      {/* Header */}
      <div className="ask-header">
        <span className="ask-title">Schema Q&amp;A</span>
        <span className="ask-subtitle">
          {IS_TAURI ? '⚡ CLI mode' : '🌐 Browser mode'} ·{' '}
          {graph.tables.size} tables · {graph.edges.length} FK edges
        </span>
        {messages.length > 0 && (
          <button className="ask-clear" onClick={clearHistory}>Clear</button>
        )}
      </div>

      {/* Message list */}
      <div className="ask-messages">
        {messages.length === 0 && (
          <div className="ask-empty">
            <div className="ask-empty-icon">◆</div>
            <div className="ask-empty-title">Ask anything about your schema</div>
            <div className="ask-empty-examples">
              {[
                'Which tables cascade delete from users?',
                'What indexes exist on the orders table?',
                'Which columns are nullable foreign keys?',
                'What tables have no primary key?',
                'How are orders and products related?',
              ].map(ex => (
                <button
                  key={ex}
                  className="ask-example"
                  onClick={() => { setInput(ex); textareaRef.current?.focus(); }}
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={`ask-msg ask-msg--${msg.role}`}>
            <div className="ask-msg-role">
              {msg.role === 'user' ? '?' : '◆'}
            </div>
            <div className="ask-msg-body">
              {/* Sources */}
              {msg.sources && msg.sources.length > 0 && (
                <div className="ask-sources">
                  {msg.sources.map(s => (
                    <span key={s.id} className="ask-source-tag" title={`score: ${s.score}`}>
                      {s.title}
                    </span>
                  ))}
                </div>
              )}

              {/* Text — preserve line breaks */}
              <div className="ask-msg-text">
                {msg.loading && !msg.text
                  ? <span className="ask-cursor">▋</span>
                  : msg.text.split('\n').map((line, i) => (
                      <span key={i}>{line}{i < msg.text.split('\n').length - 1 ? <br/> : null}</span>
                    ))
                }
                {msg.loading && msg.text && <span className="ask-cursor">▋</span>}
              </div>

              {/* Copy button */}
              {!msg.loading && msg.role === 'assistant' && msg.text && (
                <button
                  className={`ask-copy${copied === msg.id ? ' ok' : ''}`}
                  onClick={() => copyMessage(msg.text, msg.id)}
                >
                  {copied === msg.id ? 'Copied!' : 'Copy'}
                </button>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="ask-input-row">
        <textarea
          ref={textareaRef}
          className="ask-textarea"
          placeholder="Ask a question about your schema… (Enter to send, Shift+Enter for newline)"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
          disabled={busy}
        />
        <button
          className="ask-send"
          onClick={send}
          disabled={busy || !input.trim()}
        >
          {busy ? '⏳' : '▶'}
        </button>
      </div>
    </div>
  );
}