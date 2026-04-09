import { useState, useEffect } from 'react';
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts';
import { api } from '../api/client';
import type { TeamSeasonStats } from '../api/types';
import Spinner from './Spinner';

interface Props {
  teamAbbr: string;
  primaryColor: string;
  secondaryColor: string;
}

interface SeasonData {
  season: number;
  winPct: number;
  ppg: number;
  papg: number;
  homeWinPct: number;
  awayWinPct: number;
}

export default function TrendChart({ teamAbbr, primaryColor, secondaryColor }: Props) {
  const [data, setData] = useState<SeasonData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function load() {
      const currentYear = new Date().getFullYear();
      const years = Array.from({ length: 10 }, (_, i) => currentYear - 9 + i);
      const results: SeasonData[] = [];

      const settled = await Promise.allSettled(
        years.map((y) => api.getTeamSeason(teamAbbr, y)),
      );

      settled.forEach((res) => {
        if (res.status === 'fulfilled') {
          const s: TeamSeasonStats = res.value;
          const hGames = s.home_wins + s.home_losses;
          const aGames = s.away_wins + s.away_losses;
          results.push({
            season: s.season,
            winPct: Math.round(s.win_percentage * 1000) / 10,
            ppg: +(s.points_for / s.games_played).toFixed(1),
            papg: +(s.points_against / s.games_played).toFixed(1),
            homeWinPct: hGames > 0 ? Math.round((s.home_wins / hGames) * 1000) / 10 : 0,
            awayWinPct: aGames > 0 ? Math.round((s.away_wins / aGames) * 1000) / 10 : 0,
          });
        }
      });

      results.sort((a, b) => a.season - b.season);
      if (!cancelled) {
        setData(results);
        setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [teamAbbr]);

  if (loading) return <Spinner text="Loading trends..." />;
  if (data.length === 0) return null;

  const tooltipStyle = {
    backgroundColor: 'var(--color-surface-800)',
    border: '1px solid var(--color-border)',
    borderRadius: '6px',
    fontSize: '12px',
  };

  const axisStyle = { fontSize: 11, fill: 'var(--color-text-muted)', fontFamily: 'Oswald, sans-serif' };

  return (
    <div className="space-y-6 rounded-xl border border-border bg-surface-850 p-5 animate-fade-up stagger-2">
      <h2 className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em]">
        10-Season Trends
      </h2>

      {/* Win % */}
      <div>
        <p className="text-[10px] text-text-muted uppercase tracking-wider font-display font-medium mb-2">
          Win % by Season
        </p>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis dataKey="season" tick={axisStyle} />
            <YAxis domain={[0, 100]} tick={axisStyle} tickFormatter={(v) => `${v}%`} />
            <Tooltip contentStyle={tooltipStyle} formatter={(v) => `${v}%`} />
            <Line
              type="monotone" dataKey="winPct" name="Win %"
              stroke={primaryColor} strokeWidth={2.5} dot={{ r: 3, fill: primaryColor }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* PPG Scored vs Allowed */}
      <div>
        <p className="text-[10px] text-text-muted uppercase tracking-wider font-display font-medium mb-2">
          PPG Scored vs Allowed
        </p>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis dataKey="season" tick={axisStyle} />
            <YAxis tick={axisStyle} />
            <Tooltip contentStyle={tooltipStyle} />
            <Legend
              wrapperStyle={{ fontSize: '11px', fontFamily: 'Oswald, sans-serif' }}
            />
            <Line
              type="monotone" dataKey="ppg" name="Scored"
              stroke="var(--color-win)" strokeWidth={2} dot={{ r: 3 }}
            />
            <Line
              type="monotone" dataKey="papg" name="Allowed"
              stroke="var(--color-loss)" strokeWidth={2} dot={{ r: 3 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Home vs Away Win% */}
      <div>
        <p className="text-[10px] text-text-muted uppercase tracking-wider font-display font-medium mb-2">
          Home vs Away Win%
        </p>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis dataKey="season" tick={axisStyle} />
            <YAxis domain={[0, 100]} tick={axisStyle} tickFormatter={(v) => `${v}%`} />
            <Tooltip contentStyle={tooltipStyle} formatter={(v) => `${v}%`} />
            <Legend
              wrapperStyle={{ fontSize: '11px', fontFamily: 'Oswald, sans-serif' }}
            />
            <Bar dataKey="homeWinPct" name="Home" fill={primaryColor} radius={[2, 2, 0, 0]} />
            <Bar dataKey="awayWinPct" name="Away" fill={secondaryColor} radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
