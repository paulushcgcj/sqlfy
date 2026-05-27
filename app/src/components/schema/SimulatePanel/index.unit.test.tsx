import { render, fireEvent, waitFor, screen } from '@testing-library/react';
import { vi } from 'vitest';

import SimulatePanel from './index';

import type { MigrationFile } from '@/core/types';
import type { SimulateResult } from '@/bridge/cli';

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock('@/bridge/cli', () => ({
  CLI_AVAILABLE: true,
  runSimulate: vi.fn(),
}));

import { runSimulate } from '@/bridge/cli';
const mockRunSimulate = runSimulate as ReturnType<typeof vi.fn>;

// ── Fixtures ─────────────────────────────────────────────────────────────────

const sampleFiles: MigrationFile[] = [
  { name: 'V1__create_users.sql', content: 'CREATE TABLE users (id NUMBER);' },
  { name: 'V2__add_orders.sql', content: 'CREATE TABLE orders (id NUMBER);' },
];

const safeSqlResult: SimulateResult = {
  timestamp: '2026-01-01T00:00:00Z',
  base_version: '2',
  sql: 'ALTER TABLE users ADD (email VARCHAR2(255));',
  success: true,
  is_safe: true,
  is_breaking: false,
  errors: [],
  warnings: ['ORPHAN_TABLE: Table users has no FK relationships.'],
  diff: {
    stats: {
      tables_added: 0,
      tables_removed: 0,
      tables_modified: 0,
      columns_added: 1,
      columns_removed: 0,
      columns_modified: 0,
      sequences_added: 0,
      sequences_removed: 0,
      relationships_added: 0,
      relationships_removed: 0,
      is_breaking: false,
    },
    is_breaking: false,
  },
  health: { score: 85, grade: 'good', errors: 0, warnings: 1 },
};

