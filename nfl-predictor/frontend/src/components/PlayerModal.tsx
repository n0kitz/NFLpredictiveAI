import { useEffect } from 'react';
import type { PlayerEntry } from '../api/types';
import type { TeamColor } from '../theme/teamColors';

interface Props {
  player: PlayerEntry;
  teamColors: TeamColor;
  onClose: () => void;
}

/** Convert cm to feet'inches" */
function fmtHeight(cm: number | null): string {
  if (!cm) return '—';
  const totalIn = cm / 2.54;
  const ft = Math.floor(totalIn / 12);
  const inch = Math.round(totalIn % 12);
  return `${ft}'${inch}"`;
}

/** Convert kg to lbs */
function fmtWeight(kg: number | null): string {
  if (!kg) return '—';
  return `${Math.round(kg * 2.205)} lb`;
}

type StatDef = { label: string; value: string };

function getPositionStats(player: PlayerEntry): StatDef[] {
  const s = player.stats;
  if (!s) return [];

  const pos = (player.position ?? '').toUpperCase();

  if (pos === 'QB') {
    const compPct = s.pass_attempts > 0
      ? ((s.pass_completions / s.pass_attempts) * 100).toFixed(1) + '%'
      : '—';
    return [
      { label: 'G', value: String(s.games_played) },
      { label: 'Comp%', value: compPct },
      { label: 'Pass Yds', value: s.pass_yards.toLocaleString() },
      { label: 'Pass TD', value: String(s.pass_tds) },
      { label: 'INT', value: String(s.interceptions) },
      { label: 'Rating', value: s.passer_rating.toFixed(1) },
      { label: 'Rush Yds', value: String(s.rush_yards) },
      { label: 'Rush TD', value: String(s.rush_tds) },
    ];
  }

  if (pos === 'RB' || pos === 'FB') {
    return [
      { label: 'G', value: String(s.games_played) },
      { label: 'Carries', value: String(s.rush_attempts) },
      { label: 'Rush Yds', value: s.rush_yards.toLocaleString() },
      { label: 'YPC', value: s.yards_per_carry.toFixed(1) },
      { label: 'Rush TD', value: String(s.rush_tds) },
      { label: 'Targets', value: String(s.targets) },
      { label: 'Rec', value: String(s.receptions) },
      { label: 'Rec Yds', value: String(s.rec_yards) },
    ];
  }

  if (pos === 'WR' || pos === 'TE') {
    const catchPct = s.targets > 0
      ? ((s.receptions / s.targets) * 100).toFixed(1) + '%'
      : '—';
    return [
      { label: 'G', value: String(s.games_played) },
      { label: 'Targets', value: String(s.targets) },
      { label: 'Rec', value: String(s.receptions) },
      { label: 'Catch%', value: catchPct },
      { label: 'Rec Yds', value: s.rec_yards.toLocaleString() },
      { label: 'YPR', value: s.yards_per_reception.toFixed(1) },
      { label: 'Rec TD', value: String(s.rec_tds) },
    ];
  }

  // DEF / OL / K / P — show whatever non-zero data we have
  const rows: StatDef[] = [{ label: 'G', value: String(s.games_played) }];
  if (s.rush_yards !== 0 || s.rush_tds !== 0) {
    rows.push({ label: 'Rush Yds', value: String(s.rush_yards) });
    rows.push({ label: 'Rush TD', value: String(s.rush_tds) });
  }
  if (s.receptions !== 0 || s.rec_yards !== 0) {
    rows.push({ label: 'Rec', value: String(s.receptions) });
    rows.push({ label: 'Rec Yds', value: String(s.rec_yards) });
  }
  return rows;
}

function StatusBadge({ status }: { status: string | null }) {
  if (!status || status === 'Active') return null;
  const bg =
    status === 'Out' || status === 'IR' || status === 'PUP'
      ? 'rgba(248,113,113,0.15)'
      : status === 'Doubtful'
        ? 'rgba(251,146,60,0.15)'
        : 'rgba(251,191,36,0.15)';
  const fg =
    status === 'Out' || status === 'IR' || status === 'PUP'
      ? 'var(--color-loss)'
      : status === 'Doubtful'
        ? '#fb923c'
        : 'var(--color-tie)';
  return (
    <span
      className="text-[10px] font-display font-bold uppercase tracking-wider px-2 py-0.5 rounded"
      style={{ backgroundColor: bg, color: fg }}
    >
      {status}
    </span>
  );
}

