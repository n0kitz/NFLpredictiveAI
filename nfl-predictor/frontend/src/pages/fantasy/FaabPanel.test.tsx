import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FaabPanel from './FaabPanel';
import { api } from '../../api/client';
import type { FaabResult } from '../../api/types';

vi.mock('../../api/client', () => ({
  api: { getFaabRecommendations: vi.fn() },
}));

const result = (over: Partial<FaabResult> = {}): FaabResult => ({
  week: 1,
  season: 2026,
  budget_remaining: 100,
  candidates: [
    {
      player_id: 96,
      full_name: 'Bijan Robinson',
      position: 'RB',
      team_abbr: 'ATL',
      projected_points: 17.16,
      replacement_points: 3.92,
      delta: 13.24,
      tier: 'must-add',
      suggested_bid_pct: 30,
      suggested_bid_amount: 30,
    },
  ],
  ...over,
});

beforeEach(() => vi.clearAllMocks());

describe('FaabPanel', () => {
  it('does not fetch until the button is clicked', () => {
    render(<FaabPanel week={1} rosterIds={[1, 2]} />);
    expect(api.getFaabRecommendations).not.toHaveBeenCalled();
  });

  it('requests recommendations with the roster ids, week and budget', async () => {
    vi.mocked(api.getFaabRecommendations).mockResolvedValue(result());
    render(<FaabPanel week={1} rosterIds={[1, 2, 3]} />);

    await userEvent.click(screen.getByRole('button', { name: /find faab targets/i }));

    await waitFor(() => expect(api.getFaabRecommendations).toHaveBeenCalled());
    const call = vi.mocked(api.getFaabRecommendations).mock.calls[0];
    expect(call[0]).toEqual([1, 2, 3]);
    expect(call[1]).toBe(1); // week
  });

  it('renders candidates with tier, delta and suggested bid', async () => {
    vi.mocked(api.getFaabRecommendations).mockResolvedValue(result());
    render(<FaabPanel week={1} rosterIds={[1, 2]} />);
    await userEvent.click(screen.getByRole('button', { name: /find faab targets/i }));

    await waitFor(() => {
      expect(screen.getByText('Bijan Robinson')).toBeInTheDocument();
      expect(screen.getByText(/must-add/i)).toBeInTheDocument();
      expect(screen.getByText(/\+13\.2/)).toBeInTheDocument();
      expect(screen.getByText(/30%/)).toBeInTheDocument();
    });
  });

  it('shows a message when no candidates clear replacement level', async () => {
    vi.mocked(api.getFaabRecommendations).mockResolvedValue(result({ candidates: [] }));
    render(<FaabPanel week={1} rosterIds={[1, 2]} />);
    await userEvent.click(screen.getByRole('button', { name: /find faab targets/i }));

    await waitFor(() =>
      expect(screen.getByText(/no waiver target beats your roster/i)).toBeInTheDocument(),
    );
  });

  it('passes a custom budget through to the request', async () => {
    vi.mocked(api.getFaabRecommendations).mockResolvedValue(result());
    render(<FaabPanel week={1} rosterIds={[1, 2]} />);

    await userEvent.clear(screen.getByLabelText(/budget/i));
    await userEvent.type(screen.getByLabelText(/budget/i), '55');
    await userEvent.click(screen.getByRole('button', { name: /find faab targets/i }));

    await waitFor(() => expect(api.getFaabRecommendations).toHaveBeenCalled());
    const call = vi.mocked(api.getFaabRecommendations).mock.calls[0];
    expect(call[6]).toBe(55); // budgetRemaining
  });

  it('renders an error without crashing', async () => {
    vi.mocked(api.getFaabRecommendations).mockRejectedValue(new Error('boom'));
    render(<FaabPanel week={1} rosterIds={[1, 2]} />);
    await userEvent.click(screen.getByRole('button', { name: /find faab targets/i }));

    await waitFor(() => expect(screen.getByText('boom')).toBeInTheDocument());
  });
});
