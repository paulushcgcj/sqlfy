import HealthDashboard from '@/components/schema/HealthDashboard';
import { useAppContext } from '@/context/AppContext';

/**
 * Health page — schema health score and migration safety analysis.
 */
export function HealthPage() {
  const { files } = useAppContext();

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>⑧ Health</h2>
        <p className="page-subtitle">Schema health score and safety analysis</p>
      </div>
      <HealthDashboard files={files} />
    </div>
  );
}

export default HealthPage;
