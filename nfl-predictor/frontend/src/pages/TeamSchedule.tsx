import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import type { TeamScheduleResponse, TeamScheduleEntry } from '../api/types';
import TeamLogo from '../components/TeamLogo';
import Spinner from '../components/Spinner';
import { getTeamColors } from '../theme/teamColors';

const CURRENT_YEAR = new Date().getFullYear();
const SEASONS = Array.from({ length: 10 }, (_, i) => CURRENT_YEAR - i);

function difficultyBadge(d: TeamScheduleEntry['difficulty']) {
  if (!d) return null;
  const cls =
    d === 'hard'
      ? 'bg-red-500/20 text-red-400'
      : d === 'easy'
        ? 'bg-green-500/20 text-green-400'
        : 'bg-yellow-500/20 text-yellow-400';
  return (
    <span className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${cls}`}>
      {d}
    </span>
  );
}

function resultBadge(result: TeamScheduleEntry['result'], overtime: boolean) {
  if (!result) return <span className="text-text-muted text-xs">—</span>;
  const cls =
    result === 'W'
      ? 'text-green-400 font-bold'
      : result === 'L'
        ? 'text-red-400 font-bold'
        : 'text-yellow-400 font-bold';
  return (
    <span className={cls}>
      {result}{overtime ? ' (OT)' : ''}
    </span>
  );
}

export default function TeamSchedule() {
  const { abbr } = useParams<{ abbr: string }>();
  const [season, setSeason] = useState(CURRENT_YEAR);
  const [data, setData] = useState<TeamScheduleResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const teamAbbr = abbr?.toUpperCase() ?? '';
  const colors = getTeamColors(teamAbbr);

  useEffect(() => {
    if (!abbr) return;
    setLoading(true);
    setError(null);
    api.getTeamSchedule(abbr, season)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [abbr, season]);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-4 mb-6 animate-fade-up">
        <Link to={`/teams/${abbr}`} className="text-text-muted hover:text-text-primary transition-colors">
          ← Back
        </Link>
        <div className="flex items-center gap-3">
          <TeamLogo abbr={teamAbbr} size={40} />
          <div>
            <div className="font-display text-[11px] font-bold tracking-[0.2em] uppercase"
              style={{ color: colors.primary }}>
              Schedule
            </div>
            <h1 className="font-display text-2xl font-bold text-text-primary uppercase tracking-tight">
              {data?.team_name ?? teamAbbr}
            </h1>
          </div>
        </div>

        {/* Season selector */}
        <div className="ml-auto flex items-center gap-2">
          <label className="text-xs text-text-muted">Season</label>
          <select
            value={season}
            onChange={(e) => setSeason(Number(e.target.value))}
            className="bg-surface-800 border border-border rounded px-2 py-1 text-sm text-text-primary"
          >
            {SEASONS.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Record summary */}
      {data && (
        <div className="flex gap-4 mb-6">
          <div className="bg-surface-800 border border-border rounded-lg px-4 py-2 text-center">
            <div className="text-[10px] text-text-muted uppercase tracking-wider mb-0.5">Record</div>
            <div className="font-display text-lg font-bold text-text-primary">
              {data.wins}-{data.losses}{data.ties > 0 ? `-${data.ties}` : ''}
            </div>
          </div>
          <div className="bg-surface-800 border border-border rounded-lg px-4 py-2 text-center">
            <div className="text-[10px] text-text-muted uppercase tracking-wider mb-0.5">Games</div>
            <div className="font-display text-lg font-bold text-text-primary">
              {data.games.length}
            </div>
          </div>
          <div className="bg-surface-800 border border-border rounded-lg px-4 py-2 text-center">
            <div className="text-[10px] text-text-muted uppercase tracking-wider mb-0.5">Win %</div>
            <div className="font-display text-lg font-bold text-text-primary">
              {data.wins + data.losses > 0
                ? ((data.wins / (data.wins + data.losses)) * 100).toFixed(0) + '%'
                : '—'}
            </div>
          </div>
        </div>
      )}

      {/* Schedule table */}
      {loading && <Spinner />}
      {error && <p className="text-red-400 text-sm">{error}</p>}
      {data && !loading && (
        <div className="rounded-xl border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-850">
                <th className="text-left px-3 py-2 text-[10px] uppercase tracking-wider text-text-muted font-semibold w-8">Wk</th>
                <th className="text-left px-3 py-2 text-[10px] uppercase tracking-wider text-text-muted font-semibold">Date</th>
                <th className="text-left px-3 py-2 text-[10px] uppercase tracking-wider text-text-muted font-semibold">Opponent</th>
                <th className="text-center px-3 py-2 text-[10px] uppercase tracking-wider text-text-muted font-semibold">H/A</th>
                <th className="text-center px-3 py-2 text-[10px] uppercase tracking-wider text-text-muted font-semibold">Score</th>
                <th className="text-center px-3 py-2 text-[10px] uppercase tracking-wider text-text-muted font-semibold">Result</th>
              </tr>
            </thead>
            <tbody>
              {data.games.map((g, idx) => (
                <tr
                  key={g.game_id}
                  className={`border-b border-border/50 hover:bg-surface-800/50 transition-colors ${
                    idx % 2 === 0 ? 'bg-surface-900' : 'bg-surface-850'
                  }`}
                >
                  <td className="px-3 py-2.5 text-text-muted text-xs">{g.week}</td>
                  <td className="px-3 py-2.5 text-text-secondary text-xs">{g.date}</td>
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-2">
                      <TeamLogo abbr={g.opp_abbr} size={20} />
                      <div>
                        <span className="text-text-primary font-medium">{g.opp_abbr}</span>
                        <span className="text-text-muted text-xs ml-1">{g.opp_name}</span>
                      </div>
                      {g.result === null && difficultyBadge(g.difficulty)}
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${
                      g.is_home ? 'bg-accent/20 text-accent' : 'text-text-muted'
                    }`}>
                      {g.is_home ? 'HOME' : 'AWAY'}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-center text-text-secondary">
                    {g.team_score !== null && g.opp_score !== null
                      ? `${g.team_score} – ${g.opp_score}`
                      : <span className="text-text-muted">TBD</span>}
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    {resultBadge(g.result, g.overtime)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
