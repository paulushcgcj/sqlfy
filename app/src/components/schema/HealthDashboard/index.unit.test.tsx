import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import HealthDashboard from './index';

import type { HealthResult } from '@/bridge/cli';

import * as cliModule from '@/bridge/cli';

// ─── Mocks ────────────────────────────────────────────────────────────────────

const mockRunHealth = vi.fn();
vi.mock('@/bridge/cli', () => ({
  CLI_AVAILABLE: true,
  CLI_MODE_LABEL: '⚡ CLI (Tauri)',
  runHealth: mockRunHealth,
}));

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const mockHealthResult: HealthResult = {
  folder: '/path/to/migrations',
  timestamp: '2026-06-01T12:00:00Z',
  summary: {
    totalMigrations: 8,
    safeMigrations: 6,
    unsafeMigrations: 1,
    irreversibleMigrations: 1,
    safePercentage: 75,
  },
  findings: {
    errors: 1,
    warnings: 2,
    infos: 3,
    byCode: {
      ADD_NOT_NULL_NO_DEFAULT: 2,
      SELECT_STAR_VIEW: 1,
      TRIGGER_WITH_BUSINESS_LOGIC: 1,
      LARGE_DELETE_NO_WHERE: 1,
    },
  },
  migrations: [
    {
      filename: 'V1__init.sql',
      status: 'safe',
      errors: 0,
      warnings: 0,
      hasDropTable: false,
      hasDropColumn: false,
    },
    {
      filename: 'V2__add_users.sql',
      status: 'safe',
      errors: 0,
      warnings: 1,
      hasDropTable: false,
      hasDropColumn: false,
    },
    {
      filename: 'V3__add_orders.sql',
      status: 'unsafe',
      errors: 1,
      warnings: 0,
      hasDropTable: false,
      hasDropColumn: false,
    },
    {
      filename: 'V4__drop_legacy.sql',
      status: 'irreversible',
      errors: 0,
      warnings: 1,
      hasDropTable: true,
      hasDropColumn: false,
    },
  ],
  healthScore: {
    score: 60,
    grade: 'warning',
    breakdown: {
      base: 100,
      errorPenalty: -20,
      warningPenalty: -10,
      irreversiblePenalty: -10,
    },
  },
  recommendation: 'Review 2 warnings and fix 1 error before production deployment.',
};

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('HealthDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the run button and hint', () => {
    render(<HealthDashboard files={[]} />);

    expect(screen.getByText(/Run Health Check/i)).toBeDefined();
    expect(screen.getByText(/⚡ CLI \(Tauri\)/i)).toBeDefined();
  });

  it('renders "CLI required" when CLI_AVAILABLE is false', () => {
    vi.mocked(cliModule).CLI_AVAILABLE = false;

    render(<HealthDashboard files={[]} />);

    expect(screen.getByText(/CLI required/i)).toBeDefined();
    expect(screen.getByText(/Python CLI/i)).toBeDefined();
  });

  it('calls runHealth and displays results after clicking the button', async () => {
    mockRunHealth.mockResolvedValue(mockHealthResult);

    render(<HealthDashboard files={[{ filename: 'V1__test.sql', sql: 'SELECT 1;' }]} />);

    const button = screen.getByText(/Run Health Check/i);
    fireEvent.click(button);

    await waitFor(() => {
      expect(mockRunHealth).toHaveBeenCalled();
    });

    // Check that score is displayed
    expect(screen.getByText('60')).toBeDefined();
  });

  it('displays summary stats after running health check', async () => {
    mockRunHealth.mockResolvedValue(mockHealthResult);

    render(<HealthDashboard files={[{ filename: 'V1__test.sql', sql: 'SELECT 1;' }]} />);

    fireEvent.click(screen.getByText(/Run Health Check/i));

    await waitFor(() => {
      expect(screen.getByText('8')).toBeDefined(); // total migrations
      expect(screen.getByText('6')).toBeDefined(); // safe migrations
      expect(screen.getByText('1')).toBeDefined(); // unsafe migrations
    });
  });

  it('displays findings breakdown', async () => {
    mockRunHealth.mockResolvedValue(mockHealthResult);

    render(<HealthDashboard files={[{ filename: 'V1__test.sql', sql: 'SELECT 1;' }]} />);

    fireEvent.click(screen.getByText(/Run Health Check/i));

    await waitFor(() => {
      expect(screen.getByText(/Findings Summary/i)).toBeDefined();
    });
  });

  it('displays top issue codes', async () => {
    mockRunHealth.mockResolvedValue(mockHealthResult);

    render(<HealthDashboard files={[{ filename: 'V1__test.sql', sql: 'SELECT 1;' }]} />);

    fireEvent.click(screen.getByText(/Run Health Check/i));

    await waitFor(() => {
      expect(screen.getByText('ADD_NOT_NULL_NO_DEFAULT')).toBeDefined();
    });
  });

  it('displays migration status table', async () => {
    mockRunHealth.mockResolvedValue(mockHealthResult);

    render(<HealthDashboard files={[{ filename: 'V1__test.sql', sql: 'SELECT 1;' }]} />);

    fireEvent.click(screen.getByText(/Run Health Check/i));

    await waitFor(() => {
      expect(screen.getByText('V1__init.sql')).toBeDefined();
      expect(screen.getByText('V4__drop_legacy.sql')).toBeDefined();
    });
  });

  it('displays score breakdown', async () => {
    mockRunHealth.mockResolvedValue(mockHealthResult);

    render(<HealthDashboard files={[{ filename: 'V1__test.sql', sql: 'SELECT 1;' }]} />);

    fireEvent.click(screen.getByText(/Run Health Check/i));

    await waitFor(() => {
      expect(screen.getByText(/Score Breakdown/i)).toBeDefined();
      expect(screen.getByText(/Base Score/i)).toBeDefined();
    });
  });

  it('displays recommendation', async () => {
    mockRunHealth.mockResolvedValue(mockHealthResult);

    render(<HealthDashboard files={[{ filename: 'V1__test.sql', sql: 'SELECT 1;' }]} />);

    fireEvent.click(screen.getByText(/Run Health Check/i));

    await waitFor(() => {
      expect(screen.getByText(/Review 2 warnings and fix 1 error/i)).toBeDefined();
    });
  });

  it('shows loading state while fetching', () => {
    mockRunHealth.mockImplementation(
      () =>
        new Promise((resolve) => {
          setTimeout(() => resolve(mockHealthResult), 100);
        }),
    );

    render(<HealthDashboard files={[{ filename: 'V1__test.sql', sql: 'SELECT 1;' }]} />);

    const button = screen.getByText(/Run Health Check/i);
    fireEvent.click(button);

    expect(screen.getByText(/Checking…/i)).toBeDefined();
  });

  it('displays error message on failure', async () => {
    mockRunHealth.mockRejectedValue(new Error('Health check failed'));

    render(<HealthDashboard files={[{ filename: 'V1__test.sql', sql: 'SELECT 1;' }]} />);

    fireEvent.click(screen.getByText(/Run Health Check/i));

    await waitFor(() => {
      expect(screen.getByText(/Health check failed/i)).toBeDefined();
    });
  });

  it('shows destructive operation indicators', async () => {
    mockRunHealth.mockResolvedValue(mockHealthResult);

    render(<HealthDashboard files={[{ filename: 'V1__test.sql', sql: 'SELECT 1;' }]} />);

    fireEvent.click(screen.getByText(/Run Health Check/i));

    await waitFor(() => {
      // V4__drop_legacy.sql has hasDropTable: true
      const tableRows = screen.getAllByText(/TABLE/);
      expect(tableRows.length).toBeGreaterThan(0);
    });
  });
});
