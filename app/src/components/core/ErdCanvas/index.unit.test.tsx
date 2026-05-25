import { render } from '@testing-library/react';
import ErdCanvas from './index';
import type { SchemaGraph } from '../../../core/types';

const mockGraph: SchemaGraph = {
  tables: new Map([
    ['APP.USERS', {
      id: 'APP.USERS', schema: 'APP', name: 'USERS', full: 'APP.USERS',
      columns: [
        { name: 'ID', type: 'NUMBER', precision: null, scale: null, nullable: false, default: null, primaryKey: true, unique: false, references: null },
      ],
      constraints: [{ name: 'PK_USERS', type: 'primary_key', columns: ['ID'] }],
      indexes: [], comments: {}, createdIn: '1', modifiedIn: [],
    }],
  ]),
  seqs: new Map(),
  edges: [],
  migHist: [],
};

describe('ErdCanvas', () => {
  it('renders the SVG canvas', () => {
    const { container } = render(
      <ErdCanvas graph={mockGraph} selectedTable={null} onSelectTable={() => {}} />,
    );
    expect(container.querySelector('svg')).toBeDefined();
  });

  it('renders a table node for each table in the graph', () => {
    const { getByText } = render(
      <ErdCanvas graph={mockGraph} selectedTable={null} onSelectTable={() => {}} />,
    );
    expect(getByText('USERS')).toBeDefined();
  });
});
