import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useGameDetail } from '../hooks/useApi';
import { api } from '../api/client';
import Spinner from '../components/Spinner';
import { getTeamColors } from '../theme/teamColors';
import type { GameBoxScorePlayer, GameDetail, GameOdds, GameRetrodiction } from '../api/types';

function prettyFactor(type: string): string {
  return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function cToF(c: number): number {
  return Math.round((c * 9) / 5 + 32);
}

function kmhToMph(k: number): number {
  return Math.round(k / 1.609);
}

/** Determine against-the-spread result from final score + home-relative spread. */
function coverResult(game: GameDetail, odds: GameOdds): string | null {
  if (game.home_score == null || game.away_score == null || odds.opening_spread == null) return null;
  const adjusted = game.home_score - game.away_score + odds.opening_spread;
  if (Math.abs(adjusted) < 1e-9) return 'Push';
  const covering = adjusted > 0 ? game.home_abbr : game.away_abbr;
  return `${covering ?? '—'} covered`;
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-surface-800 border border-border px-4 py-3">
      <p className="text-[9px] font-display uppercase tracking-[0.15em] text-text-muted mb-1">{label}</p>
      <p className="text-sm font-semibold text-text-secondary truncate" title={value}>{value}</p>
    </div>
  );
}

function passLeader(players: GameBoxScorePlayer[]): GameBoxScorePlayer | null {
  const qbs = players.filter((p) => p.pass_attempts > 0).sort((a, b) => b.pass_yards - a.pass_yards);
  return qbs[0] ?? null;
}

function rushLeaders(players: GameBoxScorePlayer[]): GameBoxScorePlayer[] {
  return players.filter((p) => p.rush_attempts > 0).sort((a, b) => b.rush_yards - a.rush_yards).slice(0, 3);
}

function recLeaders(players: GameBoxScorePlayer[]): GameBoxScorePlayer[] {
  return players
    .filter((p) => p.receptions > 0 || p.targets > 0)
    .sort((a, b) => b.rec_yards - a.rec_yards)
    .slice(0, 4);
}

function PlayerName({ p }: { p: GameBoxScorePlayer }) {
  return (
    <Link to={`/players/${p.player_id}`} className="flex items-center gap-2 text-text-primary hover:text-accent transition-colors font-medium">
      {p.headshot_url && (
        <img src={p.headshot_url} alt="" className="w-6 h-6 rounded-full object-cover bg-surface-800 shrink-0" />
      )}
      <span>
        {p.full_name}
        {p.position && <span className="text-text-muted text-[10px] ml-1">{p.position}</span>}
      </span>
    </Link>
  );
}

function teamTotals(players: GameBoxScorePlayer[]) {
  const pass = players.reduce((s, p) => s + p.pass_yards, 0);
  const rush = players.reduce((s, p) => s + p.rush_yards, 0);
  return { pass, rush, total: pass + rush };
}

