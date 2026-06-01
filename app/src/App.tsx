import { useState, Activity } from 'react';

import { parse, IS_TAURI } from './bridge/cli';
import { pickFolder, readMigrations, type FolderHandle } from './bridge/folder';
import AskPanel from './components/schema/AskPanel';
import DiffPanel from './components/schema/DiffPanel';
import GraphExportPanel from './components/schema/GraphExportPanel';
import GraphTab from './components/schema/GraphTab';
import HealthDashboard from './components/schema/HealthDashboard';
import InsightsPanel from './components/schema/InsightsPanel';
import LlmTab from './components/schema/LlmTab';
import MigrationsTab from './components/schema/MigrationsTab';
import SchemaTab from './components/schema/SchemaTab';
import SimulatePanel from './components/schema/SimulatePanel';
import { SAMPLE_MIGRATIONS } from './data/samples';

import type { MigrationFile, SchemaGraph, VectorChunk } from './core/types';

type Tab =
  | 'migrations'
  | 'graph'
  | 'llm'
  | 'ask'
  | 'schema'
  | 'insights'
  | 'graph-export'
  | 'health'
  | 'simulate'
  | 'diff';

export default function App() {
  const [files, setFiles] = useState<MigrationFile[]>(SAMPLE_MIGRATIONS);
  const [graph, setGraph] = useState<SchemaGraph | null>(null);
  const [chunks, setChunks] = useState<VectorChunk[] | null>(null);
  const [folderHandle, setFolderHandle] = useState<FolderHandle | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('migrations');
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [parsing, setParsing] = useState(false);

  async function handleLoadFolder() {
    setError(null);
    try {
      const handle = await pickFolder();
      if (!handle) return;
      const loaded = await readMigrations(handle);
      setFolderHandle(handle);
      setFiles(loaded);
      setGraph(null);
      setChunks(null);
      setActiveTab('migrations');
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleParse() {
    setParsing(true);
    setError(null);
    try {
      const result = await parse(files);
      setGraph(result.graph);
      setChunks(result.chunks);
      setSelectedTable([...result.graph.tables.keys()][0] ?? null);
      setActiveTab('graph');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setParsing(false);
    }
  }

  function switchTab(tab: Tab) {
    if (tab === 'graph' && !graph) return;
    if (tab === 'llm' && !chunks) return;
    if (tab === 'ask' && !chunks) return;
    if (tab === 'schema' && !graph) return;
    if (tab === 'insights' && !graph) return;
    if (tab === 'graph-export' && !graph) return;
    setActiveTab(tab);
  }

  return (
    <div className="shell">
      {/* Top bar */}
      <div className="topbar">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <circle cx="9" cy="9" r="8" stroke="#7c3aed" strokeWidth="1.2" />
          <circle cx="9" cy="9" r="4" fill="#7c3aed" opacity=".4" />
          <circle cx="9" cy="9" r="1.5" fill="#7c3aed" />
        </svg>
        <span className="topbar-title">SQLfy - Schema Graph Engine</span>
        <span className="topbar-sub">Flyway → AST → Vector Context</span>
        {/* Show mode badge so it's obvious which runtime is active */}
        <span className="mode-badge" data-mode={IS_TAURI ? 'tauri' : 'browser'}>
          {IS_TAURI ? '⚡ CLI' : '🌐 Browser'}
        </span>
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
        <button
          className={`tab${activeTab === 'ask' ? ' active' : ''}${!graph ? ' disabled' : ''}`}
          onClick={() => switchTab('ask')}
        >
          ④ Ask
        </button>
        <button
          className={`tab${activeTab === 'schema' ? ' active' : ''}${!graph ? ' disabled' : ''}`}
          onClick={() => switchTab('schema')}
        >
          ⑤ Schema
        </button>
        <button
          className={`tab${activeTab === 'insights' ? ' active' : ''}${!graph ? ' disabled' : ''}`}
          onClick={() => switchTab('insights')}
        >
          ⑥ Insights
        </button>
        <button
          className={`tab${activeTab === 'graph-export' ? ' active' : ''}${!graph ? ' disabled' : ''}`}
          onClick={() => switchTab('graph-export')}
        >
          ⑦ Graph Export
        </button>
        <button
          className={`tab${activeTab === 'health' ? ' active' : ''}`}
          onClick={() => switchTab('health')}
        >
          ⑧ Health
        </button>
        <button
          className={`tab${activeTab === 'simulate' ? ' active' : ''}`}
          onClick={() => switchTab('simulate')}
        >
          ⑨ Simulate
        </button>
        <button
          className={`tab${activeTab === 'diff' ? ' active' : ''}`}
          onClick={() => switchTab('diff')}
        >
          ⑨ Diff
        </button>
        <button className="parse-btn" onClick={handleParse} disabled={parsing}>
          {parsing ? '⏳ Parsing…' : '▶ Parse →'}
        </button>
      </div>

      {/* Error bar */}
      {error && (
        <div className="err-bar">
          ⚠ {error}
          {IS_TAURI && (
            <span style={{ marginLeft: 8, opacity: 0.7 }}>
              (Tauri/CLI mode — check that python3 is on PATH and cli/main.py is reachable)
            </span>
          )}
        </div>
      )}

      {/* Content */}
      <div className="content">
        <Activity mode={activeTab === 'migrations' ? 'visible' : 'hidden'}>
          <MigrationsTab
            files={files}
            onChange={setFiles}
            folderHandle={folderHandle}
            onLoadFolder={handleLoadFolder}
          />
        </Activity>

        <Activity mode={activeTab === 'graph' ? 'visible' : 'hidden'}>
          {graph && (
            <GraphTab
              graph={graph}
              selectedTable={selectedTable}
              onSelectTable={setSelectedTable}
            />
          )}
        </Activity>

        <Activity mode={activeTab === 'llm' ? 'visible' : 'hidden'}>
          {chunks && <LlmTab chunks={chunks} />}
        </Activity>

        <Activity mode={activeTab === 'ask' ? 'visible' : 'hidden'}>
          {chunks && <AskPanel chunks={chunks} />}
        </Activity>

        <Activity mode={activeTab === 'schema' ? 'visible' : 'hidden'}>
          {graph && <SchemaTab graph={graph} files={files} />}
        </Activity>

        <Activity mode={activeTab === 'insights' ? 'visible' : 'hidden'}>
          {graph && <InsightsPanel files={files} />}
        </Activity>

        <Activity mode={activeTab === 'graph-export' ? 'visible' : 'hidden'}>
          {graph && <GraphExportPanel files={files} />}
        </Activity>

        <Activity mode={activeTab === 'health' ? 'visible' : 'hidden'}>
          <HealthDashboard files={files} />
        </Activity>

        <Activity mode={activeTab === 'simulate' ? 'visible' : 'hidden'}>
          <SimulatePanel files={files} />
        </Activity>

        <Activity mode={activeTab === 'diff' ? 'visible' : 'hidden'}>
          <DiffPanel files={files} graph={graph} />
        </Activity>
      </div>
    </div>
  );
}
