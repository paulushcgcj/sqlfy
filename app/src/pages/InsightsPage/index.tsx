import InsightsPanel from '@/components/schema/InsightsPanel';
import { useAppContext } from '@/context/AppContext';

/**
 * Insights page — schema analysis and anti-pattern detection.
 */
export function InsightsPage() {
  const { graph, files } = useAppContext();

  if (!graph) {
    return (
      <div className="page-container">
        <div className="empty-state">
          <p>🔍 Insights require a parsed schema.</p>
          <p>
            Go to <strong>Migrations</strong> and click <strong>Parse</strong> to generate insights.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>⑥ Insights</h2>
        <p className="page-subtitle">Schema quality analysis</p>
      </div>
      <InsightsPanel files={files} />
    </div>
  );
}

export default InsightsPage;
