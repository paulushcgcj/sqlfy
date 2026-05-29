import { render, fireEvent, waitFor, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import DiffPanel from './index';

import type { DiffVersionsResult } from '@/bridge/cli';
import type { MigrationFile, SchemaGraph } from '@/core/types';

// Mock the CLI bridge
vi.mock('@/bridge/cli', () => ({
  runDiff: vi.fn(),
  CLI_AVAILABLE: true,
}));

const mockGraph: SchemaGraph = {
  tables: new Map(),
  seqs: new Map(),
  edges: [],
  migHist: [
    { version: '1', description: 'create users' },
    { version: '2', description: 'add email' },
  ],
};

const mockFiles: MigrationFile[] = [
  { filename: 'V1__create_users.sql', sql: 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY);' },
  { filename: 'V2__add_email.sql', sql: 'ALTER TABLE APP.USERS ADD EMAIL VARCHAR2(255);' },
];

const mockDiffResult: DiffVersionsResult = {
  versionA: '1',
  versionB: '2',
  fingerprintA: 'abc',
  fingerprintB: 'def',
  stats: {
    tablesAdded: 1,
    tablesRemoved: 0,
    tablesModified: 1,
    columnsAdded: 2,
    columnsRemoved: 0,
    columnsModified: 0,
    sequencesAdded: 0,
    sequencesRemoved: 0,
    relationshipsAdded: 0,
    relationshipsRemoved: 0,
    isBreaking: false,
  },
  tableChanges: [
    { fullName: 'APP.NEW_TABLE', change: 'added', breaking: false },
    {
      fullName: 'APP.USERS',
      change: 'modified',
      breaking: false,
      columnChanges: [{ name: 'EMAIL', change: 'added', breaking: false }],
    },
  ],
  sequenceChanges: [],
  relationshipChanges: [],
};

describe('DiffPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders version selectors and Diff button', () => {
    const { container } = render(<DiffPanel files={mockFiles} graph={mockGraph} />);
    const selects = container.querySelectorAll('.diff-version-select');
    expect(selects.length).toBe(2);
    expect(screen.getByText('▶ Diff')).toBeTruthy();
  });

  it('calls runDiff with the selected versions and displays stats', async () => {
    const { runDiff } = await import('@/bridge/cli');
    vi.mocked(runDiff).mockResolvedValue(mockDiffResult);

    const { container } = render(<DiffPanel files={mockFiles} graph={mockGraph} />);

    const selects = container.querySelectorAll(
      '.diff-version-select',
    ) as NodeListOf<HTMLSelectElement>;
    fireEvent.change(selects[0], { target: { value: '1' } });
    fireEvent.change(selects[1], { target: { value: '2' } });

    fireEvent.click(screen.getByText('▶ Diff'));

    await waitFor(() => {
      expect(runDiff).toHaveBeenCalledWith(mockFiles, { fromVersion: '1', toVersion: '2' });
    });

    await waitFor(() => {
      expect(container.querySelector('.diff-stats-grid')).toBeTruthy();
      expect(container.textContent).toContain('Tables added');
      expect(container.textContent).toContain('V1 → V2');
      expect(container.textContent).toContain('✓ No breaking removals detected');
    });
  });

  it('shows error when runDiff throws', async () => {
    const { runDiff } = await import('@/bridge/cli');
    vi.mocked(runDiff).mockRejectedValue(new Error('CLI not available'));

    render(<DiffPanel files={mockFiles} graph={mockGraph} />);
    fireEvent.click(screen.getByText('▶ Diff'));

    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toContain('CLI not available');
    });
  });
});
