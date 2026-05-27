import { describe, it, expect, vi, beforeEach } from 'vitest';

import { downloadBlob, copyToClipboard } from './io';

describe('downloadBlob', () => {
  it('creates and clicks an anchor element', () => {
    const createObjectURL = vi.fn(() => 'blob:fake');
    const revokeObjectURL = vi.fn();
    // Stub global URL
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL } as unknown as typeof URL);

    const appendSpy = vi.spyOn(document.body, 'appendChild');
    const removeSpy = vi.spyOn(document.body, 'removeChild');

    downloadBlob('hello', 'test.txt');

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(appendSpy).toHaveBeenCalledTimes(1);
    expect(removeSpy).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:fake');
  });
});

describe('copyToClipboard', () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it('returns true on success', async () => {
    expect(await copyToClipboard('hello')).toBe(true);
  });

  it('returns false when clipboard API throws', async () => {
    (navigator.clipboard.writeText as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('denied'),
    );
    expect(await copyToClipboard('hello')).toBe(false);
  });
});
