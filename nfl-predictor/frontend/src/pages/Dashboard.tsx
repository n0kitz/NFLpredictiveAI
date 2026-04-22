import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { Prediction, ValuePick, AccuracyStats } from '../api/types';
import { useAccuracy, useValuePicks } from '../hooks/useApi';
import TeamLogo from '../components/TeamLogo';
import Spinner from '../components/Spinner';
import { getTeamColors } from '../theme/teamColors';

const FEATURED_MATCHUPS: [string, string][] = [
  ['KC', 'PHI'],
  ['SF', 'DAL'],
  ['BAL', 'BUF'],
  ['DET', 'GB'],
  ['MIA', 'NYJ'],
  ['CIN', 'CLE'],
  ['LAR', 'SEA'],
  ['NO', 'ATL'],
];

interface MatchupResult {
  prediction: Prediction;
  homeAbbr: string;
  awayAbbr: string;
}

// ── helpers ──────────────────────────────────────────────────────────────────

function shortName(fullName: string): string {
  return fullName.trim().split(' ').at(-1) ?? fullName;
}

function confidenceWord(prob: number): string {
  const p = prob * 100;
  if (p >= 68) return 'heavy';
  if (p >= 62) return 'clear';
  if (p >= 57) return 'narrow';
  return 'slight';
}

// ── EditorialHeader ──────────────────────────────────────────────────────────

function EditorialHeader({ accuracy, top }: { accuracy: AccuracyStats; top: MatchupResult }) {
  const { prediction: pred, homeAbbr, awayAbbr } = top;
  const winnerAbbr = pred.home_win_probability >= 0.5 ? homeAbbr : awayAbbr;
  const loserAbbr = winnerAbbr === homeAbbr ? awayAbbr : homeAbbr;
  const winnerFullName = winnerAbbr === homeAbbr ? pred.home_team : pred.away_team;
  const loserFullName = winnerAbbr === homeAbbr ? pred.away_team : pred.home_team;
  const winProb = Math.max(pred.home_win_probability, pred.away_win_probability);
  const confWord = confidenceWord(winProb);
  const winnerColors = getTeamColors(winnerAbbr);
  // suppress unused var warning
  void loserAbbr;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[1fr_auto] gap-10 xl:gap-16 items-end pb-8 border-b border-border animate-fade-up">
      {/* Left: editorial headline with team-color accent bar */}
      <div className="flex gap-6 items-start">
        <div
          className="hidden md:block w-[3px] rounded-full shrink-0 mt-1"
          style={{
            background: `linear-gradient(to bottom, ${winnerColors.primary}, ${winnerColors.primary}40)`,
            height: '7rem',
          }}
        />
        <div>
          <div className="font-display text-[11px] font-bold tracking-[0.2em] text-accent mb-3">
            2025 SEASON · MODEL BRIEFING
          </div>
          <h1 className="font-display text-5xl md:text-6xl lg:text-[76px] font-extrabold tracking-[-0.045em] leading-[0.92] m-0">
            <span style={{ color: winnerColors.primary }}>{shortName(winnerFullName)}</span> open as
            <br />
            <span className="text-text-primary">{confWord}</span> favorites
            <br />
            <span className="text-text-muted font-bold text-4xl md:text-5xl lg:text-6xl">over the {shortName(loserFullName)}.</span>
          </h1>
          <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-text-muted">
            The model gives {winnerFullName} a {Math.round(winProb * 100)}% edge.
            Below, a full market scan and this week's highest-edge value picks.
          </p>
        </div>
      </div>

      {/* Right: accuracy card */}
      <div
        className="flex flex-col gap-2 p-5 rounded-lg min-w-[220px] shrink-0 relative overflow-hidden"
        style={{
          background: `linear-gradient(135deg, ${winnerColors.primary}18 0%, transparent 60%)`,
          border: `1px solid ${winnerColors.primary}30`,
        }}
      >
        <div
          className="absolute top-0 left-0 right-0 h-[2px]"
          style={{ background: `linear-gradient(to right, ${winnerColors.primary}, transparent)` }}
        />
        <div className="font-display text-[10px] font-bold tracking-[0.14em] text-text-muted">
          SEASON ACCURACY
        </div>
        <div className="font-display text-5xl font-extrabold tracking-[-0.03em] leading-none tabular-nums">
          {(accuracy.accuracy * 100).toFixed(1)}
          <span className="text-[0.5em] opacity-50">%</span>
        </div>
        <div className="text-[11px] text-text-muted">
          {accuracy.correct_predictions}/{accuracy.total_games} games · 2025
        </div>
        <div className="mt-1 h-1 rounded-full bg-surface-600 overflow-hidden">
          <div
            className="h-full rounded-full"
            style={{
              width: `${(accuracy.accuracy * 100).toFixed(1)}%`,
              background: `linear-gradient(to right, ${winnerColors.primary}, ${winnerColors.primary}cc)`,
            }}
          />
        </div>
        <Link
          to="/predict"
          className="mt-3 px-4 py-2 font-display text-[11px] font-bold tracking-[0.1em] uppercase rounded-sm transition-colors text-center"
          style={{
            background: winnerColors.primary,
            color: '#0a0b0e',
          }}
        >
          RUN A PREDICTION →
        </Link>
      </div>
    </div>
  );
}