function RetrodictionCard({ gameId }: { gameId: number }) {
  const [data, setData] = useState<GameRetrodiction | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.getGameRetrodiction(gameId)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(e?.message ?? 'Retrodiction unavailable'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [gameId]);

  if (loading) {
    return (
      <div className="rounded-xl border border-border bg-surface-850 p-5 mb-6 text-text-muted text-xs">
        Running model retrodiction…
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="rounded-xl border border-border bg-surface-850 p-5 mb-6 text-text-muted text-xs">
        Model retrodiction unavailable{error ? ` — ${error}` : ''}.
      </div>
    );
  }

  const home = getTeamColors(data.home_abbr);
  const away = getTeamColors(data.away_abbr);
  const homePct = Math.round(data.home_prob * 100);
  const awayPct = 100 - homePct;
  const verdict = data.correct === null ? 'TIE' : data.correct ? 'HIT' : 'MISS';
  const verdictColor =
    data.correct === null ? 'var(--color-tie)' : data.correct ? 'var(--color-win)' : 'var(--color-loss)';
  const confClass =
    data.confidence === 'high' ? 'text-conf-high' : data.confidence === 'medium' ? 'text-conf-medium' : 'text-conf-low';

  return (
    <div className="rounded-xl border border-border bg-surface-850 overflow-hidden mb-6">
      {/* Probability bar — top edge, matches PredictionCard */}
      <div className="flex h-1">
        <div style={{ width: `${awayPct}%`, backgroundColor: away.primary }} />
        <div style={{ width: `${homePct}%`, backgroundColor: home.primary }} />
      </div>
      <div className="p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-text-muted">
            Model Retrodiction
          </h2>
          <span
            className="text-[10px] font-display font-bold uppercase tracking-wider px-2 py-0.5 rounded"
            style={{ color: verdictColor, backgroundColor: `color-mix(in srgb, ${verdictColor} 12%, transparent)` }}
          >
            {verdict}
          </span>
        </div>

        <div className="flex items-center justify-between text-sm mb-3">
          <span className="font-display font-bold tabular-nums" style={{ color: away.primary }}>
            {data.away_abbr} {awayPct}%
          </span>
          <span className="text-text-secondary text-xs">
            Model picked{' '}
            <b className="text-text-primary">{data.predicted_winner_abbr}</b>
            {data.actual_winner_abbr && (
              <> · Actual: <b className="text-text-primary">{data.actual_winner_abbr}</b></>
            )}
          </span>
          <span className="font-display font-bold tabular-nums" style={{ color: home.primary }}>
            {data.home_abbr} {homePct}%
          </span>
        </div>

        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-text-muted border-t border-border pt-3">
          <span>
            Confidence: <span className={`font-semibold uppercase ${confClass}`}>{data.confidence}</span>
          </span>
          {data.predicted_spread != null && (
            <span>
              {/* predicted_spread uses Vegas convention: negative = home favored */}
              Predicted margin:{' '}
              <span className="text-text-secondary font-semibold tabular-nums">
                {data.home_abbr} {data.predicted_spread < 0 ? '+' : ''}{(-data.predicted_spread).toFixed(1)}
              </span>
            </span>
          )}
          {data.actual_margin != null && (
            <span>
              Actual margin:{' '}
              <span className="text-text-secondary font-semibold tabular-nums">
                {data.home_abbr} {data.actual_margin > 0 ? '+' : ''}{data.actual_margin}
              </span>
            </span>
          )}
        </div>

        {data.key_factors.length > 0 && (
          <ul className="mt-3 space-y-0.5">
            {data.key_factors.slice(0, 4).map((f, i) => (
              <li key={i} className="text-[11px] text-text-muted">· {f}</li>
            ))}
          </ul>
        )}

        <p className="mt-3 text-[10px] text-text-muted/70">
          Computed using only data available before {data.cutoff_date} — the same
          point-in-time setup the backtester uses.
        </p>
      </div>
    </div>
  );
}

function StatLine({ children }: { children: React.ReactNode }) {
  return <div className="flex items-baseline justify-between gap-3 text-xs py-1">{children}</div>;
}

function TeamBox({ title, abbr, players }: { title: string; abbr: string | null; players: GameBoxScorePlayer[] }) {
  const colors = getTeamColors(abbr ?? '');
  const pass = passLeader(players);
  const rush = rushLeaders(players);
  const rec = recLeaders(players);
  const totals = teamTotals(players);

  return (
    <div className="rounded-xl border border-border bg-surface-850 overflow-hidden">
      <div className="h-1" style={{ background: colors.primary }} />
      <div className="px-5 py-3 border-b border-border bg-surface-800/50">
        <h3 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em]" style={{ color: colors.primary }}>
          {title}
        </h3>
      </div>
      {totals.total > 0 && (
        <div className="px-5 py-2 border-b border-border flex gap-4 text-[11px] text-text-muted">
          <span>Pass <b className="text-text-secondary tabular-nums">{totals.pass}</b></span>
          <span>Rush <b className="text-text-secondary tabular-nums">{totals.rush}</b></span>
          <span>Total <b className="text-text-primary tabular-nums">{totals.total}</b></span>
        </div>
      )}
      <div className="p-5 space-y-5">
        {pass && (
          <div>
            <p className="text-[9px] font-display uppercase tracking-[0.15em] text-text-muted mb-1.5">Passing</p>
            <StatLine>
              <PlayerName p={pass} />
              <span className="tabular-nums text-text-secondary">
                {pass.pass_completions}/{pass.pass_attempts}, {pass.pass_yards} yds, {pass.pass_tds} TD
                {pass.interceptions > 0 && `, ${pass.interceptions} INT`}
              </span>
            </StatLine>
          </div>
        )}
        {rush.length > 0 && (
          <div>
            <p className="text-[9px] font-display uppercase tracking-[0.15em] text-text-muted mb-1.5">Rushing</p>
            {rush.map((p) => (
              <StatLine key={p.player_id}>
                <PlayerName p={p} />
                <span className="tabular-nums text-text-secondary">
                  {p.rush_attempts} car, {p.rush_yards} yds{p.rush_tds > 0 && `, ${p.rush_tds} TD`}
                </span>
              </StatLine>
            ))}
          </div>
        )}
        {rec.length > 0 && (
          <div>
            <p className="text-[9px] font-display uppercase tracking-[0.15em] text-text-muted mb-1.5">Receiving</p>
            {rec.map((p) => (
              <StatLine key={p.player_id}>
                <PlayerName p={p} />
                <span className="tabular-nums text-text-secondary">
                  {p.receptions}/{p.targets}, {p.rec_yards} yds{p.rec_tds > 0 && `, ${p.rec_tds} TD`}
                </span>
              </StatLine>
            ))}
          </div>
        )}
        {!pass && rush.length === 0 && rec.length === 0 && (
          <p className="text-text-muted text-xs">No player stats recorded.</p>
        )}
      </div>
    </div>
  );
}

