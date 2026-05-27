import { render } from '@testing-library/react';

import AskPanel from './index';

import type { SchemaGraph } from '@/core/types';

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
            precision: null,
            scale: null,
            nullable: false,
            default: null,
            primaryKey: true,
            unique: false,
            references: null,
          },
          {
            name: 'EMAIL',
            type: 'VARCHAR2',
            precision: 255,
            scale: null,
            nullable: false,
            default: null,
            primaryKey: false,
            unique: true,
            references: null,
          },
        ],
        constraints: [{ name: 'PK_USERS', type: 'primary_key', columns: ['ID'] }],
        indexes: [],
        comments: {},
        createdIn: '1',
        modifiedIn: [],
      },
    ],
  ]),
  seqs: new Map(),
  edges: [],
  migHist: [],
};

describe('AskPanel', () => {
  it('renders the empty-state prompt when graph is null', () => {
    const { getByText } = render(<AskPanel graph={null} />);
    expect(getByText('Parse your migrations first to enable schema queries.')).toBeDefined();
  });

  it('renders the header when graph is provided', () => {
    const { getByText } = render(<AskPanel graph={mockGraph} />);
    expect(getByText('Schema Q&A')).toBeDefined();
  });

  it('renders example questions when no prompt has been assembled', () => {
    const { getByText } = render(<AskPanel graph={mockGraph} />);
    expect(getByText('Which tables have cascading deletes?')).toBeDefined();
  });
});
