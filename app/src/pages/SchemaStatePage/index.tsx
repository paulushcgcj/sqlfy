import SchemaTab from '@/components/schema/SchemaTab';
import { useAppContext } from '@/context/AppContext';

/**
 * Schema State page — schema dump and state analysis.
 */
export function SchemaStatePage() {
  const { graph, files } = useAppContext();

  if (!graph) {
    return (
      <div className="page-container">
        <div className="empty-state">
          <p>🏗️ Schema state not available yet.</p>
          <p>
            Go to <strong>Migrations</strong> and click <strong>Parse</strong> to generate the
            schema.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>⑤ Schema State</h2>
        <p className="page-subtitle">Current database schema snapshot</p>
      </div>
      <SchemaTab graph={graph} files={files} />
    </div>
  );
}

export default SchemaStatePage;
