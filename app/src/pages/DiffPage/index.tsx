import { useAppContext } from '@/context/AppContext';
import DiffPanel from '@/components/schema/DiffPanel';

/**
 * Diff page — compare schema versions and migration versions.
 */
export function DiffPage() {
  const { files, graph } = useAppContext();

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>⑩ Diff</h2>
        <p className="page-subtitle">Compare schema and migration versions</p>
      </div>
      <DiffPanel files={files} graph={graph} />
    </div>
  );
}

export default DiffPage;
