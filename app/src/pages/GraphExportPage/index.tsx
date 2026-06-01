import { useAppContext } from '@/context/AppContext';
import GraphExportPanel from '@/components/schema/GraphExportPanel';

/**
 * Graph Export page — export schema in multiple formats (Mermaid, DOT, Excalidraw, Draw.io).
 */
export function GraphExportPage() {
  const { graph, files } = useAppContext();

  if (!graph) {
    return (
      <div className="page-container">
        <div className="empty-state">
          <p>📤 Export requires a parsed schema.</p>
          <p>Go to <strong>Migrations</strong> and click <strong>Parse</strong> to enable exports.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>⑦ Graph Export</h2>
        <p className="page-subtitle">Export schema in multiple formats</p>
      </div>
      <GraphExportPanel files={files} />
    </div>
  );
}

export default GraphExportPage;
