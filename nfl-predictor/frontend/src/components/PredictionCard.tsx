import { Link } from 'react-router-dom';
import type { Prediction, VegasContext, ConditionsSummary } from '../api/types';
import { getTeamColors, teamBgTint } from '../theme/teamColors';
import TeamLogo from './TeamLogo';

function VegasPanel({ vegas }: { vegas: VegasContext }) {
  if (!vegas.home_implied_prob && !vegas.spread) return null;
  return (
    <div className="mt-3 pt-3 border-t border-border">
      <p className="text-[10px] uppercase tracking-[0.15em] text-text-muted font-semibold mb-2">Vegas Lines</p>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {vegas.spread !== null && (
          <span className="text-text-secondary">Spread: <span className="text-text-primary font-semibold">{vegas.spread > 0 ? '+' : ''}{vegas.spread}</span></span>
        )}
        {vegas.over_under !== null && (
          <span className="text-text-secondary">O/U: <span className="text-text-primary font-semibold">{vegas.over_under}</span></span>
        )}
        {vegas.home_implied_prob !== null && (
          <span className="text-text-secondary">Home implied: <span className="text-text-primary font-semibold">{Math.round(vegas.home_implied_prob * 100)}%</span></span>
        )}
      </div>
    </div>
  );
}

function ConditionsPanel({ conditions, homeAbbr, awayAbbr }: { conditions: ConditionsSummary; homeAbbr: string; awayAbbr: string }) {
  const hasInjuries = conditions.home_injuries.length > 0 || conditions.away_injuries.length > 0;
  const weather = conditions.weather;
  if (!hasInjuries && !weather) return null;
  return (
    <div className="mt-3 pt-3 border-t border-border space-y-2">
      <p className="text-[10px] uppercase tracking-[0.15em] text-text-muted font-semibold">Game Conditions</p>
      {weather && !weather.is_dome && (
        <div className="flex flex-wrap gap-x-3 text-xs text-text-secondary">
          <span>{weather.condition}</span>
          {weather.temperature_c !== null && <span>{Math.round(weather.temperature_c)}°C</span>}
          {weather.wind_speed_kmh !== null && <span>Wind {Math.round(weather.wind_speed_kmh)} km/h</span>}
          {weather.is_adverse && <span className="text-yellow-400 font-semibold">⚠ Adverse</span>}
        </div>
      )}
      {hasInjuries && (
        <div className="grid grid-cols-2 gap-2 text-xs">
          {conditions.home_injuries.length > 0 && (
            <div>
              <p className="text-[10px] text-text-muted mb-0.5">{homeAbbr} Out/Doubtful</p>
              {conditions.home_injuries.slice(0, 3).map((inj) => (
                <p key={inj.player_name} className="text-text-secondary truncate">{inj.player_name} <span className="text-loss text-[10px]">{inj.injury_status}</span></p>
              ))}
            </div>
          )}
          {conditions.away_injuries.length > 0 && (
            <div>
              <p className="text-[10px] text-text-muted mb-0.5">{awayAbbr} Out/Doubtful</p>
              {conditions.away_injuries.slice(0, 3).map((inj) => (
                <p key={inj.player_name} className="text-text-secondary truncate">{inj.player_name} <span className="text-loss text-[10px]">{inj.injury_status}</span></p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

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

        {prediction.vegas_context && <VegasPanel vegas={prediction.vegas_context} />}
        {prediction.conditions && (
          <ConditionsPanel conditions={prediction.conditions} homeAbbr={homeAbbr} awayAbbr={awayAbbr} />
        )}
      </div>
    </div>
  );
}