export default function GameDetail() {
  const { id } = useParams<{ id: string }>();
  // normalize NaN (e.g. /games/abc) to null so it renders as not-found
  const parsed = id ? parseInt(id, 10) : NaN;
  const gameId = Number.isFinite(parsed) ? parsed : null;
  const { data: game, loading, error } = useGameDetail(gameId);

  if (loading) return <Spinner text="Loading game..." />;
  if (error || !game) {
    return (
      <div className="text-center py-20 text-text-muted">
        {error && error !== 'no id' ? error : 'Game not found'}
      </div>
    );
  }

  const home = getTeamColors(game.home_abbr ?? '');
  const away = getTeamColors(game.away_abbr ?? '');
  const played = game.home_score != null && game.away_score != null;
  const isPlayoff = game.game_type === 'playoff';
  const cover = game.odds ? coverResult(game, game.odds) : null;

  return (
    <div className="max-w-4xl mx-auto animate-fade-up">
      {/* Back link */}
      <Link
        to={`/seasons/${game.season}`}
        className="inline-flex items-center gap-1.5 text-[11px] font-display uppercase tracking-[0.15em] text-text-muted hover:text-accent transition-colors mb-6"
      >
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        {game.season} Season
      </Link>

      {/* Header / scoreboard */}
      <div className="rounded-xl border border-border bg-surface-850 overflow-hidden mb-6">
        <div className="h-1.5" style={{ background: `linear-gradient(90deg, ${away.primary}, ${home.primary})` }} />
        <div className="p-6">
          <div className="flex items-center justify-center gap-2 mb-5 flex-wrap">
            <span className="text-[10px] font-display font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-surface-800 text-text-secondary">
              {isPlayoff ? game.week : `Week ${game.week}`}
            </span>
            {isPlayoff && (
              <span className="text-[10px] font-display font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-accent/15 text-accent">
                Playoffs
              </span>
            )}
            {game.overtime && (
              <span className="text-[10px] font-display font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-surface-800 text-text-muted">
                OT
              </span>
            )}
            <span className="text-xs text-text-muted tabular-nums">{game.date}</span>
          </div>

          <div className="grid grid-cols-3 items-center gap-4">
            {/* Away */}
            <Link to={`/teams/${game.away_abbr}`} className="text-center group">
              <p className="font-display text-2xl font-bold group-hover:text-accent transition-colors" style={{ color: away.primary }}>
                {game.away_abbr}
              </p>
              <p className="text-[11px] text-text-muted mt-0.5 truncate">{game.away_team}</p>
            </Link>

            {/* Score */}
            <div className="text-center">
              {played ? (
                <div className="flex items-center justify-center gap-3">
                  <span
                    className="font-display text-4xl font-bold tabular-nums"
                    style={{ color: game.winner_id === game.away_team_id ? 'var(--color-text-primary)' : 'var(--color-text-muted)' }}
                  >
                    {game.away_score}
                  </span>
                  <span className="text-text-muted text-xl">–</span>
                  <span
                    className="font-display text-4xl font-bold tabular-nums"
                    style={{ color: game.winner_id === game.home_team_id ? 'var(--color-text-primary)' : 'var(--color-text-muted)' }}
                  >
                    {game.home_score}
                  </span>
                </div>
              ) : (
                <span className="font-display text-lg font-bold text-text-muted uppercase tracking-wider">Scheduled</span>
              )}
              {played && game.winner_abbr && (
                <p className="text-[10px] font-display uppercase tracking-wider text-win mt-1">{game.winner_abbr} win</p>
              )}
            </div>

            {/* Home */}
            <Link to={`/teams/${game.home_abbr}`} className="text-center group">
              <p className="font-display text-2xl font-bold group-hover:text-accent transition-colors" style={{ color: home.primary }}>
                {game.home_abbr}
              </p>
              <p className="text-[11px] text-text-muted mt-0.5 truncate">{game.home_team}</p>
            </Link>
          </div>
        </div>
      </div>

      {/* Meta */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
        <MetaItem label="Venue" value={game.venue || '—'} />
        <MetaItem label="Attendance" value={game.attendance ? game.attendance.toLocaleString() : '—'} />
        <MetaItem label="Type" value={isPlayoff ? 'Playoff' : 'Regular Season'} />
      </div>

      {/* Model retrodiction — only meaningful once the game is played */}
      {played && <RetrodictionCard gameId={game.game_id} />}

      <div className="grid md:grid-cols-2 gap-6 mb-6">
        {/* Betting line */}
        {game.odds && (game.odds.opening_spread != null || game.odds.over_under != null) && (
          <div className="rounded-xl border border-border bg-surface-850 p-5">
            <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-text-muted mb-4">
              Betting Line
            </h2>
            <div className="space-y-2.5 text-sm">
              {game.odds.opening_spread != null && (
                <div className="flex justify-between">
                  <span className="text-text-muted">Spread (home)</span>
                  <span className="text-text-primary font-semibold tabular-nums">
                    {game.odds.opening_spread > 0 ? `+${game.odds.opening_spread}` : game.odds.opening_spread}
                  </span>
                </div>
              )}
              {game.odds.over_under != null && (
                <div className="flex justify-between">
                  <span className="text-text-muted">Over/Under</span>
                  <span className="text-text-primary font-semibold tabular-nums">{game.odds.over_under}</span>
                </div>
              )}
              {game.odds.home_implied_prob != null && game.odds.away_implied_prob != null && (
                <div className="flex justify-between">
                  <span className="text-text-muted">Implied win %</span>
                  <span className="text-text-primary font-semibold tabular-nums">
                    {game.away_abbr} {Math.round(game.odds.away_implied_prob * 100)}% · {game.home_abbr} {Math.round(game.odds.home_implied_prob * 100)}%
                  </span>
                </div>
              )}
              {cover && (
                <div className="flex justify-between border-t border-border pt-2.5">
                  <span className="text-text-muted">ATS result</span>
                  <span className="text-accent font-semibold">{cover}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Weather */}
        {game.weather && (
          <div className="rounded-xl border border-border bg-surface-850 p-5">
            <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-text-muted mb-4">
              Conditions
            </h2>
            {game.weather.is_dome ? (
              <p className="text-sm text-text-secondary">Indoor / dome — climate controlled.</p>
            ) : (
              <div className="space-y-2.5 text-sm">
                <div className="flex justify-between">
                  <span className="text-text-muted">Condition</span>
                  <span className="text-text-primary font-semibold">{game.weather.condition}</span>
                </div>
                {game.weather.temperature_c != null && (
                  <div className="flex justify-between">
                    <span className="text-text-muted">Temperature</span>
                    <span className="text-text-primary font-semibold tabular-nums">
                      {cToF(game.weather.temperature_c)}°F
                    </span>
                  </div>
                )}
                {game.weather.wind_speed_kmh != null && (
                  <div className="flex justify-between">
                    <span className="text-text-muted">Wind</span>
                    <span className="text-text-primary font-semibold tabular-nums">
                      {kmhToMph(game.weather.wind_speed_kmh)} mph
                    </span>
                  </div>
                )}
                {game.weather.precipitation_mm != null && game.weather.precipitation_mm > 0 && (
                  <div className="flex justify-between">
                    <span className="text-text-muted">Precipitation</span>
                    <span className="text-text-primary font-semibold tabular-nums">{game.weather.precipitation_mm} mm</span>
                  </div>
                )}
                {game.weather.is_adverse && (
                  <p className="text-[11px] text-loss font-display uppercase tracking-wider pt-1">Adverse weather</p>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Box score */}
      <h2 className="font-display text-sm font-semibold uppercase tracking-[0.2em] text-text-secondary mb-4">Box Score</h2>
      {game.box_score_available ? (
        <div className="grid md:grid-cols-2 gap-6 mb-6">
          <TeamBox title={game.away_team ?? game.away_abbr ?? 'Away'} abbr={game.away_abbr} players={game.away_box} />
          <TeamBox title={game.home_team ?? game.home_abbr ?? 'Home'} abbr={game.home_abbr} players={game.home_box} />
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-surface-850 p-8 text-center text-text-muted text-sm mb-6">
          {played
            ? 'Player box score is available for regular-season games from 2018 onward.'
            : 'Box score will be available after the game is played.'}
        </div>
      )}

      {/* Factors */}
      {game.factors.length > 0 && (
        <div className="rounded-xl border border-border bg-surface-850 p-5">
          <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-text-muted mb-4">
            Game Factors
          </h2>
          <div className="space-y-2">
            {game.factors.map((f, i) => (
              <div key={i} className="flex items-center justify-between text-sm">
                <span className="text-text-secondary">
                  <span className="text-text-muted font-display text-xs mr-2">{f.team_abbr}</span>
                  {prettyFactor(f.factor_type)}
                  {f.factor_value && <span className="text-text-muted text-xs ml-2">{f.factor_value}</span>}
                </span>
                <span
                  className="tabular-nums font-semibold font-display"
                  style={{ color: f.impact_rating >= 0 ? 'var(--color-win)' : 'var(--color-loss)' }}
                >
                  {f.impact_rating > 0 ? `+${f.impact_rating}` : f.impact_rating}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
