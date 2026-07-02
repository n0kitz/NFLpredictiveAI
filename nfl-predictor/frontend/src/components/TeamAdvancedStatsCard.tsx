import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { TeamAdvancedStats } from '../api/types';

interface Props {
  teamAbbr: string;
}

function rankColor(rank: number | undefined): string {
  if (!rank) return 'var(--color-text-muted)';
  if (rank <= 8) return 'var(--color-win)';
  if (rank >= 25) return 'var(--color-loss)';
  return 'var(--color-text-secondary)';
}

function ordinal(n: number): string {
  const s = ['th', 'st', 'nd', 'rd'];
  const v = n % 100;
  return `${n}${s[(v - 20) % 10] ?? s[v] ?? s[0]}`;
}

const METRICS: {
  key: keyof Pick<TeamAdvancedStats,
    'turnover_margin' | 'third_down_pct' | 'redzone_efficiency' |
    'yards_per_play' | 'sack_rate_allowed' | 'qb_epa_per_play'>;
  label: string;
  fmt: (v: number) => string;
}[] = [
  { key: 'turnover_margin', label: 'Turnover Margin', fmt: (v) => (v > 0 ? `+${v.toFixed(0)}` : v.toFixed(0)) },
  { key: 'third_down_pct', label: '3rd Down Conv', fmt: (v) => `${(v * 100).toFixed(1)}%` },
  { key: 'redzone_efficiency', label: 'Red Zone TD %', fmt: (v) => `${(v * 100).toFixed(1)}%` },
  { key: 'yards_per_play', label: 'Yards / Play', fmt: (v) => v.toFixed(2) },
  { key: 'sack_rate_allowed', label: 'Sack Rate Allowed', fmt: (v) => `${(v * 100).toFixed(1)}%` },
  { key: 'qb_epa_per_play', label: 'QB EPA / Play', fmt: (v) => (v > 0 ? `+${v.toFixed(3)}` : v.toFixed(3)) },
];

export default function TeamAdvancedStatsCard({ teamAbbr }: Props) {
  const [data, setData] = useState<TeamAdvancedStats | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(false);
    api.getTeamAdvancedStats(teamAbbr)
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [teamAbbr]);

  if (error || !data) return null;

  return (
    <div className="rounded-xl border border-border bg-surface-850 overflow-hidden animate-fade-up">
      <div className="px-5 py-3 border-b border-border bg-surface-800/50 flex items-center justify-between">
        <h2 className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em]">
          Advanced Stats — {data.season}
        </h2>
        <span className="text-[10px] text-text-muted">These feed the prediction model</span>
      </div>
      <div className="p-5 grid grid-cols-2 md:grid-cols-3 gap-3">
        {METRICS.map(({ key, label, fmt }) => {
          const value = data[key];
          const rank = data.ranks[key];
          if (value === null || value === undefined) return null;
          return (
            <div key={key} className="rounded-lg bg-surface-800 border border-border p-3">
              <p className="text-[9px] font-display uppercase tracking-[0.15em] text-text-muted mb-1">
                {label}
              </p>
              <div className="flex items-baseline gap-2">
                <span className="font-display text-lg font-bold tabular-nums text-text-primary">
                  {fmt(value)}
                </span>
                {rank && (
                  <span className="text-[10px] font-display font-semibold" style={{ color: rankColor(rank) }}>
                    {ordinal(rank)}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
