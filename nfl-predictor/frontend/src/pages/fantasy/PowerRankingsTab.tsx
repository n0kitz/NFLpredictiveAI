import { useState, useEffect } from 'react';
import { api } from '../../api/client';
import type { PowerRanking } from '../../api/types';
import Spinner from '../../components/Spinner';
import { LAST_COMPLETED_SEASON } from '../../config';

export default function PowerRankingsTab() {
  const [week, setWeek] = useState(1);
  const [season] = useState(LAST_COMPLETED_SEASON);
  const [rankings, setRankings] = useState<PowerRanking[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.getFantasyPowerRankings(week, season)
      .then((r) => setRankings(r.rankings))
      .catch(() => setRankings([]))
      .finally(() => setLoading(false));
  }, [week, season]);

  function trendIcon(t: PowerRanking['trend'], change: number) {
    if (t === 'rising')  return <span className="text-win text-xs">▲{Math.abs(change)}</span>;
    if (t === 'falling') return <span className="text-loss text-xs">▼{Math.abs(change)}</span>;
    return <span className="text-text-muted text-xs">–</span>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <label className="text-xs text-text-muted font-display uppercase tracking-widest">Week</label>
        <select value={week} onChange={(e) => setWeek(Number(e.target.value))}
          className="bg-surface-800 border border-border rounded px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent">
          {Array.from({ length: 18 }, (_, i) => i + 1).map((w) => <option key={w} value={w}>Week {w}</option>)}
        </select>
        <span className="text-xs text-text-muted ml-2">Composite: recent form, pt diff, adv stats, next opp strength</span>
      </div>

      {loading ? <Spinner text="Computing power rankings…" /> : (
        <div className="rounded-xl border border-border bg-surface-850 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                {['Rank', 'Trend', 'Team', 'Conf', 'Score', 'Recent', 'Pt Diff', 'Fantasy Implication'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-[10px] font-display uppercase tracking-widest text-text-muted">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rankings.map((r) => (
                <tr key={r.team_abbr} className={`border-b border-border/50 hover:bg-surface-800 transition-colors ${r.rank <= 5 ? 'bg-win/3' : r.rank >= 28 ? 'bg-loss/3' : ''}`}>
                  <td className="px-4 py-2.5 font-bold text-text-primary tabular-nums">{r.rank}</td>
                  <td className="px-4 py-2.5">{trendIcon(r.trend, r.rank_change)}</td>
                  <td className="px-4 py-2.5 font-semibold text-text-primary text-xs">{r.team_abbr}</td>
                  <td className="px-4 py-2.5 text-text-muted text-xs">{r.conference}</td>
                  <td className="px-4 py-2.5 tabular-nums text-text-secondary">{(r.composite_score * 100).toFixed(0)}</td>
                  <td className="px-4 py-2.5 tabular-nums text-text-muted text-xs">{r.recent_wins}-{r.recent_games - r.recent_wins}</td>
                  <td className={`px-4 py-2.5 tabular-nums text-xs font-medium ${r.pt_diff_4g > 0 ? 'text-win' : r.pt_diff_4g < 0 ? 'text-loss' : 'text-text-muted'}`}>
                    {r.pt_diff_4g > 0 ? '+' : ''}{r.pt_diff_4g}
                  </td>
                  <td className="px-4 py-2.5 text-[10px] text-text-muted max-w-[200px]">{r.implication}</td>
                </tr>
              ))}
              {!loading && rankings.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-text-muted text-xs">No data — ensure player_season_stats is populated.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
