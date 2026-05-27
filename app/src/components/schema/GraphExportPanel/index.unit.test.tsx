import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import GraphExportPanel from './index';

import type { MigrationFile } from '@/core/types';

import * as cli from '@/bridge/cli';

// ── Mocks ──────────────────────────────────────────────────────────────────

vi.mock('@/bridge/cli', () => ({
  IS_TAURI: false,
  CLI_AVAILABLE: true,
  CLI_MODE_LABEL: '⚡ Dev CLI',
  runGraphExport: vi.fn(),
}));

// Mock clipboard
Object.assign(navigator, {
  clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
});

// Mock URL.createObjectURL / revokeObjectURL
URL.createObjectURL = vi.fn().mockReturnValue('blob:mock');
URL.revokeObjectURL = vi.fn();

// ── Fixtures ───────────────────────────────────────────────────────────────

const mockFiles: MigrationFile[] = [
  { filename: 'V1__create.sql', sql: 'CREATE TABLE APP.USERS (ID NUMBER PRIMARY KEY);' },
];

const MERMAID_OUTPUT = 'erDiagram\n  USERS {\n    NUMBER ID PK\n  }';
const DOT_OUTPUT = 'digraph G { APP_USERS [shape=record]; }';
const HTML_OUTPUT = '<html><body><div id="graph"></div></body></html>';

// ── Tests ──────────────────────────────────────────────────────────────────

