import { useAppContext } from '@/context/AppContext';
import AskPanel from '@/components/schema/AskPanel';

/**
 * Ask page — natural language Q&A with Claude.
 */
export function AskPage() {
  const { chunks } = useAppContext();

  if (!chunks) {
    return (
      <div className="page-container">
        <div className="empty-state">
          <p>💬 Ask feature requires LLM chunks.</p>
          <p>Go to <strong>Migrations</strong> and click <strong>Parse</strong> to generate chunks.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>④ Ask</h2>
        <p className="page-subtitle">Natural language Q&A with Claude</p>
      </div>
      <AskPanel chunks={chunks} />
    </div>
  );
}

export default AskPage;
