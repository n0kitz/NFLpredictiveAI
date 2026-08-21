import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import DraftSimulatorPage from './DraftSimulatorPage';
import { api } from '../api/client';
import type { DraftRanking } from '../api/types';

vi.mock('../api/client', () => ({
  api: { getDraftRankings: vi.fn() },
}));

function ranking(over: Partial<DraftRanking> = {}): DraftRanking {
  return {
    player_id: 1, full_name: 'Test Back', position: 'RB', team_abbr: 'KC',
    headshot_url: null, overall_rank: 1, position_rank: 1, tier: 1, adp: 1,
    projected_season_points: 280, season: 2026, scoring_format: 'standard',
    vbd: 150, boom_pct: null, bust_pct: null, ...over,
  };
}

/** Enough players that a 10-team, 15-round draft doesn't run dry. */
function board(): DraftRanking[] {
  const spec: Array<[string, number]> = [
    ['RB', 60], ['WR', 70], ['QB', 30], ['TE', 40], ['K', 20], ['DST', 20],
  ];
  const out: DraftRanking[] = [];
  let id = 1;
  for (const [position, count] of spec) {
    for (let i = 0; i < count; i++) {
      out.push(ranking({
        player_id: id, full_name: `${position}${i + 1}`, position,
        overall_rank: id, position_rank: i + 1, tier: Math.floor(i / 4) + 1,
        adp: id, projected_season_points: 300 - i * 5, vbd: 200 - i * 6,
      }));
      id++;
    }
  }
  return out;
}

function renderPage() {
  return render(
    <MemoryRouter>
      <DraftSimulatorPage />
    </MemoryRouter>,
  );
}

describe('DraftSimulatorPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    vi.mocked(api.getDraftRankings).mockResolvedValue(board());
  });

  it('renders both modes', async () => {
    renderPage();
    expect(await screen.findByText('Compare strategies')).toBeTruthy();
    expect(screen.getByText('Mock draft')).toBeTruthy();
  });

  it('lists every strategy as a checkbox', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Zero-RB')).toBeTruthy());
    expect(screen.getAllByRole('checkbox')).toHaveLength(8);
  });

  it('shows an empty state when no rankings come back', async () => {
    vi.mocked(api.getDraftRankings).mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText(/No draft rankings available/)).toBeTruthy();
  });

  it('warns that synthetic ADP makes the value strategy meaningless', async () => {
    renderPage();
    // The fixture's adp equals overall_rank, which is exactly the synthetic case.
    expect(await screen.findByText(/no real market data is loaded/)).toBeTruthy();
  });

  it('produces a results table after running a simulation', async () => {
    const user = userEvent.setup();
    renderPage();
    const run = await screen.findByRole('button', { name: /Run simulation/ });

    await user.click(run);

    await waitFor(
      () => expect(screen.getByText(/Results —/)).toBeTruthy(),
      { timeout: 20000 },
    );
    expect(screen.getAllByText('Win %').length).toBeGreaterThan(0);
  }, 30000);

  it('switches to the mock draft and shows my roster', async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByText('Mock draft'));

    await waitFor(() => expect(screen.getByText(/My roster/)).toBeTruthy());
    expect(screen.getByRole('button', { name: 'Auto-pick' })).toBeTruthy();
  });
});
