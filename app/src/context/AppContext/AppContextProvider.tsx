import { useState } from 'react';

import { AppContext } from './context';

import type { FolderHandle } from '@/bridge/folder';
import type { MigrationFile } from '@/core/local-types';
import type { SchemaGraph, VectorChunk } from '@/core/types';
import type { ReactNode } from 'react';

interface AppContextProviderProps {
  children: ReactNode;
  initialFiles?: MigrationFile[];
}

export function AppContextProvider({ children, initialFiles = [] }: AppContextProviderProps) {
  const [files, setFiles] = useState<MigrationFile[]>(initialFiles);
  const [folderHandle, setFolderHandle] = useState<FolderHandle | null>(null);
  const [graph, setGraph] = useState<SchemaGraph | null>(null);
  const [chunks, setChunks] = useState<VectorChunk[] | null>(null);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [parsing, setParsing] = useState(false);

  return (
    <AppContext.Provider
      value={{
        files,
        setFiles,
        folderHandle,
        setFolderHandle,
        graph,
        setGraph,
        chunks,
        setChunks,
        selectedTable,
        setSelectedTable,
        error,
        setError,
        parsing,
        setParsing,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}
