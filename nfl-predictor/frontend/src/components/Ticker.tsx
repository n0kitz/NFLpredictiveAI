import { useEffect, useState } from 'react';
import { api } from '../api/client';

interface TickerItem {
  text: string;
}

const FALLBACK: TickerItem[] = [
  { text: 'MODEL ONLINE' },
  { text: '9,400+ GAMES IN DATABASE' },
  { text: '35 SEASONS OF DATA · 1990–2025' },
  { text: '32 ACTIVE NFL TEAMS' },
  { text: 'RUN A CUSTOM PREDICTION AT /PREDICT' },
  { text: 'EXPLORE TEAM STATS AT /TEAMS' },
];

export default function Ticker() {
  const [items, setItems] = useState<TickerItem[]>(FALLBACK);

  useEffect(() => {
    async function load() {
      const next: TickerItem[] = [{ text: 'MODEL ONLINE' }];

      try {
        const h = await api.health();
        next.push({ text: `${h.total_games.toLocaleString()} GAMES IN DATABASE` });
      } catch { /* silent */ }

      try {
        const acc = await api.getAccuracy('2025');
        if (acc.total_games > 0) {
          next.push({
            text: `${(acc.accuracy * 100).toFixed(1)}% SEASON ACCURACY · ${acc.correct_predictions}/${acc.total_games} GAMES`,
          });
          const high = acc.by_confidence?.['high'];
          if (high && high.total > 0) {
            next.push({
              text: `HIGH CONF PICKS: ${((high.correct / high.total) * 100).toFixed(0)}% HIT RATE (${high.correct}/${high.total})`,
            });
          }
        }
      } catch { /* silent */ }

      try {
        const vp = await api.getValuePicks();
        for (const pick of vp.picks.slice(0, 3)) {
          const edgePp = Math.round(Math.abs(pick.edge) * 100);
          const side = pick.edge_side === 'home' ? pick.home_team : pick.away_team;
          next.push({
            text: `${pick.away_team} @ ${pick.home_team} · MODEL FAVORS ${side} +${edgePp}PP VS VEGAS`,
          });
        }
      } catch { /* silent */ }

      next.push({ text: '35 SEASONS OF NFL DATA · 1990–2025' });
      next.push({ text: 'CUSTOM PREDICTIONS AT /PREDICT' });

      if (next.length >= 4) setItems(next);
    }
    load();
  }, []);

  const loop = [...items, ...items, ...items];

  return (
    <div
      className="relative overflow-hidden border-b border-border bg-surface-800 select-none"
      style={{
        maskImage: 'linear-gradient(to right, transparent 0%, black 6%, black 94%, transparent 100%)',
        WebkitMaskImage: 'linear-gradient(to right, transparent 0%, black 6%, black 94%, transparent 100%)',
      }}
    >
      <div
        className="flex gap-10 whitespace-nowrap py-[7px] animate-ticker hover:[animation-play-state:paused] cursor-default"
        style={{ width: 'max-content' }}
      >
        {loop.map((item, i) => (
          <span key={i} className="font-display text-[11px] font-bold tracking-[0.12em] text-text-muted inline-flex items-center gap-2">
            <span className="text-accent text-[8px]">◆</span>
            {item.text}
          </span>
        ))}
      </div>
    </div>
  );
}
