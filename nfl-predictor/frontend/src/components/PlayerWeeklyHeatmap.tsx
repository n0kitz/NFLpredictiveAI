import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { PlayerWeeklyStatsResponse, PlayerWeekCell } from '../api/types';
import HeatStrip from './HeatStrip';
import Spinner from './Spinner';

interface Props {
  playerId: number;
  position: string | null;
  defaultSeason?: number;
}

const SEASON_OPTIONS = (() => {
  const now = new Date().getFullYear();
  return [now, now - 1, now - 2, now - 3];
})();

function fmtPct(p: number): string {
  return `${Math.round(p * 100)}`;
}

function tooltip(c: PlayerWeekCell): string {
  if (c.is_bye) return `Week ${c.week}: BYE`;
  if (c.snaps === 0) return `Week ${c.week}: did not play`;
  const opp = c.opponent_abbr ? (c.is_home ? `vs ${c.opponent_abbr}` : `@ ${c.opponent_abbr}`) : '';
  return [
    `Week ${c.week} ${opp}`,
    `Snaps: ${c.snaps} (${fmtPct(c.snap_pct)}%)`,
    c.targets ? `Targets: ${c.targets} (${fmtPct(c.target_share)}%)` : '',
    c.rec_yards ? `Rec yds: ${c.rec_yards}` : '',
    c.rush_yards ? `Rush yds: ${c.rush_yards}` : '',
    c.pass_yards ? `Pass yds: ${c.pass_yards}` : '',
    `Fantasy: ${c.fantasy_points_ppr.toFixed(1)} PPR`,
  ].filter(Boolean).join(' · ');
}

export default function PlayerWeeklyHeatmap({ playerId, position, defaultSeason }: Props) {
  const [season, setSeason] = useState(defaultSeason ?? SEASON_OPTIONS[1]);
  const [data, setData] = useState<PlayerWeeklyStatsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.getPlayerWeeklyStats(playerId, season)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(e?.message ?? 'Failed to load weekly stats'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [playerId, season]);

  if (loading) return <Spinner text="Loading weekly stats…" />;
  if (error) return <div className="text-text-muted text-xs">{error}</div>;
  if (!data || data.weeks.length === 0) {
    return <div className="text-text-muted text-xs">No weekly data for {season}.</div>;
  }

  const showTargetShare = ['WR', 'TE', 'RB'].includes((position ?? '').toUpperCase());

  const snapCells = data.weeks.map((c) => ({
    week: c.week,
    value: c.snap_pct,
    rawLabel: c.is_bye ? '' : (c.snap_pct > 0 ? Math.round(c.snap_pct * 100).toString() : '·'),
    tooltip: tooltip(c),
    isBye: c.is_bye,
    isMissing: !c.is_bye && c.snaps === 0,
  }));

  const targetCells = data.weeks.map((c) => ({
    week: c.week,
    value: c.target_share,
    rawLabel: c.is_bye ? '' : (c.target_share > 0 ? Math.round(c.target_share * 100).toString() : '·'),
    tooltip: tooltip(c),
    isBye: c.is_bye,
    isMissing: !c.is_bye && c.targets === 0,
  }));

  return (
    <div className="rounded-xl border border-border bg-surface-850 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[11px] font-display uppercase tracking-[0.15em] text-text-secondary">Weekly Workload</h3>
        <select
          value={season}
          onChange={(e) => setSeason(Number(e.target.value))}
          className="bg-surface-800 border border-border rounded px-2 py-1 text-xs text-text-secondary focus:outline-none focus:border-accent"
        >
          {SEASON_OPTIONS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>
      <HeatStrip cells={snapCells} hue="green" label="Snap %" />
      {showTargetShare && <HeatStrip cells={targetCells} hue="blue" label="Target share %" />}
    </div>
  );
}