// ── StoryCard ────────────────────────────────────────────────────────────────

function StoryCard({ m, index }: { m: MatchupResult; index: number }) {
  const { prediction: pred, homeAbbr, awayAbbr } = m;
  const awayPct = Math.round(pred.away_win_probability * 100);
  const homePct = 100 - awayPct;
  const winnerAbbr = pred.home_win_probability >= 0.5 ? homeAbbr : awayAbbr;
  const winnerName = shortName(winnerAbbr === homeAbbr ? pred.home_team : pred.away_team);
  const winnerPct = Math.max(awayPct, homePct);
  const winnerColors = getTeamColors(winnerAbbr);
  const awayColors = getTeamColors(awayAbbr);
  const homeColors = getTeamColors(homeAbbr);

  const confLabel = pred.confidence === 'high' ? 'HIGH' : pred.confidence === 'medium' ? 'MED' : 'LOW';
  const confColor = pred.confidence === 'high' ? '#34d399' : pred.confidence === 'medium' ? '#fbbf24' : '#515872';
  const isFeatured = index === 0;

  return (
    <div
      className="relative rounded-xl overflow-hidden transition-all duration-200 hover:-translate-y-0.5 group"
      style={{
        background: isFeatured ? `linear-gradient(135deg, ${winnerColors.primary}12, transparent 50%)` : undefined,
        border: `1px solid var(--color-border)`,
      }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = `${winnerColors.primary}60`)}
      onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--color-border)')}
    >
      {/* Team-color top accent strip */}
      <div className="flex h-[3px]">
        <div style={{ flex: awayPct, background: awayColors.primary, transition: 'flex 600ms cubic-bezier(.2,.7,.2,1)' }} />
        <div style={{ flex: homePct, background: homeColors.primary, transition: 'flex 600ms cubic-bezier(.2,.7,.2,1)' }} />
      </div>

      <div className="p-5">
        {/* Meta row */}
        <div className="flex items-center justify-between mb-4 font-display text-[10px] font-bold tracking-[0.14em]">
          <span className="text-text-muted">{isFeatured ? 'FEATURED' : 'THIS WEEK'}</span>
          <span
            className="px-2 py-0.5 rounded-sm text-[9px]"
            style={{ color: confColor, background: `${confColor}18`, border: `1px solid ${confColor}30` }}
          >
            {confLabel} CONF
          </span>
        </div>

        {/* Matchup row */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2.5">
            <TeamLogo abbr={awayAbbr} size={38} />
            <div>
              <div className="font-display text-base font-bold tracking-tight">{shortName(pred.away_team)}</div>
              <div className="font-display text-[11px] tabular-nums" style={{ color: awayColors.primary }}>{awayPct}%</div>
            </div>
          </div>
          <span className="font-display text-[10px] text-text-muted font-bold tracking-widest">AT</span>
          <div className="flex items-center gap-2.5 flex-row-reverse">
            <TeamLogo abbr={homeAbbr} size={38} />
            <div className="text-right">
              <div className="font-display text-base font-bold tracking-tight">{shortName(pred.home_team)}</div>
              <div className="font-display text-[11px] tabular-nums" style={{ color: homeColors.primary }}>{homePct}%</div>
            </div>
          </div>
        </div>

        {/* Prob bar */}
        <div className="flex h-[5px] rounded-full overflow-hidden bg-surface-600">
          <div style={{ width: `${awayPct}%`, background: awayColors.primary, boxShadow: `0 0 8px ${awayColors.primary}66`, transition: 'width 600ms cubic-bezier(.2,.7,.2,1)' }} />
          <div style={{ width: `${homePct}%`, background: homeColors.primary, boxShadow: `0 0 8px ${homeColors.primary}66`, transition: 'width 600ms cubic-bezier(.2,.7,.2,1)' }} />
        </div>

        {/* Bottom row */}
        <div className="flex justify-between items-end mt-4">
          <div>
            <div className="font-display text-[10px] font-bold tracking-[0.14em] text-text-muted mb-0.5">MODEL PICK</div>
            <div className="font-display text-xl font-extrabold tracking-tight" style={{ color: winnerColors.primary }}>
              {winnerName} <span className="text-text-muted font-bold text-sm">{winnerPct}%</span>
            </div>
          </div>
          <Link
            to="/predict"
            className="font-display text-[10px] font-bold tracking-[0.1em] px-3 py-1.5 rounded-sm transition-colors"
            style={{ color: winnerColors.primary, border: `1px solid ${winnerColors.primary}40`, background: `${winnerColors.primary}10` }}
            onMouseEnter={e => (e.currentTarget.style.background = `${winnerColors.primary}25`)}
            onMouseLeave={e => (e.currentTarget.style.background = `${winnerColors.primary}10`)}
          >
            PREDICT →
          </Link>
        </div>
      </div>
    </div>
  );
}

