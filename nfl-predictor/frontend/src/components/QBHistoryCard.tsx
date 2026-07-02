import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { TeamQBHistory } from '../api/types';

interface Props {
  teamAbbr: string;
}

/** EPA/play → chip color: green for good, red for bad, neutral around 0. */
function epaColor(epa: number | null): string {
  if (epa === null) return 'var(--color-surface-600)';
  if (epa >= 0.15) return 'rgba(52, 211, 153, 0.55)';
  if (epa >= 0.05) return 'rgba(52, 211, 153, 0.3)';
  if (epa > -0.05) return 'var(--color-surface-500)';
  if (epa > -0.15) return 'rgba(248, 113, 113, 0.3)';
  return 'rgba(248, 113, 113, 0.55)';
}

function StarterName({ name, playerId }: { name: string; playerId: number | null }) {
  if (playerId) {
    return (
      <Link to={`/players/${playerId}`} className="font-medium text-text-primary hover:text-accent transition-colors">
        {name}
      </Link>
    );
  }
  return <span className="font-medium text-text-primary">{name}</span>;
}

export default function QBHistoryCard({ teamAbbr }: Props) {
  const [data, setData] = useState<TeamQBHistory | null>(null);
  const [season, setSeason] = useState<number | undefined>(undefined);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setError(false);
    api.getTeamQBHistory(teamAbbr, season)
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [teamAbbr, season]);

  if (error || !data) return null;

  const detail = data.seasons.find((s) => s.season === data.detail_season);

  return (
    <div className="rounded-xl border border-border bg-surface-850 overflow-hidden animate-fade-up">
      <div className="px-5 py-3 border-b border-border bg-surface-800/50 flex items-center justify-between">
        <h2 className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em]">
          Starting QB History
        </h2>
        <select
          value={data.detail_season ?? ''}
          onChange={(e) => setSeason(Number(e.target.value))}
          className="bg-surface-800 border border-border rounded px-2 py-1 text-xs text-text-primary"
          aria-label="QB history season"
        >
          {data.seasons.map((s) => (
            <option key={s.season} value={s.season}>{s.season}</option>
          ))}
        </select>
      </div>

      <div className="p-5 space-y-4">
        {/* Weekly strip: one chip per start, colored by EPA */}
        {data.weeks.length > 0 && (
          <div>
            <p className="text-[10px] text-text-muted uppercase tracking-wider font-display font-medium mb-2">
              Week-by-week starts, {data.detail_season} (color = EPA/play)
            </p>
            <div className="flex flex-wrap gap-1">
              {data.weeks.map((w) => (
                <div
                  key={`${w.week}-${w.qb_name}`}
                  className="px-1.5 py-1 rounded text-[9px] font-display font-semibold text-text-primary text-center min-w-9"
                  style={{ backgroundColor: epaColor(w.epa_per_play) }}
                  title={`Week ${w.week}: ${w.qb_name}${w.epa_per_play !== null ? ` · EPA ${w.epa_per_play.toFixed(2)}` : ''}${w.snap_count !== null ? ` · ${w.snap_count} snaps` : ''}`}
                >
                  <div className="text-text-muted">W{w.week}</div>
                  <div>{w.qb_name.split('.').pop()}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Starters summary for the selected season */}
        {detail && (
          <div className="space-y-1.5">
            {detail.starters.map((st) => (
              <div key={st.qb_name} className="flex items-center gap-3 text-xs bg-surface-800 border border-border rounded-md px-3 py-2">
                <StarterName name={st.qb_name} playerId={st.player_id} />
                <span className="text-text-muted">{st.starts} start{st.starts !== 1 ? 's' : ''}</span>
                {st.avg_epa !== null && (
                  <span
                    className="ml-auto font-display font-semibold tabular-nums"
                    style={{ color: st.avg_epa >= 0.05 ? 'var(--color-win)' : st.avg_epa <= -0.05 ? 'var(--color-loss)' : 'var(--color-text-secondary)' }}
                  >
                    {st.avg_epa > 0 ? '+' : ''}{st.avg_epa.toFixed(3)} EPA/play
                  </span>
                )}
              </div>
            ))}
          </div>
        )}

        <p className="text-[10px] text-text-muted">
          Starts and EPA from play-by-play data (2010 onward). EPA/play measures how much
          each dropback changed expected points — +0.1 is elite, below −0.1 is struggling.
        </p>
      </div>
    </div>
  );
}
