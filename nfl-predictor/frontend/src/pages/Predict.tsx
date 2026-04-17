import { useState } from 'react';
import { useTeams, usePrediction, useExplainPrediction, useH2H } from '../hooks/useApi';
import TeamSelector from '../components/TeamSelector';
import PredictionCard from '../components/PredictionCard';
import FactorPanel from '../components/FactorPanel';
import ExplanationPanel, { ExplanationSkeleton } from '../components/ExplanationPanel';
import Spinner from '../components/Spinner';
import H2HTimeline from '../components/H2HTimeline';
import { getTeamColors } from '../theme/teamColors';
import type { InlineFactor } from '../api/types';

export default function Predict() {
  const { data: teamList } = useTeams();
  const [homeAbbr, setHomeAbbr] = useState('');
  const [awayAbbr, setAwayAbbr] = useState('');
  const [factors, setFactors] = useState<InlineFactor[]>([]);
  const { data: prediction, loading, error, predict } = usePrediction();
  const { data: explanationData, loading: explainLoading, explain } = useExplainPrediction();

  const showH2H = !!(prediction && homeAbbr && awayAbbr);

  function handlePredict() {
    if (homeAbbr && awayAbbr) {
      const f = factors.length > 0 ? factors : undefined;
      // Fire both calls in parallel
      predict(homeAbbr, awayAbbr, f);
      explain(homeAbbr, awayAbbr, f);
    }
  }

  const canPredict = homeAbbr && awayAbbr && homeAbbr !== awayAbbr;

  return (
    <div>
      {/* Header */}
      <div className="mb-8 animate-fade-up">
        <div className="flex items-center gap-3 mb-3">
          <div className="h-px w-6 bg-accent" />
          <span className="font-display text-[11px] uppercase tracking-[0.2em] text-accent font-semibold">
            Matchup Analysis
          </span>
        </div>
        <h1 className="font-display text-3xl font-bold text-text-primary uppercase tracking-tight">
          Predict
        </h1>
        <p className="text-text-secondary text-sm mt-2">
          Select any two teams and see the win probability breakdown.
        </p>
      </div>

      {/* Team selectors */}
      <div className="rounded-lg border border-border bg-surface-850 p-6 mb-6 animate-fade-up stagger-1">
        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-5 items-end">
          <TeamSelector
            teams={teamList?.teams ?? []}
            value={awayAbbr}
            onChange={setAwayAbbr}
            label="Away Team"
            excludeAbbr={homeAbbr}
          />

          <div className="font-display text-text-muted text-xl font-bold self-center pt-5 hidden md:block">
            @
          </div>

          <TeamSelector
            teams={teamList?.teams ?? []}
            value={homeAbbr}
            onChange={setHomeAbbr}
            label="Home Team"
            excludeAbbr={awayAbbr}
          />
        </div>

        {canPredict && (
          <div className="mt-5">
            <FactorPanel
              homeAbbr={homeAbbr}
              awayAbbr={awayAbbr}
              factors={factors}
              onChange={setFactors}
            />
          </div>
        )}

        <button
          onClick={handlePredict}
          disabled={!canPredict || loading}
          className="w-full mt-6 px-6 py-3.5 rounded-md bg-accent text-surface-900 font-display font-semibold text-sm uppercase tracking-wider
                     hover:bg-accent-hover disabled:opacity-25 disabled:cursor-not-allowed
                     transition-all active:scale-[0.98]"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
              </svg>
              Analyzing...
            </span>
          ) : (
            'Run Prediction'
          )}
        </button>
      </div>

      {error && (
        <div className="rounded-md bg-loss/10 border border-loss/20 px-5 py-3 text-sm text-loss mb-6 animate-fade-in">
          {error}
        </div>
      )}

      {/* Results */}
      {prediction && (
        <div className="space-y-5 animate-fade-up">
          <PredictionCard prediction={prediction} homeAbbr={homeAbbr} awayAbbr={awayAbbr} />

          {/* SHAP explanation — fires in parallel with prediction */}
          {explainLoading && <ExplanationSkeleton />}
          {!explainLoading && explanationData && (
            <ExplanationPanel
              explanation={explanationData.explanation}
              homeAbbr={homeAbbr}
              awayAbbr={awayAbbr}
            />
          )}

          {/* Key factors */}
          <div className="rounded-lg border border-border bg-surface-850 p-5">
            <h2 className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em] mb-4">
              Key Factors
            </h2>
            <ul className="space-y-2.5">
              {prediction.key_factors.map((factor, i) => (
                <li key={i} className="text-sm text-text-secondary flex items-start gap-3">
                  <span
                    className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0"
                    style={{ backgroundColor: 'var(--color-accent)' }}
                  />
                  {factor}
                </li>
              ))}
            </ul>
          </div>

          {/* H2H */}
          {showH2H && <H2HSection team1={awayAbbr} team2={homeAbbr} />}
        </div>
      )}
    </div>
  );
}

