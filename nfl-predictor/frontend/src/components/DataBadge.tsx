import { useState } from 'react';

export type DataSource =
  | 'espn'
  | 'pfr'
  | 'nfl-data-py'
  | 'open-meteo'
  | 'odds-api'
  | 'calculated'
  | 'ml-model';

interface Config {
  label: string;
  tooltip: string;
  color: string;
  bg: string;
}

const SOURCE: Record<DataSource, Config> = {
  'espn':        { label: 'ESPN',     color: 'text-red-400',    bg: 'bg-red-500/10',    tooltip: 'Scraped from ESPN public API (injuries, rosters, player data)' },
  'pfr':         { label: 'PFR',      color: 'text-yellow-400', bg: 'bg-yellow-500/10', tooltip: 'Pro Football Reference — historical game data (1990–2025)' },
  'nfl-data-py': { label: 'nfl-data', color: 'text-blue-400',   bg: 'bg-blue-500/10',   tooltip: 'nfl_data_py — play-by-play, QB EPA, advanced team stats' },
  'open-meteo':  { label: 'Weather',  color: 'text-cyan-400',   bg: 'bg-cyan-500/10',   tooltip: 'Open-Meteo forecast API (no auth) — temperature, wind, precipitation' },
  'odds-api':    { label: 'Vegas',    color: 'text-green-400',  bg: 'bg-green-500/10',  tooltip: 'The Odds API — Vegas lines (display-only, never used in predictions)' },
  'calculated':  { label: 'Calc',     color: 'text-text-muted', bg: 'bg-surface-700',   tooltip: 'Derived from 35 seasons of historical game data in the local database' },
  'ml-model':    { label: 'GBM',      color: 'text-accent',     bg: 'bg-accent/10',     tooltip: 'Gradient Boosting Machine — 35 features, 67.2% OOS accuracy (2023–2024)' },
};

export default function DataBadge({ source }: { source: DataSource }) {
  const cfg = SOURCE[source];
  const [show, setShow] = useState(false);

  return (
    <span className="relative inline-block">
      <span
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[9px] font-display font-semibold uppercase tracking-wider cursor-default select-none ${cfg.bg} ${cfg.color}`}
      >
        {cfg.label}
      </span>
      {show && (
        <span
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 rounded-lg border border-border bg-surface-800 px-2.5 py-1.5 text-[10px] text-text-secondary shadow-xl pointer-events-none"
          style={{ width: 220, whiteSpace: 'normal', textAlign: 'center' }}
        >
          {cfg.tooltip}
        </span>
      )}
    </span>
  );
}
