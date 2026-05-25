import { useState } from 'react';
import { applyMigrations, buildChunks } from './core/core';
import { MigrationsTab } from './components/MigrationsTab';
import { GraphTab }      from './components/GraphTab';
import { LlmTab }        from './components/LlmTab';
import { SAMPLE_MIGRATIONS } from './data/samples';
import type { MigrationFile, SchemaGraph, VectorChunk } from './core/types';

type Tab = 'migrations' | 'graph' | 'llm';

export default function App() {
  const [files, setFiles]             = useState<MigrationFile[]>(SAMPLE_MIGRATIONS);
  const [graph, setGraph]             = useState<SchemaGraph | null>(null);
  const [chunks, setChunks]           = useState<VectorChunk[] | null>(null);
  const [activeTab, setActiveTab]     = useState<Tab>('migrations');
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [error, setError]             = useState<string | null>(null);

  function parse() {
    try {
      const g  = applyMigrations(files);
      const ch = buildChunks(g);
      setGraph(g);
      setChunks(ch);
      setSelectedTable([...g.tables.keys()][0] ?? null);
      setError(null);
      setActiveTab('graph');
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function switchTab(tab: Tab) {
    if (tab === 'graph' && !graph) return;
    if (tab === 'llm'   && !chunks) return;
    setActiveTab(tab);
  }

  return (
    <div className="shell">
      {/* Top bar */}
      <div className="topbar">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <circle cx="9" cy="9" r="8" stroke="#7c3aed" strokeWidth="1.2"/>
          <circle cx="9" cy="9" r="4" fill="#7c3aed" opacity=".4"/>
          <circle cx="9" cy="9" r="1.5" fill="#7c3aed"/>
        </svg>
        <span className="topbar-title">Schema Graph Engine</span>
        <span className="topbar-sub">Flyway → AST → Vector Context</span>
      </div>

      {/* Tab bar */}
      <div className="tabs">
        <button
          className={`tab${activeTab === 'migrations' ? ' active' : ''}`}
          onClick={() => switchTab('migrations')}
        >
          ① Migrations
        </button>
        <button
          className={`tab${activeTab === 'graph' ? ' active' : ''}${!graph ? ' disabled' : ''}`}
          onClick={() => switchTab('graph')}
        >
          ② Schema Graph
        </button>
        <button
          className={`tab${activeTab === 'llm' ? ' active' : ''}${!chunks ? ' disabled' : ''}`}
          onClick={() => switchTab('llm')}
        >
          ③ LLM Chunks
        </button>
        <button className="parse-btn" onClick={parse}>▶ Parse →</button>
      </div>

      {/* Error bar */}
      {error && <div className="err-bar">⚠ Parse error: {error}</div>}

      {/* Content */}
      <div className="content">
        {activeTab === 'migrations' && (
          <MigrationsTab files={files} onChange={setFiles} />
        )}
        {activeTab === 'graph' && graph && (
          <GraphTab
            graph={graph}
            selectedTable={selectedTable}
            onSelectTable={setSelectedTable}
          />
        )}
        {activeTab === 'llm' && chunks && (
          <LlmTab chunks={chunks} />
        )}
      </div>
    </div>
  );
}