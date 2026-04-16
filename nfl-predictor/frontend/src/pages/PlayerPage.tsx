import { useParams, Link } from 'react-router-dom';
import { usePlayer } from '../hooks/useApi';
import Spinner from '../components/Spinner';
import { getTeamColors } from '../theme/teamColors';

function fmtHeight(cm: number | null): string {
  if (!cm) return '—';
  const totalIn = cm / 2.54;
  const ft = Math.floor(totalIn / 12);
  const inch = Math.round(totalIn % 12);
  return `${ft}'${inch}"`;
}

function fmtWeight(kg: number | null): string {
  if (!kg) return '—';
  return `${Math.round(kg * 2.205)} lb`;
}

function StatCard({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-lg bg-surface-850 border border-border p-4 text-center">
      <p className="text-[9px] font-display uppercase tracking-[0.15em] text-text-muted mb-1">{label}</p>
      <p className="text-lg font-bold font-display tabular-nums" style={{ color: accent ?? 'var(--color-text-primary)' }}>
        {value}
      </p>
    </div>
  );
}

export default function PlayerPage() {
  const { id } = useParams<{ id: string }>();
  const playerId = id ? parseInt(id, 10) : null;
  const { data: player, loading, error } = usePlayer(playerId);

  if (loading) return <Spinner text="Loading player..." />;
  if (error || !player) {
    return (
      <div className="text-center py-20 text-text-muted">
        {error ?? 'Player not found'}
      </div>
    );
  }

  const colors = player.team_abbr ? getTeamColors(player.team_abbr) : { primary: '#888', secondary: '#555' };
  const s = player.current_stats;
  const pos = (player.position ?? '').toUpperCase();

  return (
    <div className="max-w-2xl mx-auto animate-fade-up">
      {/* Back link */}
      <Link
        to="/teams"
        className="inline-flex items-center gap-1.5 text-[11px] font-display uppercase tracking-[0.15em] text-text-muted hover:text-accent transition-colors mb-6"
      >
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        Teams
        {player.team_abbr && (
          <>
            <span className="text-text-muted/40">/</span>
            <Link to={`/teams/${player.team_abbr}`} className="hover:text-accent transition-colors">
              {player.team_abbr}
            </Link>
          </>
        )}
      </Link>

      {/* Header card */}
      <div className="rounded-xl border border-border bg-surface-850 overflow-hidden mb-6">
        <div className="h-1.5" style={{ background: `linear-gradient(90deg, ${colors.primary}, ${colors.secondary})` }} />
        <div className="p-6 flex items-start gap-6">
          {/* Headshot */}
          <div
            className="w-28 h-28 rounded-xl shrink-0 overflow-hidden flex items-center justify-center"
            style={{ backgroundColor: `${colors.primary}22` }}
          >
            {player.headshot_url ? (
              <img
                src={player.headshot_url}
                alt={player.full_name}
                className="w-full h-full object-cover"
              />
            ) : (
              <span className="font-display font-bold text-3xl text-text-muted">
                {player.jersey_number ?? '?'}
              </span>
            )}
          </div>

          {/* Info */}
          <div className="flex-1">
            <h1 className="font-display text-3xl font-bold text-text-primary">{player.full_name}</h1>
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              {player.position && (
                <span
                  className="text-[10px] font-display font-bold uppercase tracking-wider px-2 py-0.5 rounded"
                  style={{ backgroundColor: `${colors.primary}30`, color: colors.primary }}
                >
                  {player.position}
                </span>
              )}
              {player.jersey_number && (
                <span className="text-sm text-text-muted font-display">#{player.jersey_number}</span>
              )}
              {player.team_abbr && (
                <Link
                  to={`/teams/${player.team_abbr}`}
                  className="text-[10px] font-display font-medium uppercase tracking-wider text-text-muted hover:text-accent transition-colors"
                >
                  {player.team_abbr}
                </Link>
              )}
              {player.status && player.status !== 'Active' && (
                <span className="text-[10px] font-display font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-loss/15 text-loss">
                  {player.status}
                </span>
              )}
            </div>

            {/* Bio grid */}
            <div className="grid grid-cols-4 gap-3 mt-4">
              {[
                { label: 'Height', value: fmtHeight(player.height_cm) },
                { label: 'Weight', value: fmtWeight(player.weight_kg) },
                { label: 'Experience', value: player.experience_years > 0 ? `${player.experience_years} yr` : 'Rookie' },
                { label: 'College', value: player.college ?? '—' },
              ].map(({ label, value }) => (
                <div key={label}>
                  <p className="text-[9px] font-display uppercase tracking-[0.15em] text-text-muted mb-0.5">{label}</p>
                  <p className="text-xs font-semibold text-text-secondary truncate" title={value}>{value}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Stats */}
      {s && (
        <div className="rounded-xl border border-border bg-surface-850 p-6 mb-6">
          <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-text-muted mb-4">
            Season Stats
          </h2>

          {pos === 'QB' && (
            <div className="grid grid-cols-4 gap-3">
              <StatCard label="Games" value={String(s.games_played)} accent={colors.primary} />
              <StatCard label="Comp%" value={s.pass_attempts > 0 ? ((s.pass_completions / s.pass_attempts) * 100).toFixed(1) + '%' : '—'} accent={colors.primary} />
              <StatCard label="Pass Yds" value={s.pass_yards.toLocaleString()} accent={colors.primary} />
              <StatCard label="Pass TD" value={String(s.pass_tds)} accent={colors.primary} />
              <StatCard label="INT" value={String(s.interceptions)} />
              <StatCard label="Rating" value={s.passer_rating.toFixed(1)} accent={colors.primary} />
              <StatCard label="Rush Yds" value={String(s.rush_yards)} />
              <StatCard label="Rush TD" value={String(s.rush_tds)} />
            </div>
          )}

          {(pos === 'RB' || pos === 'FB') && (
            <div className="grid grid-cols-4 gap-3">
              <StatCard label="Games" value={String(s.games_played)} accent={colors.primary} />
              <StatCard label="Carries" value={String(s.rush_attempts)} accent={colors.primary} />
              <StatCard label="Rush Yds" value={s.rush_yards.toLocaleString()} accent={colors.primary} />
              <StatCard label="YPC" value={s.yards_per_carry.toFixed(1)} accent={colors.primary} />
              <StatCard label="Rush TD" value={String(s.rush_tds)} accent={colors.primary} />
              <StatCard label="Targets" value={String(s.targets)} />
              <StatCard label="Rec" value={String(s.receptions)} />
              <StatCard label="Rec Yds" value={String(s.rec_yards)} />
            </div>
          )}

          {(pos === 'WR' || pos === 'TE') && (
            <div className="grid grid-cols-4 gap-3">
              <StatCard label="Games" value={String(s.games_played)} accent={colors.primary} />
              <StatCard label="Targets" value={String(s.targets)} accent={colors.primary} />
              <StatCard label="Rec" value={String(s.receptions)} accent={colors.primary} />
              <StatCard label="Catch%" value={s.targets > 0 ? ((s.receptions / s.targets) * 100).toFixed(1) + '%' : '—'} accent={colors.primary} />
              <StatCard label="Rec Yds" value={s.rec_yards.toLocaleString()} accent={colors.primary} />
              <StatCard label="YPR" value={s.yards_per_reception.toFixed(1)} accent={colors.primary} />
              <StatCard label="Rec TD" value={String(s.rec_tds)} accent={colors.primary} />
            </div>
          )}

          {pos !== 'QB' && pos !== 'RB' && pos !== 'FB' && pos !== 'WR' && pos !== 'TE' && (
            <div className="grid grid-cols-4 gap-3">
              <StatCard label="Games" value={String(s.games_played)} accent={colors.primary} />
              {s.rush_yards !== 0 && <StatCard label="Rush Yds" value={String(s.rush_yards)} />}
              {s.rush_tds !== 0 && <StatCard label="Rush TD" value={String(s.rush_tds)} />}
              {s.receptions !== 0 && <StatCard label="Rec" value={String(s.receptions)} />}
              {s.rec_yards !== 0 && <StatCard label="Rec Yds" value={String(s.rec_yards)} />}
            </div>
          )}
        </div>
      )}

      {/* Fantasy */}
      {s && (s.fantasy_points_ppr > 0 || s.fantasy_points_standard > 0) && (
        <div className="rounded-xl border border-border bg-surface-850 p-6">
          <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-text-muted mb-4">
            Fantasy Points
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg bg-surface-800 border border-border p-4 text-center">
              <p className="text-[10px] font-display uppercase tracking-[0.15em] text-text-muted mb-1">PPR</p>
              <p className="text-3xl font-bold font-display tabular-nums text-accent">
                {s.fantasy_points_ppr.toFixed(1)}
              </p>
            </div>
            <div className="rounded-lg bg-surface-800 border border-border p-4 text-center">
              <p className="text-[10px] font-display uppercase tracking-[0.15em] text-text-muted mb-1">Standard</p>
              <p className="text-3xl font-bold font-display tabular-nums text-text-secondary">
                {s.fantasy_points_standard.toFixed(1)}
              </p>
            </div>
          </div>
        </div>
      )}

      {!s && (
        <div className="rounded-xl border border-border bg-surface-850 p-12 text-center text-text-muted">
          No season stats on record.
        </div>
      )}
    </div>
  );
}
