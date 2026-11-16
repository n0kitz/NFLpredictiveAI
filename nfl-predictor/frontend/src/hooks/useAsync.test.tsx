import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useAsync } from './useAsync';

describe('useAsync', () => {
  it('is loading until the request settles, then exposes the data', async () => {
    const { result } = renderHook(() => useAsync(() => Promise.resolve(42), []));
    expect(result.current).toEqual({ data: null, loading: true, error: null });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBe(42);
  });

  it('reports the error message and clears the data', async () => {
    const { result } = renderHook(() => useAsync(() => Promise.reject(new Error('boom')), []));
    await waitFor(() => expect(result.current.error).toBe('boom'));
    expect(result.current).toMatchObject({ data: null, loading: false });
  });

  it('falls back to a default message for non-Error rejections', async () => {
    const { result } = renderHook(() =>
      useAsync(() => Promise.reject('nope'), [], 'Failed to load'));
    await waitFor(() => expect(result.current.error).toBe('Failed to load'));
  });

  it('goes back to loading as soon as a dependency changes', async () => {
    const fetcher = vi.fn((id: number) => Promise.resolve(`item ${id}`));
    const { result, rerender } = renderHook(
      ({ id }) => useAsync(() => fetcher(id), [id]),
      { initialProps: { id: 1 } },
    );
    await waitFor(() => expect(result.current.data).toBe('item 1'));
    rerender({ id: 2 });
    // Same render pass: no stale "loaded" frame for the new id.
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.data).toBe('item 2'));
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('ignores a slow response for dependencies that are no longer current', async () => {
    let resolveFirst: (v: string) => void = () => {};
    const fetcher = vi.fn((id: number) =>
      id === 1 ? new Promise<string>((r) => { resolveFirst = r; }) : Promise.resolve('second'));
    const { result, rerender } = renderHook(
      ({ id }) => useAsync(() => fetcher(id), [id]),
      { initialProps: { id: 1 } },
    );
    rerender({ id: 2 });
    await waitFor(() => expect(result.current.data).toBe('second'));
    resolveFirst('first');
    await Promise.resolve();
    expect(result.current.data).toBe('second');
  });

  it('does nothing while disabled', () => {
    const { result } = renderHook(() => useAsync<number>(null, []));
    expect(result.current).toEqual({ data: null, loading: false, error: null });
  });
});
