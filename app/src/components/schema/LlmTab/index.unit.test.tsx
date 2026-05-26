import { render } from '@testing-library/react';

import LlmTab from './index';

import type { VectorChunk } from '@/core/types';

const mockChunks: VectorChunk[] = [
  {
    id: 'chunk-1',
    type: 'table',
    title: 'APP.USERS (table definition)',
    content: 'CREATE TABLE APP.USERS (ID NUMBER);',
    meta: { table: 'APP.USERS' },
    hint: 'Full column list for APP.USERS',
  },
  {
    id: 'chunk-2',
    type: 'edge',
    title: 'FK: APP.ORDERS → APP.USERS',
    content: 'ALTER TABLE APP.ORDERS ADD CONSTRAINT ...',
    meta: { from: 'APP.ORDERS', to: 'APP.USERS' },
    hint: 'Foreign key relationship between ORDERS and USERS',
  },
];

describe('LlmTab', () => {
  it('renders the first chunk title in the sidebar', () => {
    const { getAllByText } = render(<LlmTab chunks={mockChunks} />);
    // Title appears in both the sidebar button and the detail panel header.
    expect(getAllByText('APP.USERS (table definition)').length).toBeGreaterThan(0);
  });

  it('renders the chunk count in the sidebar header', () => {
    const { getByText } = render(<LlmTab chunks={mockChunks} />);
    expect(getByText('Chunks (2)')).toBeDefined();
  });
});