// ── WeekStoryGrid ────────────────────────────────────────────────────────────

function WeekStoryGrid({ matchups }: { matchups: MatchupResult[] }) {
  const highCount = matchups.filter(m => m.prediction.confidence === 'high').length;
  return (
    <div className="animate-fade-up stagger-2">
      <div className="flex items-baseline gap-4 mb-6">
        <h2 className="font-display text-[26px] font-extrabold tracking-[-0.03em]">The Slate</h2>
        <span className="font-display text-[11px] text-text-muted tracking-[0.04em]">
          {matchups.length} matchups &middot; {highCount} high-confidence {highCount === 1 ? 'call' : 'calls'}
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {matchups.map((m, i) => (
          <StoryCard key={`${m.awayAbbr}-${m.homeAbbr}`} m={m} index={i} />
        ))}
      </div>
    </div>
  );
}

// ── SleeperRow ───────────────────────────────────────────────────────────────

function SleeperRow({ pick, rank }: { pick: ValuePick; rank: number }) {
  const teamAbbr = pick.edge_side === 'home' ? pick.home_team : pick.away_team;
  const edgePp = Math.round(Math.abs(pick.edge) * 100);
  const teamColors = getTeamColors(teamAbbr);
  const confColor =
    pick.model_confidence === 'HIGH' ? '#34d399' :
    pick.model_confidence === 'MEDIUM' ? '#fbbf24' : '#515872';
  const isOdd = rank % 2 === 1;

  const dateStr = (() => {
    try {
      return new Date(pick.game_date + 'T12:00:00').toLocaleDateString('en-US', {
        weekday: 'short', month: 'short', day: 'numeric',
      });
    } catch {
      return pick.game_date;
    }
  })();

  return (
    <div
      className={`grid items-center py-4 px-3.5 border-b border-border transition-colors cursor-default ${
        isOdd ? 'border-r border-border' : ''
      }`}
      style={{ gridTemplateColumns: '28px auto 1fr auto auto', gap: '12px' }}
      onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.02)')}
      onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
    >
      <span className="font-display text-lg font-extrabold tabular-nums" style={{ color: `${teamColors.primary}80` }}>
        {String(rank).padStart(2, '0')}
      </span>
      <TeamLogo abbr={teamAbbr} size={30} />
      <div className="min-w-0">
        <div className="font-display text-sm font-bold tracking-tight truncate">
          <span style={{ color: getTeamColors(pick.away_team).primary }}>{pick.away_team}</span>
          <span className="text-text-muted mx-1">@</span>
          <span style={{ color: getTeamColors(pick.home_team).primary }}>{pick.home_team}</span>
        </div>
        <div className="text-[11px] text-text-muted">
          {dateStr}{pick.vegas_spread !== null ? ` · ${pick.vegas_spread > 0 ? '+' : ''}${pick.vegas_spread}` : ''}
        </div>
      </div>
      <div className="text-right shrink-0">
        <div className="font-display text-sm font-bold tabular-nums text-text-primary">
          {Math.round(pick.model_home_prob * 100)}%
        </div>
        <div className="font-display text-[9px] font-bold tracking-[0.1em] text-text-muted">MODEL</div>
      </div>
      <div className="text-right shrink-0">
        <div className="font-display text-base font-extrabold tracking-tight tabular-nums" style={{ color: confColor }}>
          +{edgePp}pp
        </div>
        <div className="font-display text-[9px] font-bold tracking-[0.12em] mt-0.5" style={{ color: confColor, opacity: 0.7 }}>
          {pick.model_confidence}
        </div>
      </div>
    </div>
  );
}

