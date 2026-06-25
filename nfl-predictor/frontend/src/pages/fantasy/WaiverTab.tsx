import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import type { FantasyProjection } from '../../api/types';
import Spinner from '../../components/Spinner';
import BoomBustBadge from '../../components/BoomBustBadge';
import { LAST_COMPLETED_SEASON } from '../../config';
import { matchupColor, type PositionFilter } from './helpers';
import {
  PositionFilterBar, PosBadge, Headshot, MTooltip,
} from './shared';

export default function WaiverTab() {
  const [week, setWeek] = useState(1);
  const [season] = useState(LAST_COMPLETED_SEASON);
  const [position, setPosition] = useState<PositionFilter>('ALL');
  const [hideBye, setHideBye] = useState(true);
  const [players, setPlayers] = useState<FantasyProjection[]>([]);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    api.getWaiverWire(week, season, 'ppr', position === 'ALL' ? 'all' : position, 30)
      .then(setPlayers)
      .catch(() => setPlayers([]))
      .finally(() => setLoading(false));
  }, [week, season, position]);

  const visible = hideBye
    ? players.filter((p) => p.bye_week !== week)
    : players;

  function oppBar(score: number) {
    const pct = Math.round(score * 10);
    const color = score > 7 ? 'var(--color-win)' : score > 4 ? '#f39c12' : 'var(--color-loss)';
    return (
      <div className="flex items-center gap-1.5">
        <div className="w-16 h-1.5 rounded-full bg-surface-700 overflow-hidden">
          <div className="h-full rounded-full transition-all" style={{ width: `${pct}0%`, backgroundColor: color }} />
        </div>
        <span className="text-[10px] tabular-nums" style={{ color }}>{score.toFixed(1)}</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-xs text-text-muted font-display uppercase tracking-widest">Week</label>
          <select
            value={week}
            onChange={(e) => setWeek(Number(e.target.value))}
            className="bg-surface-800 border border-border rounded px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent"
          >
            {Array.from({ length: 18 }, (_, i) => i + 1).map((w) => (
              <option key={w} value={w}>Week {w}</option>
            ))}
          </select>
        </div>
        <PositionFilterBar value={position} onChange={setPosition} />
        <label className="flex items-center gap-1.5 text-xs text-text-muted font-display uppercase tracking-widest cursor-pointer select-none">
          <input
            type="checkbox"
            checked={hideBye}
            onChange={(e) => setHideBye(e.target.checked)}
            className="accent-accent"
          />
          Hide bye week
        </label>
      </div>

      {loading ? <Spinner text="Loading waiver wire…" /> : (
        <div className="rounded-xl border border-border bg-surface-850 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                {['#', 'Player', 'Pos', 'Team', 'Proj Pts', 'Opportunity', 'Matchup', 'Status'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-[10px] font-display uppercase tracking-widest text-text-muted">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((p, i) => (
                <tr
                  key={p.player_id}
                  onClick={() => navigate(`/players/${p.player_id}`)}
                  className="border-b border-border/50 hover:bg-surface-800 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-2.5 text-text-muted text-[11px]">{i + 1}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <Headshot url={p.headshot_url} name={p.full_name} />
                      <div className="flex flex-col min-w-0">
                        <span className="text-text-primary font-medium text-xs truncate max-w-[140px]">{p.full_name}</span>
                        <BoomBustBadge boomPct={p.boom_pct} bustPct={p.bust_pct} />
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-2.5"><PosBadge pos={p.position} /></td>
                  <td className="px-4 py-2.5 text-text-muted text-xs">{p.team_abbr ?? '—'}</td>
                  <td className="px-4 py-2.5 font-bold tabular-nums text-text-primary">
                    {p.projected_points_ppr.toFixed(1)}
                  </td>
                  <td className="px-4 py-2.5">{oppBar(p.opportunity_score)}</td>
                  <td className="px-4 py-2.5">
                    <MTooltip text={`Matchup Score: ${p.matchup_score.toFixed(2)}× — Week ${week} opponent defensive stats. >1.1 = favorable, <0.9 = unfavorable, 1.0 = neutral`}>
                      <span className="text-xs tabular-nums font-medium cursor-help" style={{ color: matchupColor(p.matchup_score) }}>
                        {p.matchup_score.toFixed(2)}×
                      </span>
                    </MTooltip>
                  </td>
                  <td className="px-4 py-2.5">
                    {p.bye_week === week ? (
                      <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-surface-700 text-text-muted">
                        BYE
                      </span>
                    ) : p.injury_status ? (
                      <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${
                        ['Out', 'IR', 'PUP'].includes(p.injury_status)
                          ? 'bg-loss/15 text-loss'
                          : 'bg-yellow-500/15 text-yellow-400'
                      }`}>
                        {p.injury_status}
                      </span>
                    ) : (
                      <span className="text-[10px] text-text-muted">Active</span>
                    )}
                  </td>
                </tr>
              ))}
              {!loading && visible.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-text-muted text-xs">
                    No waiver data — run scripts/import_rosters.py first.
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
