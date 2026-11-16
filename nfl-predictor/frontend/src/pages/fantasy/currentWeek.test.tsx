import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { api } from '../../api/client';
import { resetCurrentWeekCache, useFantasyWeek } from './currentWeek';

vi.mock('../../api/client', () => ({
  api: { getCurrentWeek: vi.fn() },
}));

describe('useFantasyWeek', () => {
  beforeEach(() => {
    resetCurrentWeekCache();
    vi.mocked(api.getCurrentWeek).mockReset();
  });

  it('opens on the week the API says is still to be played', async () => {
    vi.mocked(api.getCurrentWeek).mockResolvedValue({ season: 2026, week: 10 });
    const { result } = renderHook(() => useFantasyWeek());
    await waitFor(() => expect(result.current[0]).toBe(10));
  });

  it('stays on week 1 when the lookup fails', async () => {
    vi.mocked(api.getCurrentWeek).mockRejectedValue(new Error('offline'));
    const { result } = renderHook(() => useFantasyWeek());
    await waitFor(() => expect(api.getCurrentWeek).toHaveBeenCalled());
    expect(result.current[0]).toBe(1);
  });

  it('never overrides a week the user picked themselves', async () => {
    let resolve: (v: { season: number; week: number }) => void = () => {};
    vi.mocked(api.getCurrentWeek).mockReturnValue(
      new Promise((r) => { resolve = r; }),
    );
    const { result } = renderHook(() => useFantasyWeek());
    act(() => result.current[1](4));
    await act(async () => { resolve({ season: 2026, week: 10 }); });
    expect(result.current[0]).toBe(4);
  });

  it('asks the API once for all tabs', async () => {
    vi.mocked(api.getCurrentWeek).mockResolvedValue({ season: 2026, week: 10 });
    const a = renderHook(() => useFantasyWeek());
    const b = renderHook(() => useFantasyWeek());
    await waitFor(() => expect(b.result.current[0]).toBe(10));
    expect(a.result.current[0]).toBe(10);
    expect(api.getCurrentWeek).toHaveBeenCalledTimes(1);
  });
});
