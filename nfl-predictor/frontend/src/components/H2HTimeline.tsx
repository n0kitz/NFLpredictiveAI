import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer } from 'recharts';
import type { H2H } from '../api/types';

interface Props {
  h2h: H2H;
  t1: string;
  t2: string;
  c1: string;
  c2: string;
}

export default function H2HTimeline({ h2h, t1, t2, c1, c2 }: Props) {
  const games = [...h2h.games].reverse().slice(0, 10);
  if (!games.length) return null;

  const data = games.map((g) => {
    const t1IsHome = g.home_abbr === t1;
    return {
      date: g.date?.slice(0, 4) ?? '',
      label: `${g.away_abbr}@${g.home_abbr} ${g.date?.slice(0, 4)}`,
      t1: t1IsHome ? (g.home_score ?? 0) : (g.away_score ?? 0),
      t2: t1IsHome ? (g.away_score ?? 0) : (g.home_score ?? 0),
      winner: g.winner_abbr,
    };
  });

  return (
    <div className="rounded-lg border border-border bg-surface-850 p-5">
      <h3 className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em] mb-4">
        H2H Score Timeline · Last {games.length} Meetings
      </h3>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} barCategoryGap="30%" barGap={2} margin={{ left: -10, right: 10, top: 0, bottom: 0 }}>
          <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--color-text-muted)' }} />
          <YAxis tick={{ fontSize: 9, fill: 'var(--color-text-muted)' }} />
          <Tooltip
            contentStyle={{ background: 'var(--color-surface-800)', border: '1px solid var(--color-border)', borderRadius: 8, fontSize: 11 }}
            formatter={(val, name) => [val as number, (name as string) === 't1' ? t1 : t2]}
            labelFormatter={(label) => {
              const g = data.find((d) => d.date === label);
              return g?.label ?? label;
            }}
          />
          <Bar dataKey="t1" name={t1} radius={[2, 2, 0, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={c1} opacity={d.winner === t1 ? 1 : 0.45} />
            ))}
          </Bar>
          <Bar dataKey="t2" name={t2} radius={[2, 2, 0, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={c2} opacity={d.winner === t2 ? 1 : 0.45} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="text-[9px] text-text-muted mt-1 text-center">Full opacity = winner</p>
    </div>
  );
}
