import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { Prediction } from '../api/types';
import { useAccuracy } from '../hooks/useApi';
import PredictionCard from '../components/PredictionCard';
import Spinner from '../components/Spinner';
import ValuePicksPanel from '../components/ValuePicksPanel';

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

export default function Dashboard() {
  const [matchups, setMatchups] = useState<MatchupResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { data: accuracy } = useAccuracy('2025');

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const results = await Promise.all(
          FEATURED_MATCHUPS.map(async ([away, home]) => {
            const prediction = await api.predictGet(away, home);
            return { prediction, homeAbbr: home, awayAbbr: away };
          }),
        );
        if (!cancelled) {
          setMatchups(results);
          setLoading(false);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load');
          setLoading(false);
        }
      }
    }

    load();
    return () => { cancelled = true; };
  }, []);

  return (
    <div>
      {/* Hero section — broadcast opening */}
      <div className="relative rounded-xl overflow-hidden mb-10 animate-fade-up">
        {/* Background layers */}
        <div className="absolute inset-0 bg-gradient-to-br from-surface-700 via-surface-800 to-surface-900" />
        <div className="absolute inset-0 field-lines opacity-50" />
        <div className="absolute top-0 right-0 w-96 h-96 bg-accent/5 rounded-full blur-[100px] -translate-y-1/2 translate-x-1/3" />

        <div className="relative px-8 py-12 md:px-12 md:py-16">
          <div className="flex items-start justify-between gap-8">
            <div className="max-w-xl">
              <div className="flex items-center gap-3 mb-4">
                <div className="h-px w-8 bg-accent" />
                <span className="font-display text-[11px] uppercase tracking-[0.2em] text-accent font-semibold">
                  Powered by Data
                </span>
              </div>

              <h1 className="font-display text-4xl md:text-5xl font-bold text-text-primary uppercase leading-[1.1] tracking-tight">
                Game
                <br />
                Predictions
              </h1>

              <p className="text-text-secondary text-sm leading-relaxed mt-4 max-w-md">
                Win probabilities calculated from 35 years of NFL history — weighted
                metrics for strength, form, head-to-head, and home advantage.
              </p>

              <div className="flex gap-3 mt-8">
                <Link
                  to="/predict"
                  className="px-6 py-2.5 rounded-md bg-accent text-surface-900 font-display text-sm font-semibold uppercase tracking-wider hover:bg-accent-hover transition-colors"
                >
                  Run Prediction
                </Link>
                <Link
                  to="/teams"
                  className="px-6 py-2.5 rounded-md border border-border-strong text-text-secondary font-display text-sm font-medium uppercase tracking-wider hover:border-text-muted hover:text-text-primary transition-colors"
                >
                  Browse Teams
                </Link>
              </div>
            </div>

            {/* Stats callout */}
            <div className="hidden lg:flex flex-col gap-6 text-right">
              {[
                { value: '9,400+', label: 'Games Analyzed' },
                { value: '35', label: 'Seasons of Data' },
                { value: '32', label: 'Active Teams' },
              ].map((stat) => (
                <div key={stat.label}>
                  <p className="font-display text-3xl font-bold text-text-primary tabular-nums">
                    {stat.value}
                  </p>
                  <p className="text-[11px] text-text-muted uppercase tracking-widest font-medium mt-0.5">
                    {stat.label}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Model accuracy bar */}
      {accuracy && accuracy.total_games > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-10 animate-fade-up stagger-1">
          <div className="rounded-lg bg-surface-850 border border-border p-4">
            <p className="font-display text-[10px] uppercase tracking-[0.2em] text-text-muted font-semibold mb-1">
              Model Accuracy
            </p>
            <p className="font-display text-3xl font-bold text-win tabular-nums">
              {(accuracy.accuracy * 100).toFixed(1)}%
            </p>
            <p className="text-[11px] text-text-muted mt-1">
              {accuracy.correct_predictions}/{accuracy.total_games} games
            </p>
          </div>
          {Object.entries(accuracy.calibration)
            .filter(([, v]) => v.total > 0)
            .slice(0, 3)
            .map(([bucket, v]) => (
              <div key={bucket} className="rounded-lg bg-surface-850 border border-border p-4">
                <p className="font-display text-[10px] uppercase tracking-[0.2em] text-text-muted font-semibold mb-1">
                  {bucket} picks
                </p>
                <p className="font-display text-2xl font-bold text-text-primary tabular-nums">
                  {v.total > 0 ? ((v.correct / v.total) * 100).toFixed(0) : 0}%
                </p>
                <p className="text-[11px] text-text-muted mt-1">
                  {v.correct}/{v.total} correct
                </p>
              </div>
            ))}
        </div>
      )}

      {/* Section header */}
      <div className="flex items-center gap-4 mb-6 animate-fade-up stagger-1">
        <h2 className="font-display text-lg font-semibold text-text-primary uppercase tracking-wider">
          Featured Matchups
        </h2>
        <div className="flex-1 h-px bg-border" />
        <Link
          to="/predict"
          className="text-[11px] font-display uppercase tracking-widest text-accent hover:text-accent-hover font-semibold transition-colors"
        >
          Custom Matchup &rarr;
        </Link>
      </div>

      {loading && <Spinner text="Loading predictions..." />}
      {error && (
        <div className="rounded-md bg-loss/10 border border-loss/20 px-5 py-3 text-sm text-loss animate-fade-in">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {matchups.map((m, i) => (
          <div key={`${m.awayAbbr}-${m.homeAbbr}`} className={`animate-fade-up stagger-${Math.min(i + 2, 8)}`}>
            <PredictionCard
              prediction={m.prediction}
              homeAbbr={m.homeAbbr}
              awayAbbr={m.awayAbbr}
              compact
            />
          </div>
        ))}
      </div>

      {/* ── Value Picks ─────────────────────────────────── */}
      <div className="mt-10 animate-fade-up stagger-8">
        <ValuePicksPanel />
      </div>
    </div>
  );
}
