import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import Season from './Season';
import { api } from '../api/client';
import type { Game, Team } from '../api/types';

vi.mock('../api/client', () => ({
  api: { getGames: vi.fn(), getTeams: vi.fn(), getPlayoffPicture: vi.fn() },
}));

const team = (id: number, abbr: string): Team => ({
  team_id: id, name: abbr, city: 'City', conference: 'NFC', division: 'North',
  abbreviation: abbr, franchise_id: null, active_from: null, active_until: null,
});

const game = (id: number, home: number, away: number, hs: number | null, as: number | null): Game => ({
  game_id: id, date: '2025-09-07', season: 2025, week: '1', game_type: 'regular',
  home_team_id: home, away_team_id: away, home_team: null, home_abbr: null,
  away_team: null, away_abbr: null, home_score: hs, away_score: as,
  winner: null, winner_abbr: null,
  winner_id: hs === null || as === null ? null : hs > as ? home : away,
  overtime: false,
});

/** Team abbreviations repeat across the page; this is the standings row. */
async function standingsRow(abbr: string): Promise<HTMLElement> {
  const hits = await screen.findAllByText(abbr);
  const row = hits.map((el) => el.closest('tr')).find(Boolean);
  if (!row) throw new Error(`no standings row for ${abbr}`);
  return row as HTMLElement;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/seasons/:year?" element={<Season />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Season', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getTeams).mockResolvedValue({ teams: [team(1, 'DET'), team(2, 'GB'), team(3, 'CHI')], count: 3 });
    vi.mocked(api.getGames).mockResolvedValue({
      games: [game(1, 1, 2, 27, 20), game(2, 1, 3, 31, 10), game(3, 2, 3, null, null)],
      count: 3,
    } as Awaited<ReturnType<typeof api.getGames>>);
  });

  it('loads the season named in the URL', async () => {
    renderAt('/seasons/2025');
    await waitFor(() => expect(api.getGames).toHaveBeenCalledWith(2025));
    expect(await screen.findByText('2025 Season')).toBeInTheDocument();
  });

  it('builds standings from played regular-season games only', async () => {
    renderAt('/seasons/2025');
    const det = await standingsRow('DET');
    // 2-0, 58 points for, 30 against
    expect(det.textContent).toContain('58');
    expect(det.textContent).toContain('30');
    expect(det.textContent).toContain('+28');
    // GB: lost once, its unplayed game does not count.
    const gb = await standingsRow('GB');
    expect(gb.textContent).toContain('.000');
  });

  it('switching the year refetches via the URL', async () => {
    renderAt('/seasons/2025');
    await standingsRow('DET');
    await userEvent.selectOptions(screen.getByRole('combobox'), '2024');
    await waitFor(() => expect(api.getGames).toHaveBeenCalledWith(2024));
    expect(await screen.findByText('2024 Season')).toBeInTheDocument();
  });

  it('shows the error instead of stale standings when loading fails', async () => {
    vi.mocked(api.getGames).mockRejectedValue(new Error('backend down'));
    renderAt('/seasons/2025');
    expect(await screen.findByText('backend down')).toBeInTheDocument();
    expect(screen.queryAllByText('DET')).toHaveLength(0);
  });
});
