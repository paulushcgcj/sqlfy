import { render } from '@testing-library/react';
import TableDetail from './index';
import type { SchemaGraph } from '../../../core/types';

const mockGraph: SchemaGraph = {
  tables: new Map([
    ['APP.USERS', {
      id: 'APP.USERS', schema: 'APP', name: 'USERS', full: 'APP.USERS',
      columns: [
        { name: 'ID', type: 'NUMBER', precision: null, scale: null, nullable: false, default: null, primaryKey: true, unique: false, references: null },
        { name: 'EMAIL', type: 'VARCHAR2', precision: 255, scale: null, nullable: false, default: null, primaryKey: false, unique: true, references: null },
      ],
      constraints: [{ name: 'PK_USERS', type: 'primary_key', columns: ['ID'] }],
      indexes: [], comments: {}, createdIn: '1', modifiedIn: [],
    }],
  ]),
  seqs: new Map(),
  edges: [],
  migHist: [],
};

describe('TableDetail', () => {
  it('renders column names for a known table key', () => {
    const { getByText } = render(
      <TableDetail tableKey="APP.USERS" graph={mockGraph} />,
    );
    expect(getByText('ID')).toBeDefined();
    expect(getByText('EMAIL')).toBeDefined();
  });

  it('shows fallback text for an unknown table key', () => {
    const { getByText } = render(
      <TableDetail tableKey="DOES_NOT_EXIST" graph={mockGraph} />,
    );
    expect(getByText('Select a table to view details')).toBeDefined();
  });

  it('renders the PK badge for the primary key column', () => {
    const { getAllByText } = render(
      <TableDetail tableKey="APP.USERS" graph={mockGraph} />,
    );
    expect(getAllByText('PK').length).toBeGreaterThan(0);
  });
});