export default function PlayerModal({ player, teamColors, onClose }: Props) {
  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const stats = getPositionStats(player);
  const hasFantasy = player.stats && (player.stats.fantasy_points_ppr > 0 || player.stats.fantasy_points_standard > 0);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />

      {/* Modal card */}
      <div
        className="relative w-full max-w-md rounded-2xl border border-border bg-surface-850 shadow-2xl overflow-hidden animate-fade-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Color accent header */}
        <div
          className="h-1.5 w-full"
          style={{ background: `linear-gradient(90deg, ${teamColors.primary}, ${teamColors.secondary})` }}
        />

        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-text-muted hover:text-text-primary transition-colors z-10"
          aria-label="Close"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Player header */}
        <div className="px-6 pt-5 pb-4 flex items-start gap-4">
          {/* Headshot */}
          <div
            className="w-20 h-20 rounded-xl shrink-0 overflow-hidden flex items-center justify-center"
            style={{ backgroundColor: `${teamColors.primary}22` }}
          >
            {player.headshot_url ? (
              <img
                src={player.headshot_url}
                alt={player.full_name}
                className="w-full h-full object-cover"
                onError={(e) => {
                  const el = e.target as HTMLImageElement;
                  el.style.display = 'none';
                  el.parentElement!.innerHTML = `<span class="font-display font-bold text-2xl text-text-muted">${player.jersey_number ?? '#'}</span>`;
                }}
              />
            ) : (
              <span className="font-display font-bold text-2xl text-text-muted">
                {player.jersey_number ?? '#'}
              </span>
            )}
          </div>

          {/* Name + badges */}
          <div className="flex-1 min-w-0 pt-1">
            <h2 className="font-display text-xl font-bold text-text-primary leading-tight truncate">
              {player.full_name}
            </h2>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              {player.position && (
                <span
                  className="text-[10px] font-display font-bold uppercase tracking-wider px-2 py-0.5 rounded"
                  style={{ backgroundColor: `${teamColors.primary}30`, color: teamColors.primary }}
                >
                  {player.position}
                </span>
              )}
              {player.jersey_number && (
                <span className="text-[10px] font-display text-text-muted">#{player.jersey_number}</span>
              )}
              {player.is_starter && (
                <span className="text-[10px] font-display font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-accent/15 text-accent">
                  Starter
                </span>
              )}
              <StatusBadge status={player.roster_status} />
            </div>
          </div>
        </div>

        {/* Physical / bio info */}
        <div className="px-6 py-3 border-t border-b border-border bg-surface-800/50 grid grid-cols-4 gap-3">
          {[
            { label: 'Height', value: fmtHeight(player.height_cm) },
            { label: 'Weight', value: fmtWeight(player.weight_kg) },
            { label: 'Exp', value: player.experience_years > 0 ? `${player.experience_years} yr` : 'Rookie' },
            { label: 'College', value: player.college ?? '—' },
          ].map(({ label, value }) => (
            <div key={label} className="text-center">
              <p className="text-[9px] font-display uppercase tracking-[0.15em] text-text-muted mb-0.5">{label}</p>
              <p className="text-xs font-semibold text-text-secondary truncate" title={value}>{value}</p>
            </div>
          ))}
        </div>

        {/* Stats */}
        {stats.length > 0 && (
          <div className="px-6 pt-4 pb-2">
            <p className="text-[10px] font-display font-semibold uppercase tracking-[0.2em] text-text-muted mb-3">
              Season Stats
            </p>
            <div className="grid grid-cols-4 gap-2">
              {stats.map(({ label, value }) => (
                <div key={label} className="rounded-lg bg-surface-800 border border-border p-2.5 text-center">
                  <p className="text-[9px] font-display uppercase tracking-[0.1em] text-text-muted mb-1">{label}</p>
                  <p className="text-sm font-bold font-display tabular-nums" style={{ color: teamColors.primary }}>
                    {value}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Fantasy points */}
        {hasFantasy && player.stats && (
          <div className="px-6 pt-3 pb-5">
            <p className="text-[10px] font-display font-semibold uppercase tracking-[0.2em] text-text-muted mb-3">
              Fantasy Points
            </p>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg bg-surface-800 border border-border p-3 text-center">
                <p className="text-[9px] font-display uppercase tracking-[0.1em] text-text-muted mb-1">PPR</p>
                <p className="text-lg font-bold font-display tabular-nums text-accent">
                  {player.stats.fantasy_points_ppr.toFixed(1)}
                </p>
              </div>
              <div className="rounded-lg bg-surface-800 border border-border p-3 text-center">
                <p className="text-[9px] font-display uppercase tracking-[0.1em] text-text-muted mb-1">Standard</p>
                <p className="text-lg font-bold font-display tabular-nums text-text-secondary">
                  {player.stats.fantasy_points_standard.toFixed(1)}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* No stats fallback */}
        {!player.stats && (
          <div className="px-6 py-6 text-center text-text-muted text-sm">
            No season stats available.
          </div>
        )}
      </div>
    </div>
  );
}
