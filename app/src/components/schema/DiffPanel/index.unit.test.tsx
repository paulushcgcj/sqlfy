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
  version_a: '1',
  version_b: '2',
  fingerprint_a: 'abc',
  fingerprint_b: 'def',
  stats: {
    tables_added: 1,
    tables_removed: 0,
    tables_modified: 1,
    columns_added: 2,
    columns_removed: 0,
    columns_modified: 0,
    sequences_added: 0,
    sequences_removed: 0,
    relationships_added: 0,
    relationships_removed: 0,
    is_breaking: false,
  },
  table_changes: [
    { full_name: 'APP.NEW_TABLE', change: 'added', breaking: false },
    {
      full_name: 'APP.USERS',
      change: 'modified',
      breaking: false,
      column_changes: [{ name: 'EMAIL', change: 'added', breaking: false }],
    },
  ],
  sequence_changes: [],
  relationship_changes: [],
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
