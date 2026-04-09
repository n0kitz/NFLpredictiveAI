import { useState } from 'react';
import type { InlineFactor } from '../api/types';

const FACTOR_TYPES = [
  { value: 'better_defense', label: 'Better Defense' },
  { value: 'bad_defense', label: 'Bad Defense' },
  { value: 'better_offense', label: 'Better Offense' },
  { value: 'bad_offense', label: 'Bad Offense' },
  { value: 'better_qb', label: 'Better QB' },
  { value: 'qb_struggles', label: 'QB Struggles' },
  { value: 'turnover_prone', label: 'Turnover Prone' },
  { value: 'turnover_forcing', label: 'Turnover Forcing' },
  { value: 'not_efficient', label: 'Not Efficient' },
  { value: 'highly_efficient', label: 'Highly Efficient' },
  { value: 'injury_impact', label: 'Injury Impact' },
  { value: 'weather_impact', label: 'Weather Impact' },
  { value: 'coaching_advantage', label: 'Coaching Advantage' },
  { value: 'motivation_factor', label: 'Motivation Factor' },
  { value: 'custom', label: 'Custom' },
];

interface Props {
  homeAbbr: string;
  awayAbbr: string;
  factors: InlineFactor[];
  onChange: (factors: InlineFactor[]) => void;
}

export default function FactorPanel({ homeAbbr, awayAbbr, factors, onChange }: Props) {
  const [expanded, setExpanded] = useState(false);

  function addFactor() {
    onChange([...factors, { factor_type: 'custom', team: 'home', impact_rating: 0 }]);
    setExpanded(true);
  }

  function removeFactor(idx: number) {
    onChange(factors.filter((_, i) => i !== idx));
  }

  function updateFactor(idx: number, patch: Partial<InlineFactor>) {
    onChange(factors.map((f, i) => (i === idx ? { ...f, ...patch } : f)));
  }

  return (
    <div className="rounded-lg border border-border bg-surface-850 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-5 py-3 flex items-center justify-between hover:bg-surface-800/50 transition-colors"
      >
        <span className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em]">
          Game Factors {factors.length > 0 && `(${factors.length})`}
        </span>
        <svg
          className={`w-4 h-4 text-text-muted transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="px-5 pb-5 space-y-3 border-t border-border pt-4">
          {factors.map((f, idx) => (
            <div key={idx} className="flex items-center gap-3 flex-wrap">
              {/* Factor type */}
              <select
                value={f.factor_type}
                onChange={(e) => updateFactor(idx, { factor_type: e.target.value })}
                className="bg-surface-700 border border-border rounded-md px-3 py-1.5 text-sm text-text-primary flex-1 min-w-[160px]"
              >
                {FACTOR_TYPES.map((ft) => (
                  <option key={ft.value} value={ft.value}>{ft.label}</option>
                ))}
              </select>

              {/* Team assignment */}
              <div className="flex rounded-md overflow-hidden border border-border">
                <button
                  onClick={() => updateFactor(idx, { team: 'home' })}
                  className={`px-3 py-1.5 text-xs font-display font-medium uppercase tracking-wider transition-colors ${
                    f.team === 'home'
                      ? 'bg-accent text-surface-900'
                      : 'bg-surface-700 text-text-muted hover:text-text-secondary'
                  }`}
                >
                  {homeAbbr}
                </button>
                <button
                  onClick={() => updateFactor(idx, { team: 'away' })}
                  className={`px-3 py-1.5 text-xs font-display font-medium uppercase tracking-wider transition-colors ${
                    f.team === 'away'
                      ? 'bg-accent text-surface-900'
                      : 'bg-surface-700 text-text-muted hover:text-text-secondary'
                  }`}
                >
                  {awayAbbr}
                </button>
              </div>

              {/* Impact slider */}
              <div className="flex items-center gap-2 min-w-[140px]">
                <input
                  type="range"
                  min="-5"
                  max="5"
                  value={f.impact_rating}
                  onChange={(e) => updateFactor(idx, { impact_rating: Number(e.target.value) })}
                  className="flex-1 accent-accent"
                />
                <span className={`text-xs font-display font-bold tabular-nums w-6 text-center ${
                  f.impact_rating > 0 ? 'text-win' : f.impact_rating < 0 ? 'text-loss' : 'text-text-muted'
                }`}>
                  {f.impact_rating > 0 ? '+' : ''}{f.impact_rating}
                </span>
              </div>

              {/* Remove */}
              <button
                onClick={() => removeFactor(idx)}
                className="text-text-muted hover:text-loss transition-colors p-1"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          ))}

          <button
            onClick={addFactor}
            className="text-xs font-display uppercase tracking-wider text-accent hover:text-accent-hover transition-colors font-semibold"
          >
            + Add Factor
          </button>
        </div>
      )}
    </div>
  );
}
