import { render } from '@testing-library/react';
import GraphTab from './index';
import type { SchemaGraph } from '@/core/types';

const mockGraph: SchemaGraph = {
  tables: new Map([
    ['APP.USERS', {
      id: 'APP.USERS', schema: 'APP', name: 'USERS', full: 'APP.USERS',
      columns: [
        { name: 'ID', type: 'NUMBER', precision: null, scale: null, nullable: false, default: null, primaryKey: true, unique: false, references: null },
      ],
      constraints: [], indexes: [], comments: {}, createdIn: '1', modifiedIn: [],
    }],
  ]),
  seqs: new Map(),
  edges: [],
  migHist: [],
};

describe('GraphTab', () => {
  it('renders the table name in the sidebar', () => {
    const { getAllByText } = render(
      <GraphTab graph={mockGraph} selectedTable={null} onSelectTable={() => {}} />,
    );
    // 'USERS' appears in the sidebar button and the ERD canvas SVG node.
    expect(getAllByText('USERS').length).toBeGreaterThan(0);
  });

  it('shows the "no-data" fallback when no table is selected', () => {
    const { getByText } = render(
      <GraphTab graph={mockGraph} selectedTable={null} onSelectTable={() => {}} />,
    );
    expect(getByText('Select a table to view details')).toBeDefined();
  });
});
