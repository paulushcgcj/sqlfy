import { createContext, useContext } from 'react';

import type { FolderHandle } from '@/bridge/folder';
import type { MigrationFile } from '@/core/local-types';
import type { SchemaGraph, VectorChunk } from '@/core/types';

export interface AppContextType {
  files: MigrationFile[];
  setFiles: (files: MigrationFile[]) => void;
  folderHandle: FolderHandle | null;
  setFolderHandle: (handle: FolderHandle | null) => void;
  graph: SchemaGraph | null;
  setGraph: (graph: SchemaGraph | null) => void;
  chunks: VectorChunk[] | null;
  setChunks: (chunks: VectorChunk[] | null) => void;
  selectedTable: string | null;
  setSelectedTable: (table: string | null) => void;
  error: string | null;
  setError: (error: string | null) => void;
  parsing: boolean;
  setParsing: (parsing: boolean) => void;
}

export const AppContext = createContext<AppContextType | undefined>(undefined);

export function useAppContext(): AppContextType {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within AppContextProvider');
  }
  return context;
}
