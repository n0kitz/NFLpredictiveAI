import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import Season from './Season';
import { api } from '../api/client';
import type { PlayoffOdds } from '../api/types';

vi.mock('../api/client', () => ({
  api: {
    getGames: vi.fn(),
    getTeams: vi.fn(),
    getPlayoffPicture: vi.fn(),
    getPlayoffOdds: vi.fn(),
  },
}));

const odds: PlayoffOdds = {
  season: 2024,
  as_of_week: 10,
  weeks_completed: 10,
  games_simulated: 120,
  n_sims: 1000,
  generated_at: '2026-07-02 08:00:00',
  teams: [
    {
      team_id: 1, team_abbr: 'KC', team_name: 'Kansas City Chiefs',
      conference: 'AFC', division: 'AFC West', wins: 9, losses: 0, ties: 0,
      mean_wins: 13.9, playoff_pct: 100.0, division_pct: 92.8, top_seed_pct: 55.8,
      seed_distribution: { '1': 55.8, '2': 20, '3': 10, '4': 7, '5': 4, '6': 2, '7': 1.2 },
    },
    {
      team_id: 2, team_abbr: 'DET', team_name: 'Detroit Lions',
      conference: 'NFC', division: 'NFC North', wins: 8, losses: 1, ties: 0,
      mean_wins: 13.1, playoff_pct: 99.8, division_pct: 70.2, top_seed_pct: 57.4,
      seed_distribution: { '1': 57.4, '2': 20, '3': 10, '4': 7, '5': 4, '6': 1, '7': 0.4 },
    },
  ],
};

function renderSeason() {
  return render(
    <MemoryRouter initialEntries={['/seasons/2024']}>
      <Routes>
        <Route path="/seasons/:year?" element={<Season />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Season — Playoff Odds tab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getGames).mockResolvedValue({ games: [], count: 0 });
    vi.mocked(api.getTeams).mockResolvedValue({ teams: [], count: 0 });
    vi.mocked(api.getPlayoffOdds).mockResolvedValue(odds);
  });

  it('loads odds when the tab is opened and renders per-conference tables', async () => {
    renderSeason();
    await waitFor(() => expect(screen.getByText('Playoff Odds')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Playoff Odds'));

    await waitFor(() => expect(api.getPlayoffOdds).toHaveBeenCalledWith(2024, undefined));
    await waitFor(() => expect(screen.getAllByText('KC').length).toBeGreaterThan(0));
    expect(screen.getAllByText('DET').length).toBeGreaterThan(0);
    expect(screen.getByText('100%')).toBeInTheDocument();          // KC playoff pct
    expect(screen.getByText(/120 games simulated/)).toBeInTheDocument();
  });

  it('re-simulates when a retro week is selected', async () => {
    renderSeason();
    await waitFor(() => expect(screen.getByText('Playoff Odds')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Playoff Odds'));
    await waitFor(() => expect(screen.getAllByText('KC').length).toBeGreaterThan(0));

    fireEvent.change(screen.getByDisplayValue('Current standings'), { target: { value: '10' } });
    await waitFor(() => expect(api.getPlayoffOdds).toHaveBeenCalledWith(2024, 10));
  });
});
