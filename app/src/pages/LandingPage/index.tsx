import { useNavigate } from '@tanstack/react-router';

import { parse } from '@/bridge/cli';
import { pickFolder, readMigrations, folderLabel } from '@/bridge/folder';
import { useAppContext } from '@/context/AppContext';
import { SAMPLE_MIGRATIONS } from '@/data/samples';
import './index.scss';

/**
 * Landing/Home page — folder selection and migration loading.
 *
 * Features:
 * - Pick folder or load sample migrations
 * - Display current folder path and migration count
 * - Parse button to generate schema graph
 * - Serves as entry point to the app
 */
export function LandingPage() {
  const navigate = useNavigate();
  const {
    files,
    setFiles,
    folderHandle,
    setFolderHandle,
    setGraph,
    setChunks,
    setError,
    error,
    parsing,
    setParsing,
  } = useAppContext();

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
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function handleLoadSamples() {
    setError(null);
    setFolderHandle(null);
    setFiles(SAMPLE_MIGRATIONS);
    setGraph(null);
    setChunks(null);
  }

  async function handleParse() {
    setParsing(true);
    setError(null);
    try {
      const result = await parse(files);
      setGraph(result.graph);
      setChunks(result.chunks);
      // Navigate to graph page
      await navigate({ to: '/graph' });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setParsing(false);
    }
  }

  return (
    <div className="page-container landing-page">
      <div className="landing-hero">
        <div className="landing-content">
          <h1>SQLfy — Schema Graph Engine</h1>
          <p className="subtitle">
            Parse Flyway migrations into an AST, reconstruct your schema state, and export LLM-ready vector context.
          </p>

          <div className="landing-actions">
            <button className="btn btn-primary" onClick={handleLoadFolder}>
              📂 Select Folder
            </button>
            <button className="btn btn-secondary" onClick={handleLoadSamples}>
              📦 Load Sample Migrations
            </button>
          </div>

          {error && <div className="error-banner">{error}</div>}

          <div className="migration-info">
            {folderHandle ? (
              <div>
                <p>
                  <strong>📁 Folder:</strong> {folderLabel(folderHandle)}
                </p>
                <p>
                  <strong>📄 Migrations:</strong> {files.length} files
                </p>
              </div>
            ) : files.length > 0 ? (
              <div>
                <p>
                  <strong>📦 Source:</strong> Sample Migrations
                </p>
                <p>
                  <strong>📄 Migrations:</strong> {files.length} files
                </p>
              </div>
            ) : null}
          </div>

          {files.length > 0 && (
            <div className="landing-parse">
              <button
                className="btn btn-success"
                onClick={handleParse}
                disabled={parsing}
              >
                {parsing ? '⏳ Parsing...' : '▶ Parse & Generate Schema Graph'}
              </button>
              <p className="parse-hint">
                This will parse all migrations and generate the schema graph. You can then explore the schema in
                various ways.
              </p>
            </div>
          )}
        </div>

        <div className="landing-sidebar">
          <div className="feature-list">
            <h3>Features</h3>
            <ul>
              <li>📊 <strong>Schema Graph</strong> - Interactive ERD and table explorer</li>
              <li>🤖 <strong>LLM Chunks</strong> - Pre-formatted vector context for RAG</li>
              <li>🔍 <strong>Insights</strong> - Detect schema anti-patterns</li>
              <li>❤️ <strong>Health Score</strong> - Comprehensive health report</li>
              <li>🔄 <strong>Compare</strong> - Diff schema versions and simulate changes</li>
              <li>💬 <strong>Ask</strong> - Natural language Q&A with Claude</li>
            </ul>
          </div>

          <div className="help-box">
            <h3>Need help?</h3>
            <p>Start by selecting a folder with Flyway migrations, or load the sample migrations to explore the features.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LandingPage;
