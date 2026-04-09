import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { api } from '../api/client';
import type { Game } from '../api/types';
import Spinner from '../components/Spinner';
import { getTeamColors } from '../theme/teamColors';

const YEARS = Array.from({ length: 2025 - 1990 + 1 }, (_, i) => 2025 - i);

interface Standing {
  abbr: string;
  name: string;
  conference: string;
  division: string;
  wins: number;
  losses: number;
  ties: number;
  pf: number;
  pa: number;
  winPct: number;
}

export default function Season() {
  const { year: paramYear } = useParams<{ year?: string }>();
  const navigate = useNavigate();
  const [year, setYear] = useState(paramYear ? Number(paramYear) : 2025);
  const [games, setGames] = useState<Game[]>([]);
  const [standings, setStandings] = useState<Standing[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'standings' | 'games'>('standings');

  useEffect(() => {
    if (paramYear) setYear(Number(paramYear));
  }, [paramYear]);

  useEffect(() => {
    navigate(`/seasons/${year}`, { replace: true });
  }, [year, navigate]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function load() {
      try {
        const [gameData, teamData] = await Promise.all([
          api.getGames(year),
          api.getTeams(),
        ]);

        if (cancelled) return;
        const gs = gameData.games;
        setGames(gs);

        // Compute standings from games
        const teamMap = new Map<number, Standing>();
        for (const t of teamData.teams) {
          teamMap.set(t.team_id, {
            abbr: t.abbreviation,
            name: `${t.city} ${t.name}`,
            conference: t.conference,
            division: t.division,
            wins: 0, losses: 0, ties: 0, pf: 0, pa: 0, winPct: 0,
          });
        }

        for (const g of gs) {
          if (g.home_score === null || g.away_score === null) continue;
          if (g.game_type !== 'regular') continue;

          const home = teamMap.get(g.home_team_id);
          const away = teamMap.get(g.away_team_id);
          if (!home || !away) continue;

          home.pf += g.home_score;
          home.pa += g.away_score;
          away.pf += g.away_score;
          away.pa += g.home_score;

          if (g.winner_id === g.home_team_id) {
            home.wins++;
            away.losses++;
          } else if (g.winner_id === g.away_team_id) {
            away.wins++;
            home.losses++;
          } else {
            home.ties++;
            away.ties++;
          }
        }

        const st = Array.from(teamMap.values()).filter((s) => s.wins + s.losses + s.ties > 0);
        st.forEach((s) => {
          const total = s.wins + s.losses + s.ties;
          s.winPct = total > 0 ? (s.wins + s.ties * 0.5) / total : 0;
        });
        st.sort((a, b) => b.winPct - a.winPct);
        setStandings(st);
      } catch {
        // ignore
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [year]);

  // Group games by week
  const weeks = new Map<string, Game[]>();
  for (const g of games) {
    const key = g.week;
    if (!weeks.has(key)) weeks.set(key, []);
    weeks.get(key)!.push(g);
  }

  // Group standings by division
  const divisions = new Map<string, Standing[]>();
  for (const s of standings) {
    const key = `${s.conference} ${s.division}`;
    if (!divisions.has(key)) divisions.set(key, []);
    divisions.get(key)!.push(s);
  }
  // Sort divisions alphabetically
  const sortedDivisions = Array.from(divisions.entries()).sort(([a], [b]) => a.localeCompare(b));

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-5 mb-8 animate-fade-up">
        <div>
          <div className="flex items-center gap-3 mb-3">
            <div className="h-px w-6 bg-accent" />
            <span className="font-display text-[11px] uppercase tracking-[0.2em] text-accent font-semibold">
              Season Browser
            </span>
          </div>
          <h1 className="font-display text-3xl font-bold text-text-primary uppercase tracking-tight">
            {year} Season
          </h1>
        </div>
        <select
          value={year}
          onChange={(e) => setYear(Number(e.target.value))}
          className="bg-surface-700 border border-border rounded-md px-4 py-2 text-sm text-text-primary font-display ml-auto"
        >
          {YEARS.map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-border animate-fade-up stagger-1">
        {(['standings', 'games'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-5 py-2.5 font-display text-sm font-medium uppercase tracking-wider transition-colors relative ${
              tab === t ? 'text-accent' : 'text-text-muted hover:text-text-secondary'
            }`}
          >
            {t}
            {tab === t && <span className="absolute bottom-0 left-2 right-2 h-[2px] bg-accent rounded-full" />}
          </button>
        ))}
      </div>

      {loading && <Spinner text="Loading season data..." />}

      {/* Standings */}
      {!loading && tab === 'standings' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-fade-up stagger-2">
          {sortedDivisions.map(([divName, teams]) => (
            <div key={divName} className="rounded-lg border border-border bg-surface-850 overflow-hidden">
              <div className="px-4 py-2.5 bg-surface-800/50 border-b border-border">
                <span className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.15em]">
                  {divName}
                </span>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[10px] text-text-muted uppercase tracking-wider font-display">
                    <th className="text-left px-4 py-2">Team</th>
                    <th className="text-center px-2 py-2">W</th>
                    <th className="text-center px-2 py-2">L</th>
                    <th className="text-center px-2 py-2">T</th>
                    <th className="text-center px-2 py-2">Pct</th>
                    <th className="text-center px-2 py-2">PF</th>
                    <th className="text-center px-2 py-2">PA</th>
                    <th className="text-center px-2 py-2">Diff</th>
                  </tr>
                </thead>
                <tbody>
                  {teams.sort((a, b) => b.winPct - a.winPct).map((s) => {
                    const diff = s.pf - s.pa;
                    const tc = getTeamColors(s.abbr);
                    return (
                      <tr key={s.abbr} className="border-t border-border hover:bg-surface-700/30 transition-colors">
                        <td className="px-4 py-2">
                          <Link to={`/teams/${s.abbr}`} className="flex items-center gap-2 hover:text-accent transition-colors">
                            <span className="w-6 h-6 rounded-sm flex items-center justify-center text-[9px] font-display font-bold text-white" style={{ backgroundColor: tc.primary }}>
                              {s.abbr}
                            </span>
                            <span className="font-medium text-text-primary">{s.abbr}</span>
                          </Link>
                        </td>
                        <td className="text-center px-2 py-2 tabular-nums text-text-primary">{s.wins}</td>
                        <td className="text-center px-2 py-2 tabular-nums text-text-primary">{s.losses}</td>
                        <td className="text-center px-2 py-2 tabular-nums text-text-muted">{s.ties || '-'}</td>
                        <td className="text-center px-2 py-2 tabular-nums font-semibold" style={{ color: s.winPct >= 0.5 ? 'var(--color-win)' : 'var(--color-loss)' }}>
                          .{(s.winPct * 1000).toFixed(0).padStart(3, '0')}
                        </td>
                        <td className="text-center px-2 py-2 tabular-nums text-text-secondary">{s.pf}</td>
                        <td className="text-center px-2 py-2 tabular-nums text-text-secondary">{s.pa}</td>
                        <td className={`text-center px-2 py-2 tabular-nums font-medium ${diff > 0 ? 'text-win' : diff < 0 ? 'text-loss' : 'text-text-muted'}`}>
                          {diff > 0 ? '+' : ''}{diff}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}

      {/* Games by week */}
      {!loading && tab === 'games' && (
        <div className="space-y-4 animate-fade-up stagger-2">
          {Array.from(weeks.entries()).map(([week, weekGames]) => (
            <WeekAccordion key={week} week={week} games={weekGames} />
          ))}
        </div>
      )}
    </div>
  );
}

function WeekAccordion({ week, games }: { week: string; games: Game[] }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-lg border border-border bg-surface-850 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-5 py-3 flex items-center justify-between hover:bg-surface-800/50 transition-colors"
      >
        <span className="font-display text-sm font-semibold text-text-primary uppercase tracking-wider">
          Week {week}
        </span>
        <span className="flex items-center gap-3">
          <span className="text-xs text-text-muted">{games.length} games</span>
          <svg className={`w-4 h-4 text-text-muted transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </span>
      </button>
      {open && (
        <div className="border-t border-border divide-y divide-border">
          {games.map((g) => {
            const hasScore = g.home_score !== null;
            return (
              <div key={g.game_id} className="flex items-center px-5 py-2.5 text-sm hover:bg-surface-700/30 transition-colors">
                <span className="text-text-muted w-24 text-xs tabular-nums">{g.date}</span>
                <Link to={`/teams/${g.away_abbr}`} className="font-medium text-text-secondary hover:text-accent transition-colors w-12">
                  {g.away_abbr}
                </Link>
                {hasScore ? (
                  <span className="tabular-nums text-text-primary font-semibold w-16 text-center">
                    {g.away_score}&ndash;{g.home_score}
                  </span>
                ) : (
                  <span className="text-text-muted w-16 text-center text-xs">TBD</span>
                )}
                <Link to={`/teams/${g.home_abbr}`} className="font-medium text-text-secondary hover:text-accent transition-colors w-12">
                  {g.home_abbr}
                </Link>
                {g.winner_abbr && (
                  <span className="ml-auto text-xs font-display font-bold text-win">{g.winner_abbr} W</span>
                )}
                {g.overtime && <span className="ml-2 text-[10px] text-text-muted font-display">OT</span>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
