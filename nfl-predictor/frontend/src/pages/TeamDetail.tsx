import { useParams, Link } from 'react-router-dom';
import { useTeamProfile, useTeamMetrics, useTeamGames } from '../hooks/useApi';
import Spinner from '../components/Spinner';
import TrendChart from '../components/TrendChart';
import { getTeamColors, teamBgTint } from '../theme/teamColors';

export default function TeamDetail() {
  const { abbr } = useParams<{ abbr: string }>();
  const { data: profile, loading: pLoading, error: pError } = useTeamProfile(abbr ?? '');
  const { data: metrics, loading: mLoading } = useTeamMetrics(abbr ?? '');
  const { data: games, loading: gLoading } = useTeamGames(abbr ?? '', 15);

  if (pLoading || mLoading) return <Spinner text="Loading team..." />;
  if (pError || !profile) {
    return <div className="text-loss text-sm">{pError ?? 'Team not found'}</div>;
  }

  const colors = getTeamColors(profile.team_abbr);
  const allTime = profile.all_time;
  const lastSeason = profile.last_season;

  return (
    <div>
      {/* Hero header */}
      <div className="relative rounded-xl overflow-hidden mb-8 animate-fade-up">
        {/* Background */}
        <div
          className="absolute inset-0"
          style={{
            background: `linear-gradient(135deg, ${teamBgTint(profile.team_abbr, 0.2)} 0%, ${teamBgTint(profile.team_abbr, 0.03)} 70%, transparent 100%)`,
          }}
        />
        <div className="absolute inset-0 field-lines opacity-30" />
        <div
          className="absolute -top-20 -right-20 w-80 h-80 rounded-full blur-[100px] opacity-20"
          style={{ backgroundColor: colors.primary }}
        />

        <div className="relative px-8 py-8">
          {/* Breadcrumb */}
          <Link
            to="/teams"
            className="inline-flex items-center gap-1.5 text-[11px] font-display uppercase tracking-[0.15em] text-text-muted hover:text-accent transition-colors mb-5"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            All Teams
          </Link>

          <div className="flex items-center gap-5">
            {/* Team badge */}
            <div
              className="w-16 h-16 rounded-lg flex items-center justify-center shrink-0 shadow-lg"
              style={{
                backgroundColor: colors.primary,
                boxShadow: `0 8px 32px ${teamBgTint(profile.team_abbr, 0.4)}`,
              }}
            >
              <span className="font-display font-bold text-white text-lg tracking-wider">
                {profile.team_abbr}
              </span>
            </div>

            <div>
              <h1 className="font-display text-3xl font-bold text-text-primary uppercase tracking-tight">
                {profile.team_name}
              </h1>
              <div className="flex items-center gap-3 mt-1.5">
                <span className="text-sm text-text-secondary">
                  {allTime.games_played} games all-time
                </span>
                {profile.last_season_year && (
                  <>
                    <span className="w-1 h-1 rounded-full bg-text-muted" />
                    <span className="text-sm text-text-muted">
                      Last season: {profile.last_season_year}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8 animate-fade-up stagger-1">
        <DualStatBox
          label="Record"
          allTime={`${allTime.wins}-${allTime.losses}${allTime.ties ? `-${allTime.ties}` : ''}`}
          lastSeason={lastSeason ? `${lastSeason.wins}-${lastSeason.losses}${lastSeason.ties ? `-${lastSeason.ties}` : ''}` : undefined}
          color={colors.primary}
        />
        <DualStatBox
          label="Win %"
          allTime={`${(allTime.win_pct * 100).toFixed(1)}%`}
          lastSeason={lastSeason ? `${(lastSeason.win_pct * 100).toFixed(1)}%` : undefined}
          color={colors.primary}
        />
        <DualStatBox
          label="PPG"
          allTime={allTime.ppg.toFixed(1)}
          allTimeSub={`Allowed: ${allTime.papg.toFixed(1)}`}
          lastSeason={lastSeason ? lastSeason.ppg.toFixed(1) : undefined}
          lastSeasonSub={lastSeason ? `Allowed: ${lastSeason.papg.toFixed(1)}` : undefined}
          color={colors.primary}
        />
        <DualStatBox
          label="Point Diff"
          allTime={allTime.point_differential > 0 ? `+${allTime.point_differential}` : String(allTime.point_differential)}
          lastSeason={
            lastSeason
              ? lastSeason.point_differential > 0
                ? `+${lastSeason.point_differential}`
                : String(lastSeason.point_differential)
              : undefined
          }
          color={allTime.point_differential >= 0 ? 'var(--color-win)' : 'var(--color-loss)'}
        />
        <DualStatBox
          label="Home"
          allTime={`${allTime.home_wins}-${allTime.home_losses}`}
          allTimeSub={
            allTime.home_wins + allTime.home_losses > 0
              ? `${((allTime.home_wins / (allTime.home_wins + allTime.home_losses)) * 100).toFixed(0)}%`
              : undefined
          }
          lastSeason={lastSeason ? `${lastSeason.home_wins}-${lastSeason.home_losses}` : undefined}
          lastSeasonSub={
            lastSeason && lastSeason.home_wins + lastSeason.home_losses > 0
              ? `${((lastSeason.home_wins / (lastSeason.home_wins + lastSeason.home_losses)) * 100).toFixed(0)}%`
              : undefined
          }
          color={colors.primary}
        />
        <DualStatBox
          label="Away"
          allTime={`${allTime.away_wins}-${allTime.away_losses}`}
          allTimeSub={
            allTime.away_wins + allTime.away_losses > 0
              ? `${((allTime.away_wins / (allTime.away_wins + allTime.away_losses)) * 100).toFixed(0)}%`
              : undefined
          }
          lastSeason={lastSeason ? `${lastSeason.away_wins}-${lastSeason.away_losses}` : undefined}
          lastSeasonSub={
            lastSeason && lastSeason.away_wins + lastSeason.away_losses > 0
              ? `${((lastSeason.away_wins / (lastSeason.away_wins + lastSeason.away_losses)) * 100).toFixed(0)}%`
              : undefined
          }
          color={colors.primary}
        />
        {metrics && (
          <>
            <StatBox
              label="Last 5"
              value={`${metrics.recent_wins}-${metrics.recent_losses}`}
              sub={`${(metrics.recent_win_pct * 100).toFixed(0)}% win rate`}
              color={colors.primary}
            />
            <StatBox
              label="Strength"
              value={`OFF ${metrics.offensive_strength > 0 ? '+' : ''}${(metrics.offensive_strength * 100).toFixed(0)}%`}
              sub={`DEF ${metrics.defensive_strength > 0 ? '+' : ''}${(metrics.defensive_strength * 100).toFixed(0)}%`}
              color={colors.primary}
            />
            <StatBox
              label="SOS"
              value={`.${(metrics.strength_of_schedule * 1000).toFixed(0).padStart(3, '0')}`}
              sub="Opponent Win%"
              color={metrics.strength_of_schedule >= 0.5 ? 'var(--color-loss)' : 'var(--color-win)'}
            />
            <StatBox
              label="Home Edge"
              value={`+${(metrics.dynamic_hfa * 100).toFixed(1)}%`}
              sub="Home field advantage"
              color={colors.primary}
            />
          </>
        )}
      </div>

      {/* Trend charts */}
      <div className="mb-8">
        <TrendChart
          teamAbbr={profile.team_abbr}
          primaryColor={colors.primary}
          secondaryColor={colors.secondary}
        />
      </div>

      {/* Recent games */}
      <div className="rounded-xl border border-border bg-surface-850 overflow-hidden animate-fade-up stagger-2">
        <div className="px-5 py-3 border-b border-border bg-surface-800/50">
          <h2 className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em]">
            Recent Games
          </h2>
        </div>

        <div className="p-5">
          {gLoading && <Spinner text="Loading games..." />}

          {games && (
            <div className="space-y-0">
              {games.games.map((g) => {
                const isHome = g.home_team_id === profile.team_id;
                const teamScore = isHome ? g.home_score : g.away_score;
                const oppScore = isHome ? g.away_score : g.home_score;
                const oppAbbr = isHome ? g.away_abbr : g.home_abbr;
                const won = g.winner_id === profile.team_id;
                const tie = g.winner_id === null && g.home_score !== null;

                return (
                  <div
                    key={g.game_id}
                    className="flex items-center justify-between text-sm py-2.5 border-b border-border last:border-0 hover:bg-surface-700/30 -mx-2 px-2 rounded transition-colors"
                  >
                    <span className="text-text-muted w-24 text-xs tabular-nums">{g.date}</span>
                    <span className="text-text-muted w-8 text-xs font-display uppercase tracking-wider">
                      {isHome ? 'vs' : '@'}
                    </span>
                    <Link
                      to={`/teams/${oppAbbr}`}
                      className="text-text-secondary hover:text-accent flex-1 transition-colors font-medium"
                    >
                      {oppAbbr}
                    </Link>
                    <span className="text-text-primary w-16 text-right tabular-nums font-semibold">
                      {teamScore}&ndash;{oppScore}
                    </span>
                    <span
                      className="w-8 text-center font-display font-bold text-xs ml-2 rounded py-0.5"
                      style={{
                        color: won ? 'var(--color-win)' : tie ? 'var(--color-tie)' : 'var(--color-loss)',
                        backgroundColor: won
                          ? 'rgba(52, 211, 153, 0.1)'
                          : tie
                            ? 'rgba(251, 191, 36, 0.1)'
                            : 'rgba(248, 113, 113, 0.1)',
                      }}
                    >
                      {won ? 'W' : tie ? 'T' : 'L'}
                    </span>
                    {g.overtime && (
                      <span className="text-text-muted text-[10px] ml-1.5 font-display font-medium tracking-wider">
                        OT
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Stat Box Components ────────────────────────────── */

function DualStatBox({
  label,
  allTime,
  allTimeSub,
  lastSeason,
  lastSeasonSub,
  color,
}: {
  label: string;
  allTime: string;
  allTimeSub?: string;
  lastSeason?: string;
  lastSeasonSub?: string;
  color: string;
}) {
  return (
    <div className="rounded-lg bg-surface-850 border border-border p-4 hover:border-border-strong transition-all group">
      <p className="font-display text-[10px] uppercase tracking-[0.2em] text-text-muted font-semibold mb-2">
        {label}
      </p>
      <p className="font-display text-2xl font-bold tabular-nums" style={{ color }}>
        {allTime}
      </p>
      {allTimeSub && <p className="text-[11px] text-text-muted mt-0.5">{allTimeSub}</p>}
      {lastSeason && (
        <div className="mt-3 pt-2.5 border-t border-border">
          <p className="text-[10px] text-text-muted uppercase tracking-wider font-display font-medium">
            Last Season
          </p>
          <p className="text-sm font-semibold text-text-secondary tabular-nums mt-0.5">
            {lastSeason}
          </p>
          {lastSeasonSub && (
            <p className="text-[11px] text-text-muted">{lastSeasonSub}</p>
          )}
        </div>
      )}
    </div>
  );
}

function StatBox({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  color: string;
}) {
  return (
    <div className="rounded-lg bg-surface-850 border border-border p-4 hover:border-border-strong transition-all">
      <p className="font-display text-[10px] uppercase tracking-[0.2em] text-text-muted font-semibold mb-2">
        {label}
      </p>
      <p className="font-display text-2xl font-bold" style={{ color }}>
        {value}
      </p>
      {sub && <p className="text-[11px] text-text-muted mt-0.5">{sub}</p>}
    </div>
  );
}
