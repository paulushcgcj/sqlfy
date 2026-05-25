import { render, fireEvent } from '@testing-library/react';
import MigrationsTab from './index';
import type { MigrationFile } from '../../../core/types';

const mockFiles: MigrationFile[] = [
  { filename: 'V1__create_users.sql', sql: 'CREATE TABLE users (id NUMBER);' },
];

describe('MigrationsTab', () => {
  it('renders the migration filename in the input', () => {
    const { getByDisplayValue } = render(
      <MigrationsTab files={mockFiles} onChange={() => {}} />,
    );
    expect(getByDisplayValue('V1__create_users.sql')).toBeDefined();
  });

  it('calls onChange when "Add Migration File" is clicked', () => {
    const handleChange = vi.fn();
    const { getByText } = render(
      <MigrationsTab files={mockFiles} onChange={handleChange} />,
    );
    fireEvent.click(getByText('+ Add Migration File'));
    expect(handleChange).toHaveBeenCalledOnce();
  });
});
