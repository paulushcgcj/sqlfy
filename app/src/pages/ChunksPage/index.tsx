import { useAppContext } from '@/context/AppContext';
import LlmTab from '@/components/schema/LlmTab';

/**
 * Chunks page — LLM-ready vector chunks for RAG pipelines.
 */
export function ChunksPage() {
  const { chunks } = useAppContext();

  if (!chunks) {
    return (
      <div className="page-container">
        <div className="empty-state">
          <p>🤖 LLM chunks not generated yet.</p>
          <p>Go to <strong>Migrations</strong> and click <strong>Parse</strong> to generate chunks.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>③ LLM Chunks</h2>
        <p className="page-subtitle">{chunks.length} context chunks</p>
      </div>
      <LlmTab chunks={chunks} />
    </div>
  );
}

export default ChunksPage;
