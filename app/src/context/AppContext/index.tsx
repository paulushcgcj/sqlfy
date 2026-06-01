import { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';

import type { MigrationFile } from '@/core/local-types';
import type { FolderHandle } from '@/bridge/folder';
import type { SchemaGraph, VectorChunk } from '@/core/types';

/**
 * AppContext — shared state for all pages.
 *
 * Contains migration files, parsed schema, LLM chunks, and UI state
 * that need to be accessed across multiple pages.
 */

export interface AppContextType {
  // Files and folder state
  files: MigrationFile[];
  setFiles: (files: MigrationFile[]) => void;
  folderHandle: FolderHandle | null;
  setFolderHandle: (handle: FolderHandle | null) => void;

  // Parsed schema and chunks
  graph: SchemaGraph | null;
  setGraph: (graph: SchemaGraph | null) => void;
  chunks: VectorChunk[] | null;
  setChunks: (chunks: VectorChunk[] | null) => void;

  // UI state
  selectedTable: string | null;
  setSelectedTable: (table: string | null) => void;
  error: string | null;
  setError: (error: string | null) => void;
  parsing: boolean;
  setParsing: (parsing: boolean) => void;
}

export const AppContext = createContext<AppContextType | undefined>(undefined);

interface AppContextProviderProps {
  children: ReactNode;
  initialFiles?: MigrationFile[];
}

export function AppContextProvider({
  children,
  initialFiles = [],
}: AppContextProviderProps) {
  const [files, setFiles] = useState<MigrationFile[]>(initialFiles);
  const [folderHandle, setFolderHandle] = useState<FolderHandle | null>(null);
  const [graph, setGraph] = useState<SchemaGraph | null>(null);
  const [chunks, setChunks] = useState<VectorChunk[] | null>(null);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [parsing, setParsing] = useState(false);

  const value: AppContextType = {
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
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

/**
 * Hook to access AppContext.
 *
 * @throws Error if used outside AppContextProvider
 */
export function useAppContext() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within AppContextProvider');
  }
  return context;
}