// ── SleeperColumn ────────────────────────────────────────────────────────────

function SleeperColumn({ picks }: { picks: ValuePick[] }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-12 pt-8 border-t border-border animate-fade-up stagger-6">
      {/* Editorial left */}
      <div>
        <div className="font-display text-[11px] font-bold tracking-[0.2em] text-accent mb-3">
          GAME ANALYSIS · VALUE PICKS
        </div>
        <h2 className="font-display text-[42px] font-extrabold tracking-[-0.04em] leading-[1.0]">
          {picks.length > 0 ? (
            <>
              {picks.length} games where<br />
              the model{' '}
              <em className="not-italic text-accent">beats<br />the chalk.</em>
            </>
          ) : (
            <>
              Model and Vegas<br />
              <em className="not-italic text-accent">agree<br />this week.</em>
            </>
          )}
        </h2>
        <p className="mt-5 text-[14px] leading-relaxed text-text-muted max-w-[320px]">
          Games where our model disagrees with Vegas by ≥4 probability points.
          Positive edge = market is under-pricing one side.
        </p>
        <Link
          to="/predict"
          className="inline-flex items-center gap-2 mt-6 font-display text-[11px] font-bold tracking-[0.12em] text-accent hover:text-accent-hover transition-colors"
        >
          FULL PREDICTIONS →
        </Link>
      </div>

      {/* Data grid or empty state */}
      {picks.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 border-t border-border">
          {picks.slice(0, 8).map((p, i) => (
            <SleeperRow key={p.game_id} pick={p} rank={i + 1} />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center border border-border rounded-xl py-12 gap-3">
          <div className="font-display text-3xl font-extrabold text-text-muted opacity-30">✓</div>
          <p className="font-display text-[11px] font-bold tracking-[0.1em] text-text-muted text-center">
            NO ACTIVE EDGES THIS WEEK
          </p>
          <p className="text-[12px] text-text-muted text-center max-w-[240px] leading-relaxed">
            Model and Vegas agree on all upcoming matchups. Check back after odds refresh.
          </p>
        </div>
      )}
    </div>
  );
}

// ── Dashboard ────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [matchups, setMatchups] = useState<MatchupResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { data: accuracy } = useAccuracy('2025');
  const { data: valuePicks } = useValuePicks();

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const settled = await Promise.allSettled(
          FEATURED_MATCHUPS.map(async ([away, home]) => {
            const prediction = await api.predictGet(away, home);
            return { prediction, homeAbbr: home, awayAbbr: away };
          }),
        );
        if (!cancelled) {
          const successful = settled
            .filter((r): r is PromiseFulfilledResult<MatchupResult> => r.status === 'fulfilled')
            .map(r => r.value);
          setMatchups(successful);
          if (successful.length === 0) setError('No predictions could be loaded');
          setLoading(false);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load predictions');
          setLoading(false);
        }
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const picks = valuePicks?.picks ?? [];
  const topMatchup = matchups[0] ?? null;
  const slateMatchups = matchups.slice(1);

  return (
    <div className="flex flex-col gap-12">
      {/* Editorial header — shows when both accuracy and first matchup are ready */}
      {accuracy && accuracy.total_games > 0 && topMatchup ? (
        <EditorialHeader accuracy={accuracy} top={topMatchup} />
      ) : loading ? (
        <div className="flex items-center gap-3 h-40">
          <Spinner text="Loading predictions…" />
        </div>
      ) : null}

      {/* Error state */}
      {error && (
        <div className="rounded-md bg-loss/10 border border-loss/20 px-5 py-3 text-sm text-loss animate-fade-in">
          {error}
        </div>
      )}

      {/* The Slate — matchup story grid */}
      {slateMatchups.length > 0 && (
        <WeekStoryGrid matchups={slateMatchups} />
      )}

      {/* Value picks column */}
      <SleeperColumn picks={picks} />
    </div>
  );
}
