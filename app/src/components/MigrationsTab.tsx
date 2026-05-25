import type { MigrationFile } from '../core/types';

interface Props {
  files: MigrationFile[];
  onChange: (files: MigrationFile[]) => void;
}

export function MigrationsTab({ files, onChange }: Props) {
  function updateFile(index: number, field: keyof MigrationFile, value: string) {
    const next = files.map((f, i) => i === index ? { ...f, [field]: value } : f);
    onChange(next);
  }

  function removeFile(index: number) {
    onChange(files.filter((_, i) => i !== index));
  }

  function addFile() {
    onChange([...files, {
      filename: `V${files.length + 1}__new_migration.sql`,
      sql: '-- Add your SQL here\n',
    }]);
  }

  return (
    <div className="panel">
      {files.map((file, i) => (
        <div className="file-block" key={i}>
          <div className="file-hdr">
            <span className="file-v-badge">V</span>
            <input
              value={file.filename}
              onChange={e => updateFile(i, 'filename', e.target.value)}
            />
            <button className="rm" onClick={() => removeFile(i)}>×</button>
          </div>
          <textarea
            className="sql-area"
            rows={10}
            value={file.sql}
            onChange={e => updateFile(i, 'sql', e.target.value)}
          />
        </div>
      ))}
      <button className="add-btn" onClick={addFile}>+ Add Migration File</button>
    </div>
  );
}