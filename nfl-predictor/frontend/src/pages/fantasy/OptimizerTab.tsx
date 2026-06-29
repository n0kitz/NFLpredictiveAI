import { useState } from 'react';
import { api } from '../../api/client';
import type {
  OptimizeResponse, LineupResult, OptimizerPlayerInput,
} from '../../api/types';
import DataBadge from '../../components/DataBadge';
import { CURRENT_SEASON } from '../../config';
import { posColor } from './helpers';
import { PosBadge, Headshot } from './shared';

const SEASON_LONG_SLOTS: Record<string, number> = { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, K: 1 };

export default function OptimizerTab() {
  const [week, setWeek]           = useState(1);
  const [season]                  = useState(CURRENT_SEASON);
  const [mode, setMode]           = useState<'season' | 'dk' | 'fd'>('season');
  const [salaryCap, setSalaryCap] = useState<number | null>(null);
  const [nLineups, setNLineups]   = useState(5);
  const [correlations, setCorr]   = useState(true);
  const [loading, setLoading]     = useState(false);
  const [result, setResult]       = useState<OptimizeResponse | null>(null);
  const [error, setError]         = useState<string | null>(null);
  const [viewIdx, setViewIdx]     = useState(0);

  // Build player pool from cached projections, then optimise.
  async function run() {
    setLoading(true);
    setError(null);
    try {
      const allPos = ['QB', 'RB', 'WR', 'TE', 'K'];
      const pools = await Promise.all(
        allPos.map((pos) => api.getFantasyProjections(week, season, pos, 'ppr'))
      );
      const players: OptimizerPlayerInput[] = pools.flat().map((p) => ({
        player_id: p.player_id,
        full_name: p.full_name,
        position: p.position ?? '',
        team_id: 0,
        team_abbr: p.team_abbr ?? '',
        projected_points: p.projected_points_ppr,
        salary: 0,
        is_locked: false,
        is_excluded: false,
        headshot_url: p.headshot_url ?? null,
        // projection response doesn't expose opponent; optimizer treats null as "unknown"
        opponent_team_id: null,
      }));

      let res: OptimizeResponse;
      if (mode === 'season') {
        res = await api.optimizeLineup({
          players,
          slots: SEASON_LONG_SLOTS,
          flex_positions: ['RB', 'WR', 'TE'],
          salary_cap: salaryCap,
          n_lineups: nLineups,
          correlations,
        });
      } else {
        res = await api.optimizeDFS({
          players,
          site: mode,
          n_lineups: nLineups,
          correlations,
        });
      }
      setResult(res);
      setViewIdx(0);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Optimizer failed');
    } finally {
      setLoading(false);
    }
  }

  const lineup: LineupResult | null = result ? result.lineups[viewIdx] ?? null : null;

  return (
    <div className="space-y-6">
      {/* Config panel */}
      <div className="rounded-xl border border-border bg-surface-850 p-5 space-y-4">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-display uppercase tracking-widest text-text-muted">Optimizer Config</span>
          <DataBadge source="calculated" />
        </div>
        <div className="flex flex-wrap gap-4 items-end">
          {/* Week */}
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-text-muted uppercase">Week</label>
            <select value={week} onChange={(e) => setWeek(Number(e.target.value))}
              className="bg-surface-800 border border-border rounded px-2 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent">
              {Array.from({ length: 18 }, (_, i) => i + 1).map((w) => (
                <option key={w} value={w}>Week {w}</option>
              ))}
            </select>
          </div>
          {/* Mode */}
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-text-muted uppercase">Format</label>
            <div className="flex gap-1">
              {(['season', 'dk', 'fd'] as const).map((m) => (
                <button key={m} onClick={() => setMode(m)}
                  className={`px-3 py-1.5 rounded text-[11px] font-display font-semibold uppercase tracking-wide transition-colors ${mode === m ? 'bg-accent text-surface-900' : 'bg-surface-800 text-text-muted border border-border hover:text-text-secondary'}`}>
                  {m === 'season' ? 'Season-Long' : m.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          {/* Salary cap (season-long only) */}
          {mode === 'season' && (
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-text-muted uppercase">Salary Cap</label>
              <input type="number" placeholder="None"
                value={salaryCap ?? ''}
                onChange={(e) => setSalaryCap(e.target.value ? Number(e.target.value) : null)}
                className="bg-surface-800 border border-border rounded px-2 py-1.5 text-sm text-text-secondary w-28 focus:outline-none focus:border-accent" />
            </div>
          )}
          {/* # lineups */}
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-text-muted uppercase">Lineups</label>
            <select value={nLineups} onChange={(e) => setNLineups(Number(e.target.value))}
              className="bg-surface-800 border border-border rounded px-2 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent">
              {[1, 3, 5, 10, 20].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          {/* Correlations toggle */}
          <label className="flex items-center gap-2 cursor-pointer select-none mt-4">
            <input type="checkbox" checked={correlations} onChange={(e) => setCorr(e.target.checked)}
              className="accent-accent w-4 h-4" />
            <span className="text-xs text-text-muted">QB Stack / Bring-Back</span>
          </label>
          {/* Run button */}
          <button onClick={run} disabled={loading}
            className="ml-auto px-5 py-2 rounded-lg bg-accent text-surface-900 text-sm font-display font-bold uppercase tracking-wide hover:opacity-90 disabled:opacity-40 transition-opacity">
            {loading ? 'Optimizing…' : 'Optimize'}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-loss/40 bg-loss/10 px-4 py-3 text-sm text-loss">{error}</div>
      )}

      {result && !loading && (
        <div className="space-y-4">
          {/* Lineup selector */}
          <div className="flex items-center gap-2 flex-wrap">
            {result.lineups.map((lu, i) => (
              <button key={i} onClick={() => setViewIdx(i)}
                className={`px-3 py-1 rounded text-[11px] font-display font-semibold transition-colors ${i === viewIdx ? 'bg-accent text-surface-900' : 'bg-surface-800 border border-border text-text-muted hover:text-text-secondary'}`}>
                #{lu.rank} · {lu.projected_points.toFixed(1)}pts
              </button>
            ))}
          </div>

          {lineup && (
            <div className="rounded-xl border border-border bg-surface-850 overflow-hidden">
              <div className="px-5 py-3 border-b border-border flex items-center gap-4">
                <span className="text-sm font-display font-bold text-text-primary">
                  Lineup #{lineup.rank}
                </span>
                <span className="text-sm text-accent font-bold tabular-nums">
                  {lineup.projected_points.toFixed(1)} pts
                </span>
                {lineup.total_salary > 0 && (
                  <span className="text-xs text-text-muted">
                    Salary: ${lineup.total_salary.toLocaleString()}
                  </span>
                )}
                {lineup.correlation_bonus > 0 && (
                  <span className="text-[10px] text-win bg-win/10 px-2 py-0.5 rounded">
                    +{lineup.correlation_bonus.toFixed(1)} stack bonus
                  </span>
                )}
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-[10px] text-text-muted uppercase">
                    <th className="px-4 py-2 text-left">Slot</th>
                    <th className="px-4 py-2 text-left">Player</th>
                    <th className="px-4 py-2 text-left">Pos</th>
                    <th className="px-4 py-2 text-left">Team</th>
                    <th className="px-4 py-2 text-right">Proj</th>
                    {lineup.total_salary > 0 && <th className="px-4 py-2 text-right">Salary</th>}
                  </tr>
                </thead>
                <tbody>
                  {lineup.players.map((p, i) => (
                    <tr key={i} className="border-b border-border/50 hover:bg-surface-800 transition-colors">
                      <td className="px-4 py-2.5 text-[10px] font-display font-bold text-text-muted uppercase">{p.slot}</td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          <Headshot url={p.headshot_url} name={p.full_name} />
                          <span className="text-xs text-text-secondary">{p.full_name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-2.5"><PosBadge pos={p.position} /></td>
                      <td className="px-4 py-2.5 text-xs text-text-muted">{p.team_abbr}</td>
                      <td className="px-4 py-2.5 text-right text-xs font-bold tabular-nums" style={{ color: posColor(p.position) }}>
                        {p.projected_points.toFixed(1)}
                      </td>
                      {lineup.total_salary > 0 && (
                        <td className="px-4 py-2.5 text-right text-xs text-text-muted tabular-nums">
                          ${p.salary.toLocaleString()}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Exposure table */}
          {Object.keys(result.exposure).length > 0 && (
            <div className="rounded-xl border border-border bg-surface-850 overflow-hidden">
              <div className="px-5 py-3 border-b border-border">
                <span className="text-xs font-display uppercase tracking-widest text-text-muted">
                  Player Exposure ({result.total_lineups} lineups)
                </span>
              </div>
              <div className="p-4 grid grid-cols-2 gap-2">
                {Object.entries(result.exposure)
                  .sort((a, b) => b[1].pct - a[1].pct)
                  .map(([pid, e]) => (
                    <div key={pid} className="flex items-center gap-2 text-xs">
                      <PosBadge pos={e.position} />
                      <span className="flex-1 text-text-secondary truncate">{e.full_name}</span>
                      <div className="w-16 bg-surface-800 rounded-full h-1.5 overflow-hidden">
                        <div className="h-full bg-accent rounded-full" style={{ width: `${e.pct}%` }} />
                      </div>
                      <span className="text-text-muted w-10 text-right">{e.pct}%</span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!result && !loading && (
        <p className="text-sm text-text-muted text-center py-8">
          Configure options above and click Optimize to generate lineups.
        </p>
      )}
    </div>
  );
}
