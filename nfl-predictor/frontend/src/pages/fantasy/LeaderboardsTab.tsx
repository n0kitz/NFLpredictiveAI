import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import type { FantasyLeaderboard, FantasyPlayerEntry } from '../../api/types';
import Spinner from '../../components/Spinner';
import { LAST_COMPLETED_SEASON } from '../../config';
import { type PositionFilter } from './helpers';
import {
  PositionFilterBar, ScoringToggle, PosBadge, Headshot,
} from './shared';

export default function LeaderboardsTab() {
  const [position, setPosition] = useState<PositionFilter>('QB');
  const [scoring, setScoring] = useState('ppr');
  const [season] = useState(LAST_COMPLETED_SEASON);
  const [data, setData] = useState<FantasyLeaderboard | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    api.getFantasyTop(position === 'ALL' ? undefined : position, season, scoring, 50)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [position, scoring, season]);

  const players: FantasyPlayerEntry[] = data?.players ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 flex-wrap">
        <PositionFilterBar value={position} onChange={setPosition} />
        <ScoringToggle value={scoring} onChange={setScoring} />
      </div>

      {loading ? <Spinner text="Loading leaderboard…" /> : (
        <div className="rounded-xl border border-border bg-surface-850 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                {['#', 'Player', 'Team', 'Pos', 'Season Pts', 'Avg/Gm'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-[10px] font-display uppercase tracking-widest text-text-muted">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {players.map((p, i) => (
                <tr
                  key={p.player_id}
                  onClick={() => navigate(`/players/${p.player_id}`)}
                  className="border-b border-border/50 hover:bg-surface-800 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-2.5 text-text-muted text-[11px]">{i + 1}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <Headshot url={p.headshot_url} name={p.full_name} />
                      <span className="text-text-primary font-medium text-xs">{p.full_name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-text-muted text-xs">{p.team_abbr ?? '—'}</td>
                  <td className="px-4 py-2.5"><PosBadge pos={p.position} /></td>
                  <td className="px-4 py-2.5 font-bold tabular-nums text-text-primary text-sm">
                    {scoring === 'ppr'
                      ? p.fantasy_points_ppr.toFixed(1)
                      : p.fantasy_points_standard.toFixed(1)}
                  </td>
                  <td className="px-4 py-2.5 text-text-secondary tabular-nums text-xs">
                    {p.points_per_game_ppr.toFixed(1)}
                  </td>
                </tr>
              ))}
              {!loading && players.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-text-muted text-xs">
                    No data — run scripts/import_rosters.py to populate player stats.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
