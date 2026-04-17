import { Link } from 'react-router-dom';
import { useTeams } from '../hooks/useApi';
import Spinner from '../components/Spinner';
import TeamLogo from '../components/TeamLogo';
import type { Team } from '../api/types';

export default function Teams() {
  const { data, loading, error } = useTeams();

  if (loading) return <Spinner text="Loading teams..." />;
  if (error) return <div className="text-loss text-sm">{error}</div>;

  const grouped = groupTeams(data?.teams ?? []);

  return (
    <div>
      {/* Header */}
      <div className="mb-10 animate-fade-up">
        <div className="flex items-center gap-3 mb-3">
          <div className="h-px w-6 bg-accent" />
          <span className="font-display text-[11px] uppercase tracking-[0.2em] text-accent font-semibold">
            All 32 Teams
          </span>
        </div>
        <h1 className="font-display text-3xl font-bold text-text-primary uppercase tracking-tight">
          Teams
        </h1>
        <p className="text-text-secondary text-sm mt-2">
          Click any team for detailed stats, historical records, and recent performance.
        </p>
      </div>

      {(['AFC', 'NFC'] as const).map((conf) => (
        <div key={conf} className="mb-10 animate-fade-up stagger-1">
          {/* Conference header */}
          <div className="flex items-center gap-4 mb-5">
            <h2 className="font-display text-xl font-bold text-text-primary uppercase tracking-wider">
              {conf}
            </h2>
            <div className="flex-1 h-px bg-border" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            {['East', 'North', 'South', 'West'].map((div) => {
              const teams = grouped[`${conf} ${div}`] ?? [];
              return (
                <div
                  key={div}
                  className="rounded-lg border border-border bg-surface-850 overflow-hidden"
                >
                  {/* Division label */}
                  <div className="px-4 py-2.5 border-b border-border bg-surface-800/50">
                    <h3 className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em]">
                      {conf} {div}
                    </h3>
                  </div>

                  <div className="p-1.5">
                    {teams.map((t) => {
                      return (
                        <Link
                          key={t.team_id}
                          to={`/teams/${t.abbreviation}`}
                          className="flex items-center gap-3 rounded-md px-3 py-2.5 hover:bg-surface-700/60 transition-all group"
                        >
                          <TeamLogo abbr={t.abbreviation} size={36} className="rounded-sm transition-transform group-hover:scale-105" />
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-text-primary group-hover:text-accent transition-colors truncate">
                              {t.name}
                            </p>
                            <p className="text-[11px] text-text-muted">{t.city}</p>
                          </div>
                          <svg
                            className="w-3.5 h-3.5 text-text-muted ml-auto opacity-0 group-hover:opacity-100 transition-opacity"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth="2.5"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                          </svg>
                        </Link>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

function groupTeams(teams: Team[]): Record<string, Team[]> {
  const map: Record<string, Team[]> = {};
  for (const t of teams) {
    const key = `${t.conference} ${t.division}`;
    if (!map[key]) map[key] = [];
    map[key].push(t);
  }
  return map;
}
