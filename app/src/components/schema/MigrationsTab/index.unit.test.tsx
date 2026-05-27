import { render, fireEvent, waitFor, act } from '@testing-library/react';
import { vi } from 'vitest';

import MigrationsTab from './index';

import type { MigrationFile } from '@/core/types';
import type { HealthResult } from '@/bridge/cli';

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock('@/bridge/cli', () => ({
  CLI_AVAILABLE: true,
  runHealth: vi.fn(),
}));

import { runHealth } from '@/bridge/cli';
const mockRunHealth = runHealth as ReturnType<typeof vi.fn>;

const mockHealthResult: HealthResult = {
  folder: 'test/',
  timestamp: '2026-01-01T00:00:00Z',
  summary: {
    total_migrations: 2,
    safe_migrations: 1,
    unsafe_migrations: 0,
    irreversible_migrations: 1,
    safe_percentage: 50,
  },
  findings: { errors: 0, warnings: 2, infos: 0, by_code: {} },
  migrations: [
    { filename: 'V1__create_users.sql', status: 'safe', errors: 0, warnings: 0, has_drop_table: false, has_drop_column: false },
    { filename: 'V2__add_orders.sql', status: 'irreversible', errors: 0, warnings: 1, has_drop_table: false, has_drop_column: true },
  ],
  health_score: { score: 75, grade: 'good', breakdown: { base: 100, error_penalty: 0, warning_penalty: -15, irreversible_penalty: -10 } },
  recommendation: 'Review 2 warnings.',
};

// ── Fixtures ─────────────────────────────────────────────────────────────────

const orderedFiles: MigrationFile[] = [
  { filename: 'V1__create_users.sql', sql: 'CREATE TABLE users (id NUMBER);' },
  { filename: 'V2__add_orders.sql',   sql: 'CREATE TABLE orders (id NUMBER);' },
];

const outOfOrderFiles: MigrationFile[] = [
  { filename: 'V1__a.sql', sql: '' },
  { filename: 'V3__b.sql', sql: '' },
  { filename: 'V2__c.sql', sql: '' },
];

const gapFiles: MigrationFile[] = [
  { filename: 'V1__a.sql', sql: '' },
  { filename: 'V4__b.sql', sql: '' },
];

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('MigrationsTab', () => {
  describe('basic rendering', () => {
    it('renders the migration filename in the input', () => {
      const { getByDisplayValue } = render(<MigrationsTab files={orderedFiles} onChange={() => {}} />);
      expect(getByDisplayValue('V1__create_users.sql')).toBeDefined();
    });

    it('calls onChange when "Add Migration File" is clicked', () => {
      const handleChange = vi.fn();
      const { getByText } = render(<MigrationsTab files={orderedFiles} onChange={handleChange} />);
      fireEvent.click(getByText('+ Add Migration File'));
      expect(handleChange).toHaveBeenCalledOnce();
    });
  });

  describe('validation banner — auto-runs on mount', () => {
    it('does not show a banner for correctly ordered files', () => {
      const { queryByRole } = render(<MigrationsTab files={orderedFiles} onChange={() => {}} />);
      expect(queryByRole('alert')).toBeNull();
    });

    it('shows an error banner when files are out of order', () => {
      const { getByRole } = render(<MigrationsTab files={outOfOrderFiles} onChange={() => {}} />);
      const alert = getByRole('alert');
      expect(alert.textContent).toContain('Ordering Errors');
    });

    it('shows a warning banner for version gaps', () => {
      const { getByRole } = render(<MigrationsTab files={gapFiles} onChange={() => {}} />);
      const alert = getByRole('alert');
      expect(alert.textContent).toContain('Ordering Warnings');
      expect(alert.textContent).toContain('V2');
    });

    it('dismisses the banner when × is clicked', () => {
      const { getByRole, queryByRole } = render(<MigrationsTab files={gapFiles} onChange={() => {}} />);
      const dismissBtn = getByRole('alert').querySelector('.validation-banner__dismiss') as HTMLElement;
      fireEvent.click(dismissBtn);
      expect(queryByRole('alert')).toBeNull();
    });
  });

  describe('health check button', () => {
    beforeEach(() => {
      mockRunHealth.mockReset();
    });

    it('shows "🩺 Health Check" button when CLI_AVAILABLE and files present', () => {
      const { getByText } = render(<MigrationsTab files={orderedFiles} onChange={() => {}} />);
      expect(getByText('🩺 Health Check')).toBeDefined();
    });

    it('calls runHealth on click and shows health badge', async () => {
      mockRunHealth.mockResolvedValue(mockHealthResult);
      const { getByText } = render(<MigrationsTab files={orderedFiles} onChange={() => {}} />);
      await act(async () => {
        fireEvent.click(getByText('🩺 Health Check'));
      });
      await waitFor(() => {
        expect(getByText(/Good.*75\/100/)).toBeDefined();
      });
    });

    it('expands health panel after health check', async () => {
      mockRunHealth.mockResolvedValue(mockHealthResult);
      const { getByText, getByRole } = render(<MigrationsTab files={orderedFiles} onChange={() => {}} />);
      await act(async () => {
        fireEvent.click(getByText('🩺 Health Check'));
      });
      await waitFor(() => {
        expect(getByText('Migration Health Report')).toBeDefined();
      });
      // Recommendation visible
      expect(getByText('Review 2 warnings.')).toBeDefined();
    });

    it('toggles health panel when badge is clicked', async () => {
      mockRunHealth.mockResolvedValue(mockHealthResult);
      const { getByText, queryByText } = render(<MigrationsTab files={orderedFiles} onChange={() => {}} />);
      await act(async () => {
        fireEvent.click(getByText('🩺 Health Check'));
      });
      await waitFor(() => expect(getByText('Migration Health Report')).toBeDefined());
      // Click badge → collapse
      fireEvent.click(getByText(/Good.*75\/100/));
      expect(queryByText('Migration Health Report')).toBeNull();
    });

    it('shows error message when runHealth throws', async () => {
      mockRunHealth.mockRejectedValue(new Error('CLI unavailable'));
      const { getByText, getByRole } = render(<MigrationsTab files={orderedFiles} onChange={() => {}} />);
      await act(async () => {
        fireEvent.click(getByText('🩺 Health Check'));
      });
      await waitFor(() => {
        expect(getByRole('alert').textContent).toContain('CLI unavailable');
      });
    });
  });

  describe('per-file health dots', () => {
    it('shows status dots on file headers after health check', async () => {
      mockRunHealth.mockResolvedValue(mockHealthResult);
      const { getByText, container } = render(
        <MigrationsTab files={orderedFiles} onChange={() => {}} />,
      );
      await act(async () => {
        fireEvent.click(getByText('🩺 Health Check'));
      });
      await waitFor(() => {
        const dots = container.querySelectorAll('.file-health-dot');
        expect(dots.length).toBe(2);
      });
    });
  });
});
