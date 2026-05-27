import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import InsightsPanel from './index';

import type { InsightsResult } from '@/bridge/cli';
import type { MigrationFile } from '@/core/types';

import * as cli from '@/bridge/cli';

// ── Mocks ──────────────────────────────────────────────────────────────────

vi.mock('@/bridge/cli', () => ({
  IS_TAURI: false,
  runInsights: vi.fn(),
}));

// ── Fixtures ───────────────────────────────────────────────────────────────

const mockFiles: MigrationFile[] = [
  { filename: 'V1__create.sql', sql: 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY);' },
];

const mockResult: InsightsResult = {
  version: '1',
  fingerprint: 'abc123',
  summary: { errors: 1, warnings: 2, infos: 0, total: 3, healthy: false },
  findings: {
    error: [
      {
        code: 'NO_PK',
        severity: 'error',
        category: 'structural',
        message: 'Table LOGS has no primary key.',
        fix: 'Add PRIMARY KEY constraint.',
      },
    ],
    warning: [
      {
        code: 'ORPHAN_TABLE',
        severity: 'warning',
        category: 'structural',
        message: 'Table LOGS has no FK relationships.',
        table: 'APP.LOGS',
        detail: 'Disconnected from schema.',
        fix: 'Add a FK.',
      },
      {
        code: 'MISSING_FK_CANDIDATE',
        severity: 'warning',
        category: 'referential',
        message: 'Column user_id looks like a FK.',
        table: 'APP.ORDERS',
        column: 'USER_ID',
      },
    ],
    info: [],
  },
};

// ── Tests ──────────────────────────────────────────────────────────────────

describe('InsightsPanel — idle state', () => {
  it('renders Run Insights button initially', () => {
    render(<InsightsPanel files={mockFiles} />);
    expect(screen.getByText('▶ Run Insights')).toBeDefined();
  });

  it('shows idle prompt before first run', () => {
    render(<InsightsPanel files={mockFiles} />);
    expect(screen.getByText(/Run insights to analyse/i)).toBeDefined();
  });

  it('shows CLI mode badge when CLI is available', () => {
    // In Vitest, import.meta.env.DEV is true → CLI_AVAILABLE is true → shows CLI badge
    render(<InsightsPanel files={mockFiles} />);
    expect(screen.getByText(/⚡ (Tauri CLI|Dev CLI)/)).toBeDefined();
  });
});

describe('InsightsPanel — running analysis', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading state while running', async () => {
    vi.mocked(cli.runInsights).mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve(mockResult), 100)),
    );

    render(<InsightsPanel files={mockFiles} />);
    fireEvent.click(screen.getByText('▶ Run Insights'));

    await waitFor(() => expect(screen.getByText('⏳ Running…')).toBeDefined());
  });

  it('displays findings after successful run', async () => {
    vi.mocked(cli.runInsights).mockResolvedValue(mockResult);

    render(<InsightsPanel files={mockFiles} />);
    fireEvent.click(screen.getByText('▶ Run Insights'));

    await waitFor(() => screen.getByText('Table LOGS has no primary key.'));
    expect(screen.getByText('Table LOGS has no primary key.')).toBeDefined();
  });

  it('shows health score after analysis', async () => {
    vi.mocked(cli.runInsights).mockResolvedValue(mockResult);

    render(<InsightsPanel files={mockFiles} />);
    fireEvent.click(screen.getByText('▶ Run Insights'));

    await waitFor(() => screen.getByText(/Score:/));
    expect(screen.getByText(/Score:/)).toBeDefined();
  });

  it('shows severity counts in summary', async () => {
    vi.mocked(cli.runInsights).mockResolvedValue(mockResult);

    render(<InsightsPanel files={mockFiles} />);
    fireEvent.click(screen.getByText('▶ Run Insights'));

    await waitFor(() => screen.getByText('1 errors'));
    expect(screen.getByText('2 warnings')).toBeDefined();
  });

  it('shows CLI error message when runInsights fails', async () => {
    vi.mocked(cli.runInsights).mockRejectedValue(new Error('CLI process exited with code 1'));

    render(<InsightsPanel files={mockFiles} />);
    fireEvent.click(screen.getByText('▶ Run Insights'));

    await waitFor(() => screen.getByText(/CLI process exited with code 1/));
  });

  it('does not show any findings on CLI error', async () => {
    vi.mocked(cli.runInsights).mockRejectedValue(new Error('Connection refused'));

    render(<InsightsPanel files={mockFiles} />);
    fireEvent.click(screen.getByText('▶ Run Insights'));

    await waitFor(() => screen.getByText(/Connection refused/));
    // No findings should be displayed — no filter bar
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
  });

  it('error is cleared on subsequent successful run', async () => {
    vi.mocked(cli.runInsights)
      .mockRejectedValueOnce(new Error('Temporary failure'))
      .mockResolvedValueOnce(mockResult);

    render(<InsightsPanel files={mockFiles} />);
    fireEvent.click(screen.getByText('▶ Run Insights'));
    await waitFor(() => screen.getByText(/Temporary failure/));

    fireEvent.click(screen.getByText('▶ Run Insights'));
    await waitFor(() => screen.getByText('Table LOGS has no primary key.'));
    expect(screen.queryByText(/Temporary failure/)).toBeNull();
  });
});

