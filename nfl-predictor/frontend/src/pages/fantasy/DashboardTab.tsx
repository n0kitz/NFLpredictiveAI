import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { api } from '../../api/client';
import type { FantasyProjection } from '../../api/types';
import Spinner from '../../components/Spinner';
import DataBadge from '../../components/DataBadge';
import { CURRENT_SEASON } from '../../config';
import { posColor, matchupColor } from './helpers';
import {
  PosBadge, MTooltip, ConfBadge, MLBadge, Headshot, MatchupGradePill,
} from './shared';

const DASH_POSITIONS = ['QB', 'RB', 'WR', 'TE'] as const;

export default function DashboardTab() {
  const [week, setWeek] = useState(1);
  const [season] = useState(CURRENT_SEASON);
  const [projections, setProjections] = useState<Record<string, FantasyProjection[]>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const load = useCallback(async (w: number) => {
    setLoading(true);
    setError(null);
    try {
      const results = await Promise.all(
        DASH_POSITIONS.map((pos) => api.getFantasyProjections(w, season, pos, 'ppr'))
      );
      const map: Record<string, FantasyProjection[]> = {};
      DASH_POSITIONS.forEach((pos, i) => {
        map[pos] = results[i].slice(0, 5);
      });
      setProjections(map);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load projections');
    } finally {
      setLoading(false);
    }
  }, [season]);

  useEffect(() => { load(week); }, [week, load]);

  return (
    <div className="space-y-6">
      {error && <p className="text-red-400">{error}</p>}
      {/* Info banner */}
      <div className="rounded-xl border border-border bg-surface-800/50 px-4 py-3 flex items-center gap-3 flex-wrap">
        <span className="text-[11px] text-text-muted">
          Projections: season avg adjusted for matchup, injury status &amp; weather.
        </span>
        <div className="flex items-center gap-2 ml-auto">
          <DataBadge source="espn" />
          <DataBadge source="pfr" />
          <DataBadge source="open-meteo" />
          <DataBadge source="calculated" />
        </div>
      </div>

      <div className="flex items-center gap-4">
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

      {loading ? (
        <Spinner text="Generating projections…" />
      ) : (
        <div className="grid grid-cols-2 gap-6">
          {DASH_POSITIONS.map((pos) => {
            const data = projections[pos] ?? [];
            return (
              <div key={pos} className="rounded-xl border border-border bg-surface-850 p-5">
                <div className="flex items-center gap-2 mb-4">
                  <PosBadge pos={pos} />
                  <span className="text-[11px] font-display uppercase tracking-widest text-text-muted">
                    Top 5 Week {week}
                  </span>
                </div>
                {data.length === 0 ? (
                  <p className="text-xs text-text-muted py-4 text-center">No projections available</p>
                ) : (
                  <>
                    <ResponsiveContainer width="100%" height={160}>
                      <BarChart data={data} layout="vertical" margin={{ left: 80, right: 24, top: 0, bottom: 0 }}>
                        <XAxis type="number" hide />
                        <YAxis
                          type="category"
                          dataKey="full_name"
                          tick={{ fontSize: 10, fill: 'var(--color-text-secondary)' }}
                          width={80}
                          tickFormatter={(v: string) => v.split(' ').pop() ?? v}
                        />
                        <Tooltip
                          contentStyle={{ background: 'var(--color-surface-800)', border: '1px solid var(--color-border)', borderRadius: 8 }}
                          formatter={(val) => [`${(val as number).toFixed(1)} pts`, 'Projected']}
                        />
                        <Bar dataKey="projected_points_ppr" radius={[0, 4, 4, 0]}>
                          {data.map((_, idx) => (
                            <Cell key={idx} fill={posColor(pos)} opacity={1 - idx * 0.12} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                    <div className="mt-3 space-y-1">
                      {data.map((p, i) => (
                        <button
                          key={p.player_id}
                          onClick={() => navigate(`/players/${p.player_id}`)}
                          className="w-full flex items-center gap-2 px-2 py-1 rounded hover:bg-surface-800 transition-colors text-left"
                        >
                          <span className="text-[10px] text-text-muted w-4 shrink-0">{i + 1}</span>
                          <Headshot url={p.headshot_url} name={p.full_name} />
                          <span className="flex-1 text-xs text-text-secondary truncate">{p.full_name}</span>
                          {p.model_source === 'ml' && <MLBadge projection={p} />}
                          <MatchupGradePill playerId={p.player_id} week={week} season={season} />
                          <MTooltip text={`${p.confidence === 'low' ? `Low confidence — ${p.injury_status ?? 'limited data'}` : p.confidence === 'high' ? 'Full stats, no injury concerns' : 'Based on season average'}`}>
                            <ConfBadge conf={p.confidence} />
                          </MTooltip>
                          <span className="text-xs font-bold tabular-nums" style={{ color: posColor(pos) }}>
                            {p.projected_points_ppr.toFixed(1)}
                          </span>
                          {p.floor_ppr !== null && p.ceiling_ppr !== null && (
                            <span className="text-[9px] text-text-muted tabular-nums whitespace-nowrap">
                              {p.floor_ppr.toFixed(1)}–{p.ceiling_ppr.toFixed(1)}
                            </span>
                          )}
                          {p.matchup_score !== 1.0 && (
                            <MTooltip text={`Matchup Score: ${p.matchup_score.toFixed(2)}× — opponent defensive advanced stats proxy. >1.1 = favorable, <0.9 = unfavorable, 1.0 = neutral`}>
                              <span className="text-[10px]" style={{ color: matchupColor(p.matchup_score) }}>
                                ×{p.matchup_score.toFixed(2)}
                              </span>
                            </MTooltip>
                          )}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
