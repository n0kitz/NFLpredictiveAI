import { useMemo } from 'react';
import type { Team } from '../api/types';
import { getTeamColors, teamBgTint } from '../theme/teamColors';

interface Props {
  teams: Team[];
  value: string;
  onChange: (abbr: string) => void;
  label: string;
  excludeAbbr?: string;
}

interface DivisionGroup {
  conference: string;
  division: string;
  teams: Team[];
}

export default function TeamSelector({ teams, value, onChange, label, excludeAbbr }: Props) {
  const grouped = useMemo(() => {
    const groups: DivisionGroup[] = [];
    const map = new Map<string, Team[]>();

    for (const t of teams) {
      if (t.abbreviation === excludeAbbr) continue;
      const key = `${t.conference} ${t.division}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(t);
    }

    for (const [key, divTeams] of map) {
      const [conference, division] = key.split(' ');
      groups.push({ conference, division, teams: divTeams });
    }

    groups.sort((a, b) => a.conference.localeCompare(b.conference) || a.division.localeCompare(b.division));
    return groups;
  }, [teams, excludeAbbr]);

  const selected = value ? getTeamColors(value) : null;

  return (
    <div>
      <label className="block font-display text-[11px] uppercase tracking-[0.15em] text-text-muted mb-2 font-semibold">
        {label}
      </label>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-md bg-surface-700 border-2 px-4 py-3.5 text-text-primary text-sm font-medium
                     focus:outline-none appearance-none cursor-pointer transition-all"
          style={{
            borderColor: selected ? selected.primary : 'var(--color-border-strong)',
            backgroundColor: value ? teamBgTint(value, 0.05) : undefined,
          }}
        >
          <option value="">Select a team...</option>
          {grouped.map((g) => (
            <optgroup key={`${g.conference} ${g.division}`} label={`${g.conference} ${g.division}`}>
              {g.teams.map((t) => (
                <option key={t.abbreviation} value={t.abbreviation}>
                  {t.city} {t.name}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        {/* Chevron */}
        <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-4">
          <svg className="w-4 h-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
    </div>
  );
}