describe('InsightsPanel — filtering', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(cli.runInsights).mockResolvedValue(mockResult);
  });

  async function renderWithFindings() {
    const result = render(<InsightsPanel files={mockFiles} />);
    fireEvent.click(screen.getByText('▶ Run Insights'));
    await waitFor(() => screen.getByText('Table LOGS has no primary key.'));
    return result;
  }

  it('renders filter bar after analysis', async () => {
    await renderWithFindings();
    expect(screen.getAllByRole('checkbox').length).toBe(3); // error, warning, info
  });

  it('shows category dropdown', async () => {
    await renderWithFindings();
    const select = screen.getByLabelText('Category:') as HTMLSelectElement;
    expect(select).toBeDefined();
    expect(select.querySelector('option[value="structural"]')).toBeDefined();
  });

  it('toggling error checkbox hides error findings', async () => {
    await renderWithFindings();

    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[0]); // first = error

    await waitFor(() => {
      expect(screen.queryByText('Table LOGS has no primary key.')).toBeNull();
    });
  });

  it('filters by keyword search', async () => {
    await renderWithFindings();

    const searchInput = screen.getByLabelText('Search findings');
    fireEvent.change(searchInput, { target: { value: 'orphan' } });

    await waitFor(() => {
      expect(screen.getByText('Table LOGS has no FK relationships.')).toBeDefined();
      expect(screen.queryByText('Table LOGS has no primary key.')).toBeNull();
    });
  });

  it('clear filters button resets all filters', async () => {
    await renderWithFindings();

    const searchInput = screen.getByLabelText('Search findings');
    fireEvent.change(searchInput, { target: { value: 'orphan' } });
    await waitFor(() => screen.queryByText('Table LOGS has no primary key.') === null);

    fireEvent.click(screen.getByTitle('Clear all filters'));

    await waitFor(() => {
      expect(screen.getByText('Table LOGS has no primary key.')).toBeDefined();
    });
  });

  it('shows correct filtered count', async () => {
    await renderWithFindings();

    const searchInput = screen.getByLabelText('Search findings');
    fireEvent.change(searchInput, { target: { value: 'orphan' } });

    await waitFor(() => screen.getByText(/1 of 3/));
  });
});

describe('InsightsPanel — finding card expand/collapse', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(cli.runInsights).mockResolvedValue(mockResult);
  });

  it('finding details are hidden by default', async () => {
    render(<InsightsPanel files={mockFiles} />);
    fireEvent.click(screen.getByText('▶ Run Insights'));
    await waitFor(() => screen.getByText('Table LOGS has no primary key.'));

    expect(screen.queryByText('Add PRIMARY KEY constraint.')).toBeNull();
  });

  it('clicking finding card expands details', async () => {
    render(<InsightsPanel files={mockFiles} />);
    fireEvent.click(screen.getByText('▶ Run Insights'));
    await waitFor(() => screen.getByText('Table LOGS has no primary key.'));

    fireEvent.click(screen.getByText('Table LOGS has no primary key.'));

    await waitFor(() => screen.getByText('Add PRIMARY KEY constraint.'));
    expect(screen.getByText('Suggested fix:')).toBeDefined();
  });

  it('clicking again collapses details', async () => {
    render(<InsightsPanel files={mockFiles} />);
    fireEvent.click(screen.getByText('▶ Run Insights'));
    await waitFor(() => screen.getByText('Table LOGS has no primary key.'));

    const card = screen.getByText('Table LOGS has no primary key.');
    fireEvent.click(card);
    await waitFor(() => screen.getByText('Add PRIMARY KEY constraint.'));

    fireEvent.click(card);
    await waitFor(() => {
      expect(screen.queryByText('Add PRIMARY KEY constraint.')).toBeNull();
    });
  });

  it('shows detail text when expanded', async () => {
    render(<InsightsPanel files={mockFiles} />);
    fireEvent.click(screen.getByText('▶ Run Insights'));
    await waitFor(() => screen.getByText('Table LOGS has no FK relationships.'));

    fireEvent.click(screen.getByText('Table LOGS has no FK relationships.'));
    await waitFor(() => screen.getByText('Disconnected from schema.'));
    expect(screen.getByText('Disconnected from schema.')).toBeDefined();
  });
});

describe('InsightsPanel — empty state', () => {
  it('shows healthy message when no findings', async () => {
    vi.mocked(cli.runInsights).mockResolvedValue({
      version: '1',
      fingerprint: '',
      summary: { errors: 0, warnings: 0, infos: 0, total: 0, healthy: true },
      findings: { error: [], warning: [], info: [] },
    });

    render(<InsightsPanel files={mockFiles} />);
    fireEvent.click(screen.getByText('▶ Run Insights'));

    await waitFor(() => screen.getByText(/No issues found/));
  });
});
