import { useAppContext } from '@/context/AppContext';
import MigrationsTab from '@/components/schema/MigrationsTab';

/**
 * Migrations page — displays loaded migration files.
 */
export function MigrationsPage() {
  const { files, setFiles, folderHandle } = useAppContext();

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>① Migrations</h2>
        <p className="page-subtitle">{files.length} migration files loaded</p>
      </div>
      <MigrationsTab files={files} onChange={setFiles} folderHandle={folderHandle} />
    </div>
  );
}

export default MigrationsPage;
