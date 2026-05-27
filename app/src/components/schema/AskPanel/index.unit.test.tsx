import { render } from '@testing-library/react';

import AskPanel from './index';

import type { VectorChunk } from '@/core/types';

const mockChunks: VectorChunk[] = [
  {
    id: 'users.id',
    type: 'text',
    title: 'APP.USERS.id',
    content: 'ID NUMBER PRIMARY KEY',
    meta: {},
    hint: 'primary key',
  },
  {
    id: 'users.email',
    type: 'text',
    title: 'APP.USERS.email',
    content: 'EMAIL VARCHAR2(255)',
    meta: {},
    hint: 'indexed email',
  },
];

describe('AskPanel', () => {
  it('renders the empty-state prompt when chunks are empty', () => {
    const { getByText } = render(<AskPanel chunks={[]} />);
    expect(getByText('Parse your migrations first to enable schema queries.')).toBeDefined();
  });

  it('renders the header when chunks are provided', () => {
    const { getByText } = render(<AskPanel chunks={mockChunks} />);
    expect(getByText('Schema Q&A')).toBeDefined();
  });

  it('renders example questions when no prompt has been assembled', () => {
    const { getByText } = render(<AskPanel chunks={mockChunks} />);
    expect(getByText('Which tables have cascading deletes?')).toBeDefined();
  });
});