describe('GraphExportPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── idle state ─────────────────────────────────────────────────────────────

  describe('idle state', () => {
    it('renders all 8 format buttons', () => {
      render(<GraphExportPanel files={mockFiles} />);
      expect(screen.getByText('Mermaid ERD')).toBeTruthy();
      expect(screen.getByText('Graphviz DOT')).toBeTruthy();
      expect(screen.getByText('Excalidraw')).toBeTruthy();
      expect(screen.getByText('Draw.io')).toBeTruthy();
      expect(screen.getByText('Summary')).toBeTruthy();
      expect(screen.getByText('JSON')).toBeTruthy();
      expect(screen.getByText('Interactive HTML')).toBeTruthy();
      expect(screen.getByText('Report')).toBeTruthy();
    });

    it('renders generate button in idle state', () => {
      render(<GraphExportPanel files={mockFiles} />);
      expect(screen.getByText(/Generate Mermaid ERD/)).toBeTruthy();
    });

    it('renders idle prompt', () => {
      render(<GraphExportPanel files={mockFiles} />);
      expect(screen.getByText(/Select a format/)).toBeTruthy();
    });

    it('shows CLI mode badge', () => {
      render(<GraphExportPanel files={mockFiles} />);
      expect(screen.getByText(/⚡ (Tauri CLI|Dev CLI)/)).toBeTruthy();
    });

    it('selects mermaid format by default', () => {
      render(<GraphExportPanel files={mockFiles} />);
      const btn = screen.getAllByRole('button').find((b) => b.textContent?.includes('Mermaid ERD'));
      expect(btn?.className).toContain('active');
    });
  });

  // ── format selection ───────────────────────────────────────────────────────

  describe('format selection', () => {
    it('clicking a format marks it active and updates generate button label', () => {
      render(<GraphExportPanel files={mockFiles} />);
      const dotBtn = screen
        .getAllByRole('button')
        .find((b) => b.textContent?.includes('Graphviz DOT'));
      fireEvent.click(dotBtn!);
      expect(dotBtn?.className).toContain('active');
      expect(screen.getByText(/Generate Graphviz DOT/)).toBeTruthy();
    });

    it('switching format clears previous result', async () => {
      vi.mocked(cli.runGraphExport).mockResolvedValue(MERMAID_OUTPUT);
      render(<GraphExportPanel files={mockFiles} />);
      fireEvent.click(screen.getByText(/Generate Mermaid ERD/));
      await waitFor(() => screen.getByText(/erDiagram/));

      const dotBtn = screen
        .getAllByRole('button')
        .find((b) => b.textContent?.includes('Graphviz DOT'));
      fireEvent.click(dotBtn!);
      expect(screen.queryByText(/erDiagram/)).toBeNull();
    });
  });

  // ── generating ────────────────────────────────────────────────────────────

  describe('generating', () => {
    it('shows loading state while generating', async () => {
      vi.mocked(cli.runGraphExport).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(MERMAID_OUTPUT), 50)),
      );
      render(<GraphExportPanel files={mockFiles} />);
      fireEvent.click(screen.getByText(/Generate Mermaid ERD/));
      expect(screen.getByText(/Generating/)).toBeTruthy();
    });

    it('calls runGraphExport with correct format and files', async () => {
      vi.mocked(cli.runGraphExport).mockResolvedValue(MERMAID_OUTPUT);
      render(<GraphExportPanel files={mockFiles} />);
      fireEvent.click(screen.getByText(/Generate Mermaid ERD/));
      await waitFor(() =>
        expect(cli.runGraphExport).toHaveBeenCalledWith(mockFiles, {
          format: 'mermaid',
          resolution: 'medium',
        }),
      );
    });

    it('calls runGraphExport with dot format when dot is selected', async () => {
      vi.mocked(cli.runGraphExport).mockResolvedValue(DOT_OUTPUT);
      render(<GraphExportPanel files={mockFiles} />);
      const dotBtn = screen
        .getAllByRole('button')
        .find((b) => b.textContent?.includes('Graphviz DOT'));
      fireEvent.click(dotBtn!);
      fireEvent.click(screen.getByText(/Generate Graphviz DOT/));
      await waitFor(() =>
        expect(cli.runGraphExport).toHaveBeenCalledWith(mockFiles, {
          format: 'dot',
          resolution: 'medium',
        }),
      );
    });
  });

  // ── result ────────────────────────────────────────────────────────────────

  describe('result display', () => {
    it('shows code block with CLI output after generation', async () => {
      vi.mocked(cli.runGraphExport).mockResolvedValue(MERMAID_OUTPUT);
      render(<GraphExportPanel files={mockFiles} />);
      fireEvent.click(screen.getByText(/Generate Mermaid ERD/));
      await waitFor(() => screen.getByText(/erDiagram/));
      const pre = document.querySelector('.gep__code');
      expect(pre?.textContent).toContain('erDiagram');
    });

    it('shows copy and download buttons after generation', async () => {
      vi.mocked(cli.runGraphExport).mockResolvedValue(MERMAID_OUTPUT);
      render(<GraphExportPanel files={mockFiles} />);
      fireEvent.click(screen.getByText(/Generate Mermaid ERD/));
      await waitFor(() => screen.getByText(/⎘ Copy/));
      expect(screen.getByText(/↓ Download .mmd/)).toBeTruthy();
    });

    it('copy button writes content to clipboard', async () => {
      vi.mocked(cli.runGraphExport).mockResolvedValue(MERMAID_OUTPUT);
      render(<GraphExportPanel files={mockFiles} />);
      fireEvent.click(screen.getByText(/Generate Mermaid ERD/));
      await waitFor(() => screen.getByText(/⎘ Copy/));
      fireEvent.click(screen.getByText(/⎘ Copy/));
      await waitFor(() =>
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith(MERMAID_OUTPUT),
      );
    });

    it('shows mermaid.live link for mermaid format', async () => {
      vi.mocked(cli.runGraphExport).mockResolvedValue(MERMAID_OUTPUT);
      render(<GraphExportPanel files={mockFiles} />);
      fireEvent.click(screen.getByText(/Generate Mermaid ERD/));
      await waitFor(() => screen.getByText(/mermaid.live/));
      const link = screen.getByRole('link', { name: /mermaid.live/ });
      expect(link.getAttribute('href')).toBe('https://mermaid.live');
    });
  });

  // ── HTML format ───────────────────────────────────────────────────────────

  describe('HTML format', () => {
    it('shows iframe for HTML format', async () => {
      vi.mocked(cli.runGraphExport).mockResolvedValue(HTML_OUTPUT);
      render(<GraphExportPanel files={mockFiles} />);
      const htmlBtn = screen
        .getAllByRole('button')
        .find((b) => b.textContent?.includes('Interactive HTML'));
      fireEvent.click(htmlBtn!);
      fireEvent.click(screen.getByText(/Generate Interactive HTML/));
      await waitFor(() => screen.getByTitle(/preview/i));
      const iframe = screen.getByTitle(/preview/i) as HTMLIFrameElement;
      expect(iframe.getAttribute('srcdoc')).toBe(HTML_OUTPUT);
    });

    it('shows open-in-new-tab button for HTML format', async () => {
      vi.mocked(cli.runGraphExport).mockResolvedValue(HTML_OUTPUT);
      render(<GraphExportPanel files={mockFiles} />);
      const htmlBtn = screen
        .getAllByRole('button')
        .find((b) => b.textContent?.includes('Interactive HTML'));
      fireEvent.click(htmlBtn!);
      fireEvent.click(screen.getByText(/Generate Interactive HTML/));
      await waitFor(() => screen.getByText(/Open in new tab/));
    });
  });

  // ── external editor links ─────────────────────────────────────────────────

  describe('external editor links', () => {
    it('shows excalidraw.com link for excalidraw format', async () => {
      vi.mocked(cli.runGraphExport).mockResolvedValue('{"type":"excalidraw"}');
      render(<GraphExportPanel files={mockFiles} />);
      const exBtn = screen
        .getAllByRole('button')
        .find((b) => b.textContent?.includes('Excalidraw'));
      fireEvent.click(exBtn!);
      fireEvent.click(screen.getByText(/Generate Excalidraw/));
      await waitFor(() => screen.getByRole('link', { name: /Open Excalidraw/i }));
      const link = screen.getByRole('link', { name: /Open Excalidraw/i });
      expect(link.getAttribute('href')).toBe('https://excalidraw.com');
    });

    it('shows app.diagrams.net link for drawio format', async () => {
      vi.mocked(cli.runGraphExport).mockResolvedValue('<mxGraphModel/>');
      render(<GraphExportPanel files={mockFiles} />);
      const dioBtn = screen.getAllByRole('button').find((b) => b.textContent?.includes('Draw.io'));
      fireEvent.click(dioBtn!);
      fireEvent.click(screen.getByText(/Generate Draw\.io/));
      await waitFor(() => screen.getByRole('link', { name: /Open Draw\.io/i }));
      const link = screen.getByRole('link', { name: /Open Draw\.io/i });
      expect(link.getAttribute('href')).toBe('https://app.diagrams.net');
    });
  });

  // ── advanced options ──────────────────────────────────────────────────────

  describe('advanced options', () => {
    it('advanced panel is hidden by default', () => {
      render(<GraphExportPanel files={mockFiles} />);
      expect(screen.queryByPlaceholderText('Diagram title')).toBeNull();
    });

    it('toggle shows and hides advanced panel', () => {
      render(<GraphExportPanel files={mockFiles} />);
      const toggle = screen.getByText(/Advanced options/);
      fireEvent.click(toggle);
      expect(screen.getByPlaceholderText('Diagram title')).toBeTruthy();
      fireEvent.click(toggle);
      expect(screen.queryByPlaceholderText('Diagram title')).toBeNull();
    });

    it('passes title to runGraphExport', async () => {
      vi.mocked(cli.runGraphExport).mockResolvedValue(MERMAID_OUTPUT);
      render(<GraphExportPanel files={mockFiles} />);
      fireEvent.click(screen.getByText(/Advanced options/));
      fireEvent.change(screen.getByPlaceholderText('Diagram title'), {
        target: { value: 'My Schema' },
      });
      fireEvent.click(screen.getByText(/Generate Mermaid ERD/));
      await waitFor(() =>
        expect(cli.runGraphExport).toHaveBeenCalledWith(mockFiles, {
          format: 'mermaid',
          resolution: 'medium',
          title: 'My Schema',
        }),
      );
    });

    it('passes at-version to runGraphExport', async () => {
      vi.mocked(cli.runGraphExport).mockResolvedValue(MERMAID_OUTPUT);
      render(<GraphExportPanel files={mockFiles} />);
      fireEvent.click(screen.getByText(/Advanced options/));
      fireEvent.change(screen.getByPlaceholderText('e.g. 2'), { target: { value: '2' } });
      fireEvent.click(screen.getByText(/Generate Mermaid ERD/));
      await waitFor(() =>
        expect(cli.runGraphExport).toHaveBeenCalledWith(mockFiles, {
          format: 'mermaid',
          resolution: 'medium',
          atVersion: 2,
        }),
      );
    });

    it('passes no-split flag to runGraphExport', async () => {
      vi.mocked(cli.runGraphExport).mockResolvedValue(MERMAID_OUTPUT);
      render(<GraphExportPanel files={mockFiles} />);
      fireEvent.click(screen.getByText(/Advanced options/));
      const checkbox = screen.getByRole('checkbox');
      fireEvent.click(checkbox);
      fireEvent.click(screen.getByText(/Generate Mermaid ERD/));
      await waitFor(() =>
        expect(cli.runGraphExport).toHaveBeenCalledWith(mockFiles, {
          format: 'mermaid',
          resolution: 'medium',
          noSplit: true,
        }),
      );
    });
  });

  // ── error state ───────────────────────────────────────────────────────────

  describe('error state', () => {
    it('shows CLI error message directly', async () => {
      vi.mocked(cli.runGraphExport).mockRejectedValue(new Error('CLI failed: exit code 1'));
      render(<GraphExportPanel files={mockFiles} />);
      fireEvent.click(screen.getByText(/Generate Mermaid ERD/));
      await waitFor(() => screen.getByText(/CLI failed: exit code 1/));
    });

    it('does not show code block on CLI error', async () => {
      vi.mocked(cli.runGraphExport).mockRejectedValue(new Error('CLI failed'));
      render(<GraphExportPanel files={mockFiles} />);
      fireEvent.click(screen.getByText(/Generate Mermaid ERD/));
      await waitFor(() => screen.getByText(/CLI failed/));
      expect(screen.queryByText(MERMAID_OUTPUT)).toBeNull();
    });

    it('error is cleared on subsequent successful run', async () => {
      vi.mocked(cli.runGraphExport)
        .mockRejectedValueOnce(new Error('CLI failed'))
        .mockResolvedValueOnce(MERMAID_OUTPUT);
      render(<GraphExportPanel files={mockFiles} />);
      fireEvent.click(screen.getByText(/Generate Mermaid ERD/));
      await waitFor(() => screen.getByText(/CLI failed/));
      fireEvent.click(screen.getByText(/Generate Mermaid ERD/));
      await waitFor(() => screen.getByText(/erDiagram/));
      expect(screen.queryByText(/CLI failed/)).toBeNull();
    });
  });
});