function H2HSection({ team1, team2 }: { team1: string; team2: string }) {
  const { data: h2h, loading, error } = useH2H(team1, team2, 10);

  if (loading) return <Spinner text="Loading head-to-head..." />;
  if (error || !h2h) return null;

  const t1Color = getTeamColors(h2h.team1_abbr).primary;
  const t2Color = getTeamColors(h2h.team2_abbr).primary;
  const totalWins = h2h.team1_wins + h2h.team2_wins + h2h.ties;
  const t1Pct = totalWins > 0 ? (h2h.team1_wins / totalWins) * 100 : 50;

  return (
    <div className="rounded-lg border border-border bg-surface-850 p-5">
      <h2 className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em] mb-5">
        Head-to-Head &middot; Last {h2h.total_games}
      </h2>

      {/* Win comparison */}
      <div className="flex items-center gap-4 mb-2">
        <span className="font-display text-xl font-bold tabular-nums" style={{ color: t1Color }}>
          {h2h.team1_abbr} {h2h.team1_wins}
        </span>
        <div className="flex-1" />
        <span className="font-display text-xl font-bold tabular-nums" style={{ color: t2Color }}>
          {h2h.team2_wins} {h2h.team2_abbr}
        </span>
      </div>

      {/* Bar */}
      <div className="flex h-2.5 rounded-sm overflow-hidden mb-2">
        <div
          className="transition-all duration-700 ease-out"
          style={{ width: `${t1Pct}%`, backgroundColor: t1Color }}
        />
        <div
          className="transition-all duration-700 ease-out"
          style={{ width: `${100 - t1Pct}%`, backgroundColor: t2Color }}
        />
      </div>
      {h2h.ties > 0 && (
        <p className="text-[11px] text-text-muted text-center mb-3">
          {h2h.ties} tie{h2h.ties > 1 ? 's' : ''}
        </p>
      )}

      {/* Score timeline */}
      <div className="mt-4 mb-4">
        <H2HTimeline h2h={h2h} t1={h2h.team1_abbr} t2={h2h.team2_abbr} c1={t1Color} c2={t2Color} />
      </div>

      {/* Games list */}
      <div className="mt-5 space-y-0">
        {h2h.games.slice(0, 10).map((g) => {
          const winnerIsT1 = g.winner_abbr === h2h.team1_abbr;
          const isTie = g.winner_abbr === null;
          return (
            <div
              key={g.game_id}
              className="flex items-center justify-between text-xs py-2.5 border-b border-border last:border-0"
            >
              <span className="text-text-muted w-24 tabular-nums">{g.date}</span>
              <span className="text-text-secondary flex-1">
                {g.away_abbr} {g.away_score} @ {g.home_abbr} {g.home_score}
              </span>
              <span
                className="font-display font-bold w-10 text-right tracking-wide"
                style={{ color: isTie ? 'var(--color-tie)' : winnerIsT1 ? t1Color : t2Color }}
              >
                {isTie ? 'TIE' : g.winner_abbr}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
