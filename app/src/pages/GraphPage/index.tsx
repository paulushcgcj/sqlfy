import { useAppContext } from '@/context/AppContext';
import GraphTab from '@/components/schema/GraphTab';

/**
 * Graph page — interactive schema graph visualization.
 */
export function GraphPage() {
  const { graph, selectedTable, setSelectedTable } = useAppContext();

  if (!graph) {
    return (
      <div className="page-container">
        <div className="empty-state">
          <p>📊 Schema graph not generated yet.</p>
          <p>Go to <strong>Migrations</strong> and click <strong>Parse</strong> to generate the graph.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>② Schema Graph</h2>
        <p className="page-subtitle">{graph.tables.size} tables, {graph.edges.length} relationships</p>
      </div>
      <GraphTab
        graph={graph}
        selectedTable={selectedTable}
        onSelectTable={(table) => setSelectedTable(table)}
      />
    </div>
  );
}

export default GraphPage;
