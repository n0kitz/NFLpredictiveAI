import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import StreamingPanel from './StreamingPanel';
import { api } from '../../api/client';
import type { StreamingResult } from '../../api/types';

vi.mock('../../api/client', () => ({
  api: { getStreamingCandidates: vi.fn() },
}));

const result = (over: Partial<StreamingResult> = {}): StreamingResult => ({
  position: 'DST',
  week: 1,
  season: 2026,
  candidates: [
    {
      player_id: 2272,
      full_name: 'Miami Dolphins DST',
      team_abbr: 'MIA',
      opponent_team_abbr: 'LV',
      grade: 'D',
      score: 47.9,
      explanation: 'Grade D: opponent is near league avg for DST PPR allowed.',
    },
  ],
  ...over,
});

beforeEach(() => vi.clearAllMocks());

describe('StreamingPanel', () => {
  it('does not fetch until a position is picked', () => {
    render(<StreamingPanel week={1} excludeIds={[]} />);
    expect(api.getStreamingCandidates).not.toHaveBeenCalled();
  });

  it('fetches candidates for the clicked position, excluding the roster', async () => {
    vi.mocked(api.getStreamingCandidates).mockResolvedValue(result());
    render(<StreamingPanel week={1} excludeIds={[10, 11]} />);

    await userEvent.click(screen.getByRole('button', { name: 'DST' }));

    await waitFor(() => expect(api.getStreamingCandidates).toHaveBeenCalled());
    const call = vi.mocked(api.getStreamingCandidates).mock.calls[0];
    expect(call[0]).toBe('DST');
    expect(call[1]).toBe(1); // week
    expect(call[3]).toEqual([10, 11]); // excludeIds
  });

  it('renders candidates with grade, name and opponent', async () => {
    vi.mocked(api.getStreamingCandidates).mockResolvedValue(result());
    render(<StreamingPanel week={1} excludeIds={[]} />);
    await userEvent.click(screen.getByRole('button', { name: 'DST' }));

    await waitFor(() => {
      expect(screen.getByText('Miami Dolphins DST')).toBeInTheDocument();
      expect(screen.getByText(/MIA vs LV/)).toBeInTheDocument();
      expect(screen.getByText('47.9')).toBeInTheDocument();
    });
  });

  it('shows a message when no candidates are available', async () => {
    vi.mocked(api.getStreamingCandidates).mockResolvedValue(result({ candidates: [] }));
    render(<StreamingPanel week={1} excludeIds={[]} />);
    await userEvent.click(screen.getByRole('button', { name: 'DST' }));

    await waitFor(() =>
      expect(screen.getByText(/no available dst/i)).toBeInTheDocument(),
    );
  });

  it('switching position re-fetches with the new position', async () => {
    vi.mocked(api.getStreamingCandidates).mockResolvedValue(result());
    render(<StreamingPanel week={1} excludeIds={[]} />);
    await userEvent.click(screen.getByRole('button', { name: 'DST' }));
    await waitFor(() => expect(api.getStreamingCandidates).toHaveBeenCalledTimes(1));

    await userEvent.click(screen.getByRole('button', { name: 'QB' }));
    await waitFor(() => expect(api.getStreamingCandidates).toHaveBeenCalledTimes(2));
    expect(vi.mocked(api.getStreamingCandidates).mock.calls[1][0]).toBe('QB');
  });

  it('renders an error without crashing', async () => {
    vi.mocked(api.getStreamingCandidates).mockRejectedValue(new Error('boom'));
    render(<StreamingPanel week={1} excludeIds={[]} />);
    await userEvent.click(screen.getByRole('button', { name: 'DST' }));

    await waitFor(() => expect(screen.getByText('boom')).toBeInTheDocument());
  });
});
