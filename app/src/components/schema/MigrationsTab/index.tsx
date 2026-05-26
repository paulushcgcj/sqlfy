import type { MigrationFile } from '@/core/types';
import type { FC } from 'react';

import { writeFile, folderLabel, type FolderHandle } from '@/bridge/folder';
import './index.scss';

/** Props for the {@link MigrationsTab} component. */
export interface MigrationsTabProps {
  /** The list of SQL migration files currently loaded. */
  readonly files: MigrationFile[];
  /** Callback to update the migration file list (add, edit, or remove). */
  readonly onChange: (files: MigrationFile[]) => void;
  /**
   * When set, new migrations added via the button are also written to this folder.
   * @default null
   */
  readonly folderHandle?: FolderHandle | null;
  /**
   * Called when the user clicks "Load from folder".
   * App-level responsibility: opens picker, reads files, updates state.
   * @default undefined
   */
  readonly onLoadFolder?: () => Promise<void>;
}

/**
 * Migration files editor panel.
 *
 * Renders a list of editable SQL file blocks with filename inputs and SQL textareas.
 * Supports loading an entire folder of `.sql` files, adding new files (with optional
 * on-disk creation when a folder is loaded), and removing files.
 *
 * @component
 * @example
 * ```tsx
 * <MigrationsTab files={files} onChange={setFiles} folderHandle={handle} onLoadFolder={handleLoad} />
 * ```
 * @param props - {@link MigrationsTabProps}
 * @returns An editable list of SQL migration file blocks.
 */
const MigrationsTab: FC<MigrationsTabProps> = ({ files, onChange, folderHandle, onLoadFolder }) => {
  function updateFile(index: number, field: keyof MigrationFile, value: string) {
    const next = files.map((f, i) => (i === index ? { ...f, [field]: value } : f));
    onChange(next);
  }

  function removeFile(index: number) {
    onChange(files.filter((_, i) => i !== index));
  }

  async function addFile() {
    const filename = `V${files.length + 1}__new_migration.sql`;
    const sql = '-- Add your SQL here\n';
    if (folderHandle) {
      await writeFile(folderHandle, filename, sql);
    }
    onChange([...files, { filename, sql }]);
  }

  return (
    <div className="panel">
      {/* Toolbar */}
      <div className="migrations-toolbar">
        <button className="migraton-btn add-btn" onClick={addFile}>
          + Add Migration File
        </button>
        {onLoadFolder && (
          <button className="migraton-btn load-folder-btn" onClick={onLoadFolder}>
            📁 Load from folder
          </button>
        )}
        {folderHandle && (
          <span
            className="folder-badge"
            title={folderHandle.type === 'tauri' ? folderHandle.path : folderHandle.dir.name}
          >
            {folderLabel(folderHandle)}
            <span className="folder-count">
              {files.length} file{files.length !== 1 ? 's' : ''}
            </span>
          </span>
        )}
      </div>

      {files.map((file, i) => (
        <div className="file-block" key={i}>
          <div className="file-hdr">
            <span className="file-v-badge">V</span>
            <input
              value={file.filename}
              onChange={(e) => updateFile(i, 'filename', e.target.value)}
            />
            <button className="rm" onClick={() => removeFile(i)}>
              ×
            </button>
          </div>
          <textarea
            className="sql-area"
            rows={10}
            value={file.sql}
            onChange={(e) => updateFile(i, 'sql', e.target.value)}
          />
        </div>
      ))}
    </div>
  );
};

export default MigrationsTab;