const breakingSqlResult: SimulateResult = {
  timestamp: '2026-01-01T00:00:00Z',
  base_version: '2',
  sql: 'DROP TABLE users;',
  success: true,
  is_safe: false,
  is_breaking: true,
  errors: [],
  warnings: ['CIRCULAR_FK: Circular reference detected.'],
  diff: {
    stats: {
      tables_added: 0,
      tables_removed: 1,
      tables_modified: 0,
      columns_added: 0,
      columns_removed: 0,
      columns_modified: 0,
      sequences_added: 0,
      sequences_removed: 0,
      relationships_added: 0,
      relationships_removed: 2,
      is_breaking: true,
    },
    is_breaking: true,
  },
  health: { score: 30, grade: 'critical', errors: 1, warnings: 1 },
};

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('SimulatePanel', () => {
  beforeEach(() => {
    mockRunSimulate.mockReset();
  });

  it('renders SQL textarea and simulate button', () => {
    const { getByRole, getByLabelText } = render(<SimulatePanel files={sampleFiles} />);
    expect(getByLabelText('SQL to simulate')).toBeTruthy();
    expect(getByRole('button', { name: '▶ Simulate' })).toBeTruthy();
  });

  it('disables simulate button when SQL is empty', () => {
    const { getByRole } = render(<SimulatePanel files={sampleFiles} />);
    const btn = getByRole('button', { name: '▶ Simulate' }) as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });

  it('enables simulate button when SQL has content', () => {
    const { getByRole, getByLabelText } = render(<SimulatePanel files={sampleFiles} />);
    fireEvent.change(getByLabelText('SQL to simulate'), {
      target: { value: 'ALTER TABLE users ADD (x NUMBER);' },
    });
    const btn = getByRole('button', { name: '▶ Simulate' }) as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
  });

  it('shows loading state while simulating', async () => {
    mockRunSimulate.mockReturnValue(new Promise(() => {})); // never resolves
    const { getByLabelText, getByRole } = render(<SimulatePanel files={sampleFiles} />);
    fireEvent.change(getByLabelText('SQL to simulate'), {
      target: { value: 'ALTER TABLE users ADD (x NUMBER);' },
    });
    fireEvent.click(getByRole('button', { name: '▶ Simulate' }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: '⏳ Simulating…' })).toBeTruthy();
    });
  });

  it('displays safe result with health badge', async () => {
    mockRunSimulate.mockResolvedValue(safeSqlResult);
    const { getByLabelText, getByRole, getByText } = render(
      <SimulatePanel files={sampleFiles} />,
    );
    fireEvent.change(getByLabelText('SQL to simulate'), {
      target: { value: 'ALTER TABLE users ADD (email VARCHAR2(255));' },
    });
    fireEvent.click(getByRole('button', { name: '▶ Simulate' }));

    await waitFor(() => {
      expect(getByText('✓ Safe')).toBeTruthy();
      expect(getByText(/Health 85\/100/)).toBeTruthy();
      expect(getByText(/base version/)).toBeTruthy();
      expect(getByText('V2')).toBeTruthy();
    });
  });

  it('displays unsafe + breaking badges for destructive SQL', async () => {
    mockRunSimulate.mockResolvedValue(breakingSqlResult);
    const { getByLabelText, getByRole, getByText } = render(
      <SimulatePanel files={sampleFiles} />,
    );
    fireEvent.change(getByLabelText('SQL to simulate'), {
      target: { value: 'DROP TABLE users;' },
    });
    fireEvent.click(getByRole('button', { name: '▶ Simulate' }));

    await waitFor(() => {
      expect(getByText('✕ Unsafe')).toBeTruthy();
      expect(getByText('⚠ Breaking Changes')).toBeTruthy();
      expect(getByText(/Health 30\/100/)).toBeTruthy();
    });
  });

  it('shows diff stats table when changes are present', async () => {
    mockRunSimulate.mockResolvedValue(safeSqlResult);
    const { getByLabelText, getByRole, getByText } = render(
      <SimulatePanel files={sampleFiles} />,
    );
    fireEvent.change(getByLabelText('SQL to simulate'), {
      target: { value: 'ALTER TABLE users ADD (email VARCHAR2(255));' },
    });
    fireEvent.click(getByRole('button', { name: '▶ Simulate' }));

    await waitFor(() => {
      expect(getByText('Schema Changes')).toBeTruthy();
      expect(getByText('Columns')).toBeTruthy();
      expect(getByText('+1')).toBeTruthy();
    });
  });

  it('shows no-changes message when diff is empty', async () => {
    const noChangesResult: SimulateResult = {
      ...safeSqlResult,
      diff: {
        stats: {
          tables_added: 0,
          tables_removed: 0,
          tables_modified: 0,
          columns_added: 0,
          columns_removed: 0,
          columns_modified: 0,
          sequences_added: 0,
          sequences_removed: 0,
          relationships_added: 0,
          relationships_removed: 0,
          is_breaking: false,
        },
        is_breaking: false,
      },
    };
    mockRunSimulate.mockResolvedValue(noChangesResult);
    const { getByLabelText, getByRole, getByText } = render(
      <SimulatePanel files={sampleFiles} />,
    );
    fireEvent.change(getByLabelText('SQL to simulate'), {
      target: { value: 'ALTER TABLE users ADD (email VARCHAR2(255));' },
    });
    fireEvent.click(getByRole('button', { name: '▶ Simulate' }));

    await waitFor(() => {
      expect(getByText('No structural changes detected.')).toBeTruthy();
    });
  });

  it('shows collapsible warnings section when warnings present', async () => {
    mockRunSimulate.mockResolvedValue(safeSqlResult);
    const { getByLabelText, getByRole, getByText } = render(
      <SimulatePanel files={sampleFiles} />,
    );
    fireEvent.change(getByLabelText('SQL to simulate'), {
      target: { value: 'ALTER TABLE users ADD (email VARCHAR2(255));' },
    });
    fireEvent.click(getByRole('button', { name: '▶ Simulate' }));

    await waitFor(() => {
      expect(getByText('1 warning')).toBeTruthy();
    });
  });

  it('passes atVersion option when version field is set', async () => {
    mockRunSimulate.mockResolvedValue(safeSqlResult);
    const { getByLabelText, getByRole } = render(<SimulatePanel files={sampleFiles} />);

    fireEvent.change(getByLabelText('SQL to simulate'), {
      target: { value: 'ALTER TABLE users ADD (email VARCHAR2(255));' },
    });
    fireEvent.change(getByLabelText(/Base version/), { target: { value: '1' } });
    fireEvent.click(getByRole('button', { name: '▶ Simulate' }));

    await waitFor(() => {
      expect(mockRunSimulate).toHaveBeenCalledWith(
        sampleFiles,
        'ALTER TABLE users ADD (email VARCHAR2(255));',
        { atVersion: 1 },
      );
    });
  });

  it('passes no atVersion when version field is empty', async () => {
    mockRunSimulate.mockResolvedValue(safeSqlResult);
    const { getByLabelText, getByRole } = render(<SimulatePanel files={sampleFiles} />);

    fireEvent.change(getByLabelText('SQL to simulate'), {
      target: { value: 'ALTER TABLE users ADD (email VARCHAR2(255));' },
    });
    fireEvent.click(getByRole('button', { name: '▶ Simulate' }));

    await waitFor(() => {
      expect(mockRunSimulate).toHaveBeenCalledWith(
        sampleFiles,
        'ALTER TABLE users ADD (email VARCHAR2(255));',
        undefined,
      );
    });
  });

  it('shows error message when runSimulate throws', async () => {
    mockRunSimulate.mockRejectedValue(new Error('CLI not found'));
    const { getByLabelText, getByRole, getByText } = render(
      <SimulatePanel files={sampleFiles} />,
    );
    fireEvent.change(getByLabelText('SQL to simulate'), {
      target: { value: 'ALTER TABLE users ADD (x NUMBER);' },
    });
    fireEvent.click(getByRole('button', { name: '▶ Simulate' }));

    await waitFor(() => {
      expect(getByText(/CLI not found/)).toBeTruthy();
    });
  });

  it('clears previous result before a new run', async () => {
    mockRunSimulate.mockResolvedValueOnce(safeSqlResult).mockResolvedValueOnce(breakingSqlResult);
    const { getByLabelText, getByRole, queryByText } = render(
      <SimulatePanel files={sampleFiles} />,
    );
    const textarea = getByLabelText('SQL to simulate');
    fireEvent.change(textarea, {
      target: { value: 'ALTER TABLE users ADD (email VARCHAR2(255));' },
    });

    // First run
    fireEvent.click(getByRole('button', { name: '▶ Simulate' }));
    await waitFor(() => expect(queryByText('✓ Safe')).toBeTruthy());

    // Second run - previous result should be cleared first
    fireEvent.change(textarea, { target: { value: 'DROP TABLE users;' } });
    fireEvent.click(getByRole('button', { name: '▶ Simulate' }));
    await waitFor(() => expect(queryByText('✕ Unsafe')).toBeTruthy());
    expect(queryByText('✓ Safe')).toBeNull();
  });
});

describe('SimulatePanel — no CLI available', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('shows no-CLI notice and disables button when CLI_AVAILABLE is false', async () => {
    vi.doMock('@/bridge/cli', () => ({
      CLI_AVAILABLE: false,
      runSimulate: vi.fn(),
    }));

    const { default: PanelNoCliEnv } = await import('./index');
    const { getByRole, getByText } = render(<PanelNoCliEnv files={sampleFiles} />);

    expect(getByText(/requires the Python CLI/)).toBeTruthy();
    const btn = getByRole('button', { name: '▶ Simulate' }) as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });
});
