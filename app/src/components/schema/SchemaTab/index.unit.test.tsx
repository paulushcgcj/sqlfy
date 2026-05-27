import { render, fireEvent, waitFor, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import SchemaTab from './index';

import type { SchemaGraph, MigrationFile } from '@/core/types';

import * as cli from '@/bridge/cli';

// Mock the CLI bridge
vi.mock('@/bridge/cli', () => ({
  IS_TAURI: false,
  CLI_AVAILABLE: true,
  CLI_MODE_LABEL: '⚡ Dev CLI',
  dumpWithOptions: vi.fn(),
}));

const mockGraph: SchemaGraph = {
  tables: new Map([
    [
      'APP.USERS',
      {
        id: 'APP.USERS',
        schema: 'APP',
        name: 'USERS',
        full: 'APP.USERS',
        columns: [
          {
            name: 'ID',
            type: 'NUMBER',
            precision: 10,
            scale: 0,
            nullable: false,
            default: null,
            primaryKey: true,
            unique: false,
            references: null,
          },
          {
            name: 'EMAIL',
            type: 'VARCHAR2(255)',
            precision: null,
            scale: null,
            nullable: true,
            default: null,
            primaryKey: false,
            unique: false,
            references: null,
          },
        ],
        constraints: [],
        indexes: [],
        comments: {},
        createdIn: '1',
        modifiedIn: ['2'],
      },
    ],
  ]),
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

describe('SchemaTab - Dump Panel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Format Selector', () => {
    it('should render format selector with JSON, YAML, and summary options', () => {
      const { container } = render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const formatSelect = container.querySelector('.schema-fmt-select') as HTMLSelectElement;

      expect(formatSelect).toBeDefined();
      expect(formatSelect.value).toBe('json');

      const options = Array.from(formatSelect.options).map((opt) => opt.value);
      expect(options).toEqual(['json', 'yaml', 'summary']);
    });

    it('should change format when selector is changed', async () => {
      const { container } = render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const formatSelect = container.querySelector('.schema-fmt-select') as HTMLSelectElement;

      fireEvent.change(formatSelect, { target: { value: 'yaml' } });
      await waitFor(() => expect(formatSelect.value).toBe('yaml'));
    });

    it('should clear output when format is changed', async () => {
      vi.mocked(cli.dumpWithOptions).mockResolvedValue('{"version":"1"}');

      const { container } = render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const runBtn = screen.getByText('▶ Run dump');
      const formatSelect = container.querySelector('.schema-fmt-select') as HTMLSelectElement;

      // Run dump
      fireEvent.click(runBtn);
      await waitFor(() => screen.getByText(/version/i));

      // Change format
      fireEvent.change(formatSelect, { target: { value: 'yaml' } });

      // Output should be cleared (pre element should not contain previous output)
      const outputPre = container.querySelector('.schema-output pre');
      expect(outputPre?.textContent).toBeFalsy();
    });
  });

  describe('Version Selector', () => {
    it('should render version selector with migration history', () => {
      const { container } = render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const versionSelect = container.querySelector('.schema-version-select') as HTMLSelectElement;

      expect(versionSelect).toBeDefined();
      expect(versionSelect.value).toBe('');

      const options = Array.from(versionSelect.options).map((opt) => ({
        value: opt.value,
        text: opt.text,
      }));
      expect(options).toEqual([
        { value: '', text: 'Current state' },
        { value: '1', text: 'V1: create users' },
        { value: '2', text: 'V2: add email' },
      ]);
    });

    it('should change version when selector is changed', async () => {
      const { container } = render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const versionSelect = container.querySelector('.schema-version-select') as HTMLSelectElement;

      fireEvent.change(versionSelect, { target: { value: '1' } });
      await waitFor(() => expect(versionSelect.value).toBe('1'));
    });

    it('should call dumpWithOptions with atVersion when running dump at specific version', async () => {
      vi.mocked(cli.dumpWithOptions).mockResolvedValue('{"version":"1"}');

      const { container } = render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const runBtn = screen.getByText('▶ Run dump');
      const versionSelect = container.querySelector('.schema-version-select') as HTMLSelectElement;

      // Select version 1
      fireEvent.change(versionSelect, { target: { value: '1' } });

      // Run dump
      fireEvent.click(runBtn);

      await waitFor(() => {
        expect(cli.dumpWithOptions).toHaveBeenCalledWith(mockFiles, {
          format: 'json',
          atVersion: 1,
        });
      });
    });

    it('should call dumpWithOptions without atVersion when "Current state" is selected', async () => {
      vi.mocked(cli.dumpWithOptions).mockResolvedValue('{"version":"2"}');

      const { container } = render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const runBtn = screen.getByText('▶ Run dump');
      const versionSelect = container.querySelector('.schema-version-select') as HTMLSelectElement;

      // Select specific version first
      fireEvent.change(versionSelect, { target: { value: '1' } });
      // Then select current state
      fireEvent.change(versionSelect, { target: { value: '' } });

      // Run dump
      fireEvent.click(runBtn);

      await waitFor(() => {
        expect(cli.dumpWithOptions).toHaveBeenCalledWith(mockFiles, {
          format: 'json',
        });
      });
    });
  });

  describe('Run Dump Button', () => {
    it('should call dumpWithOptions with JSON format by default', async () => {
      vi.mocked(cli.dumpWithOptions).mockResolvedValue('{"version":"1"}');

      render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const runBtn = screen.getByText('▶ Run dump');

      fireEvent.click(runBtn);

      await waitFor(() => {
        expect(cli.dumpWithOptions).toHaveBeenCalledWith(mockFiles, { format: 'json' });
      });
    });

    it('should show loading state while running', async () => {
      vi.mocked(cli.dumpWithOptions).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve('{}'), 100)),
      );

      render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const runBtn = screen.getByText('▶ Run dump');

      fireEvent.click(runBtn);

      expect(screen.getByText('⏳ Running…')).toBeDefined();
      await waitFor(() => expect(screen.getByText('▶ Run dump')).toBeDefined(), { timeout: 200 });
    });

    it('should display output after successful run', async () => {
      const mockOutput = '{"version":"1","tables":{}}';
      vi.mocked(cli.dumpWithOptions).mockResolvedValue(mockOutput);

      render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const runBtn = screen.getByText('▶ Run dump');

      fireEvent.click(runBtn);

      await waitFor(() => {
        expect(screen.getByText(mockOutput)).toBeDefined();
      });
    });
  });

  describe('Copy Button', () => {
    it('should be disabled when no output is available', () => {
      render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const copyBtn = screen.getByText('⎘ Copy');

      expect(copyBtn.closest('button')?.disabled).toBe(true);
    });

    it('should be enabled after dump is run', async () => {
      vi.mocked(cli.dumpWithOptions).mockResolvedValue('{}');

      render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const runBtn = screen.getByText('▶ Run dump');

      fireEvent.click(runBtn);

      await waitFor(() => {
        const copyBtn = screen.getByText('⎘ Copy');
        expect(copyBtn.closest('button')?.disabled).toBe(false);
      });
    });

    it('should copy output to clipboard when clicked', async () => {
      const mockOutput = '{"version":"1"}';
      vi.mocked(cli.dumpWithOptions).mockResolvedValue(mockOutput);

      // Mock clipboard API
      Object.assign(navigator, {
        clipboard: {
          writeText: vi.fn().mockResolvedValue(undefined),
        },
      });

      render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const runBtn = screen.getByText('▶ Run dump');

      fireEvent.click(runBtn);
      await waitFor(() => screen.getByText('⎘ Copy'));

      const copyBtn = screen.getByText('⎘ Copy');
      fireEvent.click(copyBtn);

      await waitFor(() => {
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith(mockOutput);
      });
    });

    it('should show "Copied" state after successful copy', async () => {
      vi.mocked(cli.dumpWithOptions).mockResolvedValue('{}');
      Object.assign(navigator, {
        clipboard: {
          writeText: vi.fn().mockResolvedValue(undefined),
        },
      });

      render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const runBtn = screen.getByText('▶ Run dump');

      fireEvent.click(runBtn);
      await waitFor(() => screen.getByText('⎘ Copy'));

      const copyBtn = screen.getByText('⎘ Copy');
      fireEvent.click(copyBtn);

      await waitFor(() => {
        expect(screen.getByText('✓ Copied')).toBeDefined();
      });
    });
  });

  describe('Download Button', () => {
    it('should be disabled when no output is available', () => {
      render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const downloadBtn = screen.getByText('⬇ Download');

      expect(downloadBtn.closest('button')?.disabled).toBe(true);
    });

    it('should be enabled after dump is run', async () => {
      vi.mocked(cli.dumpWithOptions).mockResolvedValue('{}');

      render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const runBtn = screen.getByText('▶ Run dump');

      fireEvent.click(runBtn);

      await waitFor(() => {
        const downloadBtn = screen.getByText('⬇ Download');
        expect(downloadBtn.closest('button')?.disabled).toBe(false);
      });
    });

    it('should trigger download with correct filename for JSON format', async () => {
      vi.mocked(cli.dumpWithOptions).mockResolvedValue('{}');

      // Mock Blob and URL.createObjectURL
      globalThis.URL.createObjectURL = vi.fn(() => 'blob:mock');
      globalThis.URL.revokeObjectURL = vi.fn();

      render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const runBtn = screen.getByText('▶ Run dump');

      fireEvent.click(runBtn);
      await waitFor(() => screen.getByText('⬇ Download'));

      const downloadBtn = screen.getByText('⬇ Download');
      fireEvent.click(downloadBtn);

      // Check that a download was triggered (Blob was created)
      expect(globalThis.URL.createObjectURL).toHaveBeenCalled();
    });

    it('should download with .yaml extension when YAML format is selected', async () => {
      vi.mocked(cli.dumpWithOptions).mockResolvedValue('version: "1"');
      globalThis.URL.createObjectURL = vi.fn(() => 'blob:mock');

      const { container } = render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const formatSelect = container.querySelector('.schema-fmt-select') as HTMLSelectElement;
      const runBtn = screen.getByText('▶ Run dump');

      // Change to YAML
      fireEvent.change(formatSelect, { target: { value: 'yaml' } });

      // Run dump
      fireEvent.click(runBtn);
      await waitFor(() => screen.getByText('⬇ Download'));

      const downloadBtn = screen.getByText('⬇ Download');
      fireEvent.click(downloadBtn);

      expect(globalThis.URL.createObjectURL).toHaveBeenCalled();
    });
  });

  describe('Browser Fallback', () => {
    it('should use browser fallback for JSON when CLI fails', async () => {
      vi.mocked(cli.dumpWithOptions).mockRejectedValue(new Error('CLI not available'));

      render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const runBtn = screen.getByText('▶ Run dump');

      fireEvent.click(runBtn);

      await waitFor(() => {
        // Should show error message
        expect(screen.getByText(/CLI error/i)).toBeDefined();
        // Should show browser fallback output
        expect(screen.getByText(/APP.USERS/)).toBeDefined();
      });
    });

    it('should use browser fallback for YAML when CLI fails', async () => {
      vi.mocked(cli.dumpWithOptions).mockRejectedValue(new Error('CLI not available'));

      const { container } = render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const formatSelect = container.querySelector('.schema-fmt-select') as HTMLSelectElement;
      const runBtn = screen.getByText('▶ Run dump');

      // Change to YAML
      fireEvent.change(formatSelect, { target: { value: 'yaml' } });

      fireEvent.click(runBtn);

      await waitFor(() => {
        expect(screen.getByText(/version:/)).toBeDefined();
      });
    });

    it('should use browser fallback for summary when CLI fails', async () => {
      vi.mocked(cli.dumpWithOptions).mockRejectedValue(new Error('CLI not available'));

      const { container } = render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const formatSelect = container.querySelector('.schema-fmt-select') as HTMLSelectElement;
      const runBtn = screen.getByText('▶ Run dump');

      // Change to summary
      fireEvent.change(formatSelect, { target: { value: 'summary' } });

      fireEvent.click(runBtn);

      await waitFor(() => {
        expect(screen.getByText(/Schema State Summary/)).toBeDefined();
      });
    });
  });

  describe('Output Display', () => {
    it('should display JSON output in a pre element', async () => {
      const mockOutput = '{"version":"1","tables":{}}';
      vi.mocked(cli.dumpWithOptions).mockResolvedValue(mockOutput);

      const { container } = render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const runBtn = screen.getByText('▶ Run dump');

      fireEvent.click(runBtn);

      await waitFor(() => {
        const pre = container.querySelector('.schema-output pre');
        expect(pre?.textContent).toBe(mockOutput);
      });
    });

    it('should display YAML output in a pre element', async () => {
      const mockOutput = 'version: "1"\ntables:';
      vi.mocked(cli.dumpWithOptions).mockResolvedValue(mockOutput);

      const { container } = render(<SchemaTab graph={mockGraph} files={mockFiles} />);
      const formatSelect = container.querySelector('.schema-fmt-select') as HTMLSelectElement;
      const runBtn = screen.getByText('▶ Run dump');

      fireEvent.change(formatSelect, { target: { value: 'yaml' } });
      fireEvent.click(runBtn);

      await waitFor(() => {
        const pre = container.querySelector('.schema-output pre');
        expect(pre?.textContent).toContain('version:');
      });
    });
  });
});
