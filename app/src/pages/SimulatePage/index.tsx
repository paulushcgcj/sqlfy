import { useAppContext } from '@/context/AppContext';
import SimulatePanel from '@/components/schema/SimulatePanel';

/**
 * Simulate page — simulate DDL changes and preview results.
 */
export function SimulatePage() {
  const { files } = useAppContext();

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>⑨ Simulate</h2>
        <p className="page-subtitle">Simulate DDL changes and preview results</p>
      </div>
      <SimulatePanel files={files} />
    </div>
  );
}

export default SimulatePage;
