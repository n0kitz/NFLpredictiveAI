import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import QBHistoryCard from './QBHistoryCard';
import TeamAdvancedStatsCard from './TeamAdvancedStatsCard';
import { api } from '../api/client';
import type { TeamQBHistory, TeamAdvancedStats } from '../api/types';

vi.mock('../api/client', () => ({
  api: {
    getTeamQBHistory: vi.fn(),
    getTeamAdvancedStats: vi.fn(),
  },
}));

const qbHistory: TeamQBHistory = {
  team_id: 14,
  team_abbr: 'KC',
  detail_season: 2024,
  seasons: [
    {
      season: 2024,
      starters: [
        { qb_name: 'P.Mahomes', starts: 16, avg_epa: 0.102, player_id: 1067 },
        { qb_name: 'C.Wentz', starts: 1, avg_epa: -0.418, player_id: null },
      ],
    },
  ],
  weeks: [
    { week: 1, qb_name: 'P.Mahomes', epa_per_play: 0.37, snap_count: 30 },
    { week: 2, qb_name: 'P.Mahomes', epa_per_play: -0.35, snap_count: 28 },
  ],
};

const advanced: TeamAdvancedStats = {
  team_id: 14, team_abbr: 'KC', season: 2025,
  turnover_margin: -1, third_down_pct: 0.3744, redzone_efficiency: 0.1852,
  yards_per_play: 5.2176, sack_rate_allowed: 0.069, qb_epa_per_play: 0.0,
  ranks: { turnover_margin: 18, third_down_pct: 22, redzone_efficiency: 21, yards_per_play: 22, sack_rate_allowed: 21, qb_epa_per_play: 16 },
};

describe('QBHistoryCard', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders starters with EPA and links matched players', async () => {
    vi.mocked(api.getTeamQBHistory).mockResolvedValue(qbHistory);
    render(<MemoryRouter><QBHistoryCard teamAbbr="KC" /></MemoryRouter>);
    await waitFor(() => expect(screen.getAllByText('P.Mahomes').length).toBeGreaterThan(0));
    expect(screen.getByText('16 starts')).toBeInTheDocument();
    const link = screen.getAllByRole('link').find((a) => a.getAttribute('href') === '/players/1067');
    expect(link).toBeTruthy();
    // unmatched name renders as plain text, not a link
    expect(screen.getAllByRole('link').some((a) => a.textContent === 'C.Wentz')).toBe(false);
  });

  it('renders nothing when the endpoint 404s', async () => {
    vi.mocked(api.getTeamQBHistory).mockRejectedValue(new Error('not found'));
    const { container } = render(<MemoryRouter><QBHistoryCard teamAbbr="ZZ" /></MemoryRouter>);
    await waitFor(() => expect(api.getTeamQBHistory).toHaveBeenCalled());
    expect(container.textContent).toBe('');
  });
});

describe('TeamAdvancedStatsCard', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders metrics with league ranks', async () => {
    vi.mocked(api.getTeamAdvancedStats).mockResolvedValue(advanced);
    render(<MemoryRouter><TeamAdvancedStatsCard teamAbbr="KC" /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/Advanced Stats — 2025/)).toBeInTheDocument());
    expect(screen.getByText('Turnover Margin')).toBeInTheDocument();
    expect(screen.getByText('-1')).toBeInTheDocument();
    expect(screen.getByText('18th')).toBeInTheDocument();
    expect(screen.getByText('37.4%')).toBeInTheDocument();
  });
});
