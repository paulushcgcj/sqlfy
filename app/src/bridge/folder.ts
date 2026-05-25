/**
 * sqlfy — src/bridge/folder.ts
 *
 * Cross-context folder bridge.
 *
 * Provides a unified API for folder picking, directory listing, and file
 * writing that works in both the Tauri desktop runtime and a plain browser.
 *
 *  Tauri:   @tauri-apps/plugin-dialog (picker) + @tauri-apps/plugin-fs (io)
 *  Browser: File System Access API  (showDirectoryPicker / FileSystemDirectoryHandle)
 */

import { IS_TAURI } from './cli';
import type { MigrationFile } from '../core/types';

// ── Handle ───────────────────────────────────────────────────────────────────

/** Opaque reference to a folder; varies by runtime. */
export type FolderHandle =
  | { readonly type: 'tauri';   readonly path: string }
  | { readonly type: 'browser'; readonly dir: FileSystemDirectoryHandle };

/** Returns the folder's base name for display. */
export function folderLabel(handle: FolderHandle): string {
  if (handle.type === 'tauri') return handle.path.split('/').at(-1) ?? handle.path;
  return handle.dir.name;
}

// ── Pick ─────────────────────────────────────────────────────────────────────

/**
 * Opens a native folder-picker dialog.
 * Returns `null` if the user cancels or the runtime lacks support.
 */
export async function pickFolder(): Promise<FolderHandle | null> {
  if (IS_TAURI) {
    const { open } = await import('@tauri-apps/plugin-dialog');
    const result = await open({
      directory: true,
      multiple:  false,
      title:     'Select migrations folder',
    });
    if (!result) return null;
    return { type: 'tauri', path: result as string };
  }

  // Browser — File System Access API
  if (!('showDirectoryPicker' in globalThis)) {
    throw new Error(
      'Your browser does not support the File System Access API.\n' +
      'Please use Chrome, Edge, or Opera — or run the Tauri desktop app.'
    );
  }
  try {
    const dir = await showDirectoryPicker({ mode: 'readwrite' });
    return { type: 'browser', dir };
  } catch {
    return null; // AbortError = user cancelled
  }
}

// ── Read ─────────────────────────────────────────────────────────────────────

/**
 * Lists all `.sql` files in the folder, sorted by filename (Flyway order).
 */
export async function readMigrations(handle: FolderHandle): Promise<MigrationFile[]> {
  if (handle.type === 'tauri') {
    const { readDir, readTextFile } = await import('@tauri-apps/plugin-fs');
    const { join }                  = await import('@tauri-apps/api/path');
    const entries = await readDir(handle.path);
    const sqlEntries = entries
      .filter(e => e.name?.endsWith('.sql'))
      .sort((a, b) => (a.name ?? '').localeCompare(b.name ?? ''));
    return Promise.all(
      sqlEntries.map(async e => ({
        filename: e.name!,
        sql: await readTextFile(await join(handle.path, e.name!)),
      }))
    );
  }

  // Browser
  const files: MigrationFile[] = [];
  for await (const entry of handle.dir.values()) {
    if (entry.kind === 'file' && entry.name.endsWith('.sql')) {
      const fileHandle = entry as FileSystemFileHandle;
      const file = await fileHandle.getFile();
      files.push({ filename: entry.name, sql: await file.text() });
    }
  }
  return files.sort((a, b) => a.filename.localeCompare(b.filename));
}

// ── Write ────────────────────────────────────────────────────────────────────

/**
 * Creates or overwrites a `.sql` file in the folder.
 */
export async function writeFile(
  handle:   FolderHandle,
  filename: string,
  content:  string,
): Promise<void> {
  if (handle.type === 'tauri') {
    const { writeTextFile } = await import('@tauri-apps/plugin-fs');
    const { join }          = await import('@tauri-apps/api/path');
    await writeTextFile(await join(handle.path, filename), content);
    return;
  }

  // Browser
  const fileHandle = await handle.dir.getFileHandle(filename, { create: true });
  const writable   = await fileHandle.createWritable();
  await writable.write(content);
  await writable.close();
}
