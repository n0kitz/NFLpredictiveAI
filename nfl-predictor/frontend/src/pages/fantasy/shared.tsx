import { useState } from 'react';
import type { ReactNode } from 'react';
import type { FantasyProjection } from '../../api/types';
import { POSITIONS, posColor, type PositionFilter } from './helpers';

// Small presentational components shared across the Fantasy tabs.
// Pure helpers (posColor, matchupColor, POSITIONS, PositionFilter) live in helpers.ts.

export function PosBadge({ pos }: { pos: string | null }) {
  return (
    <span
      className="text-[9px] font-display font-bold uppercase tracking-wider px-1.5 py-0.5 rounded"
      style={{ backgroundColor: `${posColor(pos)}22`, color: posColor(pos) }}
    >
      {pos ?? '—'}
    </span>
  );
}

// Inline tooltip for matchup score / confidence
export function MTooltip({ text, children }: { text: string; children: ReactNode }) {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-block" onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 z-50 w-64 rounded-lg border border-border bg-surface-800 px-2.5 py-2 text-[10px] text-text-secondary shadow-xl pointer-events-none" style={{ whiteSpace: 'normal' }}>
          {text}
        </span>
      )}
    </span>
  );
}

export function ConfBadge({ conf }: { conf: string }) {
  const style = conf === 'high' ? 'bg-win/15 text-win' : conf === 'low' ? 'bg-loss/15 text-loss' : 'bg-yellow-500/15 text-yellow-400';
  return <span className={`text-[9px] font-display font-bold uppercase px-1.5 py-0.5 rounded ${style}`}>{conf}</span>;
}

export function MLBadge({ projection }: { projection: FantasyProjection }) {
  const contribs = projection.contributions ?? [];
  const top = contribs.slice(0, 3);
  const tip = top.length === 0
    ? `ML model ${projection.model_version ?? ''} — floor ${projection.floor_ppr?.toFixed(1) ?? '—'} / ceiling ${projection.ceiling_ppr?.toFixed(1) ?? '—'} PPR`
    : `ML ${projection.model_version ?? ''} top drivers: ${top.map((c) => `${c.direction === 'up' ? '↑' : c.direction === 'down' ? '↓' : '·'}${c.label} ${c.shap_value >= 0 ? '+' : ''}${c.shap_value.toFixed(2)}`).join(' · ')}`;
  return (
    <MTooltip text={tip}>
      <span className="text-[9px] font-display font-bold uppercase px-1.5 py-0.5 rounded bg-accent/15 text-accent">
        ML
      </span>
    </MTooltip>
  );
}

export function Headshot({ url, name }: { url: string | null; name: string }) {
  return url ? (
    <img
      src={url}
      alt={name}
      className="w-8 h-8 rounded-full object-cover bg-surface-700 shrink-0"
      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
    />
  ) : (
    <div className="w-8 h-8 rounded-full bg-surface-700 shrink-0 flex items-center justify-center">
      <span className="text-[9px] text-text-muted font-bold">{name.slice(0, 2).toUpperCase()}</span>
    </div>
  );
}

export function PositionFilterBar({
  value, onChange,
}: { value: PositionFilter; onChange: (p: PositionFilter) => void }) {
  return (
    <div className="flex gap-1">
      {POSITIONS.map((p) => (
        <button
          key={p}
          onClick={() => onChange(p)}
          className={`px-3 py-1 rounded text-[11px] font-display font-semibold uppercase tracking-wide transition-colors ${
            value === p
              ? 'bg-accent text-surface-900'
              : 'bg-surface-800 text-text-muted hover:text-text-secondary border border-border'
          }`}
        >
          {p}
        </button>
      ))}
    </div>
  );
}

export function ScoringToggle({
  value, onChange,
}: { value: string; onChange: (s: string) => void }) {
  return (
    <div className="flex gap-1">
      {(['ppr', 'standard'] as const).map((s) => (
        <button
          key={s}
          onClick={() => onChange(s)}
          className={`px-3 py-1 rounded text-[11px] font-display font-semibold uppercase tracking-wide transition-colors ${
            value === s
              ? 'bg-accent text-surface-900'
              : 'bg-surface-800 text-text-muted hover:text-text-secondary border border-border'
          }`}
        >
          {s === 'ppr' ? 'PPR' : 'STD'}
        </button>
      ))}
    </div>
  );
}
