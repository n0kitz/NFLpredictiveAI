import { Link } from 'react-router-dom';
import type { Prediction } from '../api/types';
import { getTeamColors, teamBgTint } from '../theme/teamColors';
import TeamLogo from './TeamLogo';

interface Props {
  prediction: Prediction;
  homeAbbr: string;
  awayAbbr: string;
  compact?: boolean;
}

export default function PredictionCard({ prediction, homeAbbr, awayAbbr, compact }: Props) {
  const homeColors = getTeamColors(homeAbbr);
  const awayColors = getTeamColors(awayAbbr);
  const homePct = Math.round(prediction.home_win_probability * 100);
  const awayPct = 100 - homePct;
  const homeIsWinner = prediction.predicted_winner === prediction.home_team;

  return (
    <div className="group relative rounded-lg overflow-hidden bg-surface-800 border border-border hover:border-border-strong transition-all duration-300">
      {/* Probability bar — top edge */}
      <div className="flex h-1">
        <div
          className="transition-all duration-700 ease-out"
          style={{
            width: `${awayPct}%`,
            backgroundColor: awayColors.primary,
          }}
        />
        <div
          className="transition-all duration-700 ease-out"
          style={{
            width: `${homePct}%`,
            backgroundColor: homeColors.primary,
          }}
        />
      </div>

      <div className={compact ? 'p-4' : 'p-5'}>
        {/* Matchup row */}
        <div className="flex items-center gap-3">
          {/* Away team */}
          <Link to={`/teams/${awayAbbr}`} className="flex-1 group/t">
            <div
              className="rounded-md px-3 py-3 transition-all duration-200 group-hover/t:scale-[1.01]"
              style={{ backgroundColor: teamBgTint(awayAbbr, 0.07) }}
            >
              <div className="flex items-center gap-2.5">
                <TeamLogo abbr={awayAbbr} size={36} className="rounded-sm" />
                <div className="min-w-0">
                  <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium">
                    Away
                  </p>
                  <p className="text-sm font-semibold text-text-primary truncate leading-tight mt-0.5">
                    {prediction.away_team.split(' ').pop()}
                  </p>
                </div>
              </div>
              <p
                className="font-display text-3xl font-bold mt-3 tabular-nums"
                style={{ color: awayColors.primary }}
              >
                {awayPct}
                <span className="text-base font-semibold opacity-60">%</span>
              </p>
            </div>
          </Link>

          {/* VS divider */}
          <div className="flex flex-col items-center shrink-0">
            <span className="font-display text-text-muted text-xs font-semibold uppercase tracking-widest">
              @
            </span>
          </div>

          {/* Home team */}
          <Link to={`/teams/${homeAbbr}`} className="flex-1 group/t">
            <div
              className="rounded-md px-3 py-3 text-right transition-all duration-200 group-hover/t:scale-[1.01]"
              style={{ backgroundColor: teamBgTint(homeAbbr, 0.07) }}
            >
              <div className="flex items-center gap-2.5 justify-end">
                <div className="min-w-0 text-right">
                  <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium">
                    Home
                  </p>
                  <p className="text-sm font-semibold text-text-primary truncate leading-tight mt-0.5">
                    {prediction.home_team.split(' ').pop()}
                  </p>
                </div>
                <TeamLogo abbr={homeAbbr} size={36} className="rounded-sm" />
              </div>
              <p
                className="font-display text-3xl font-bold mt-3 tabular-nums"
                style={{ color: homeColors.primary }}
              >
                {homePct}
                <span className="text-base font-semibold opacity-60">%</span>
              </p>
            </div>
          </Link>
        </div>

        {/* Footer bar */}
        <div className="mt-3 pt-3 border-t border-border flex items-center justify-between">
          <span className="text-[11px] text-text-muted tracking-wide">
            Confidence:{' '}
            <span
              className={`font-semibold ${
                prediction.confidence === 'high'
                  ? 'text-conf-high'
                  : prediction.confidence === 'medium'
                    ? 'text-conf-medium'
                    : 'text-conf-low'
              }`}
            >
              {prediction.confidence.toUpperCase()}
            </span>
          </span>
          <span
            className="font-display text-sm font-semibold uppercase tracking-wide"
            style={{ color: homeIsWinner ? homeColors.primary : awayColors.primary }}
          >
            {prediction.predicted_winner.split(' ').pop()}
          </span>
        </div>
      </div>
    </div>
  );
}
