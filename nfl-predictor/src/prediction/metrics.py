"""Metrics calculation module for NFL predictions."""

import math
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional, Dict, Any, Tuple

from ..database.db import Database
from ..database.models import Game, TeamSeasonStats

# Simple TTL cache for team metrics — avoids recomputing on every prediction request.
# Key: (team_id, current_season) → (TeamMetrics, timestamp)
_metrics_cache: Dict[tuple, Any] = {}
_METRICS_TTL = 3600  # 1 hour


@dataclass
class TeamMetrics:
    """Comprehensive team metrics for prediction."""
    team_id: int
    team_name: str
    team_abbr: str

    # Overall record
    overall_wins: int = 0
    overall_losses: int = 0
    overall_ties: int = 0
    win_percentage: float = 0.0

    # Current season stats
    current_season_wins: int = 0
    current_season_losses: int = 0
    current_season_ties: int = 0
    current_season_win_pct: float = 0.0

    # Points
    points_for: int = 0
    points_against: int = 0
    point_differential: int = 0
    avg_points_scored: float = 0.0
    avg_points_allowed: float = 0.0

    # Home/Away splits
    home_wins: int = 0
    home_losses: int = 0
    away_wins: int = 0
    away_losses: int = 0
    home_win_pct: float = 0.0
    away_win_pct: float = 0.0

    # Recent form (last N games)
    recent_wins: int = 0
    recent_losses: int = 0
    recent_win_pct: float = 0.0
    recent_point_diff: int = 0

    # Weighted metrics
    weighted_win_pct: float = 0.0
    weighted_point_diff: float = 0.0

    # Strength indicators
    offensive_strength: float = 0.0  # Points scored relative to league avg
    defensive_strength: float = 0.0  # Points allowed relative to league avg

    # Strength of schedule
    strength_of_schedule: float = 0.5  # avg opponent win%, 0.5 = league average

    # Home field advantage
    dynamic_hfa: float = 0.032  # team-specific HFA derived from data

    # Rest / bye week
    rest_days: int = 7  # days since last game

    # Advanced stats (populated from team_advanced_stats table; league-average defaults
    # are used so that missing data doesn't bias predictions toward 0)
    turnover_margin: float = 0.0
    third_down_pct: float = 0.40   # NFL league avg ~40%
    redzone_efficiency: float = 0.55   # NFL league avg ~55%
    yards_per_play: float = 5.5    # NFL league avg ~5.5 yards/play
    sack_rate_allowed: float = 0.065   # NFL league avg ~6.5%
    qb_epa_per_play: float = 0.0

    # Data quality
    games_analyzed: int = 0
    seasons_analyzed: int = 0


def _get_league_avg_ppg(db: Database, current_season: int, seasons_to_analyze: int) -> float:
    """Calculate league average points per game over the analysis window."""
    start_season = current_season - seasons_to_analyze + 1
    row = db.fetchone(
        """
        SELECT AVG(total_ppg) as avg_ppg FROM (
            SELECT (home_score + away_score) / 2.0 as total_ppg
            FROM games
            WHERE season BETWEEN ? AND ?
              AND home_score IS NOT NULL
        )
        """,
        (start_season, current_season),
    )
    if row and row['avg_ppg'] is not None:
        return row['avg_ppg']
    return 22.0  # fallback


def calculate_exponential_weight(games_ago: int, decay_rate: float = 0.1) -> float:
    """
    Calculate exponential decay weight for a game.

    More recent games get higher weights.

    Args:
        games_ago: Number of games in the past (0 = most recent)
        decay_rate: Rate of decay (higher = faster decay)

    Returns:
        Weight between 0 and 1
    """
    return math.exp(-decay_rate * games_ago)


def calculate_season_weight(seasons_ago: int, current_season_multiplier: float = 3.0) -> float:
    """
    Calculate weight for a season.

    Current season weighted more heavily than past seasons.

    Args:
        seasons_ago: Number of seasons in the past (0 = current)
        current_season_multiplier: Multiplier for current season

    Returns:
        Weight value
    """
    if seasons_ago == 0:
        return current_season_multiplier
    return 1.0 / (seasons_ago + 1)


def calculate_team_metrics(
    db: Database,
    team_id: int,
    current_season: Optional[int] = None,
    recent_games_count: int = 5,
    seasons_to_analyze: int = 3,
    cutoff_date: Optional[str] = None,
) -> 'TeamMetrics':
    # TTL cache — skip for historical cutoff queries (prediction engine uses cutoff_date)
    if cutoff_date is None:
        cache_key = (team_id, current_season)
        cached = _metrics_cache.get(cache_key)
        if cached and (time.time() - cached[1]) < _METRICS_TTL:
            return cached[0]
        result = _calculate_team_metrics_impl(
            db, team_id, current_season, recent_games_count, seasons_to_analyze, cutoff_date
        )
        _metrics_cache[cache_key] = (result, time.time())
        return result
    return _calculate_team_metrics_impl(
        db, team_id, current_season, recent_games_count, seasons_to_analyze, cutoff_date
    )


def _calculate_team_metrics_impl(
    db: Database,
    team_id: int,
    current_season: Optional[int] = None,
    recent_games_count: int = 5,
    seasons_to_analyze: int = 3,
    cutoff_date: Optional[str] = None,
) -> TeamMetrics:
    """
    Calculate comprehensive metrics for a team.

    Args:
        db: Database instance
        team_id: Team ID to analyze
        current_season: Current season year (defaults to latest)
        recent_games_count: Number of recent games for "form" calculation
        seasons_to_analyze: Number of seasons to include in analysis

    Returns:
        TeamMetrics object with calculated values
    """
    # Get team info
    team = db.get_team_by_id(team_id)
    if not team:
        raise ValueError(f"Team not found: {team_id}")

    metrics = TeamMetrics(
        team_id=team_id,
        team_name=team['name'],
        team_abbr=team['abbreviation']
    )

    # Determine current season
    if current_season is None:
        latest = db.fetchone(
            "SELECT MAX(season) as season FROM games WHERE home_score IS NOT NULL"
        )
        current_season = latest['season'] if latest else datetime.now().year

    # Get games from recent seasons
    all_games = []
    for season_offset in range(seasons_to_analyze):
        season = current_season - season_offset
        games = db.get_team_games(team_id, season)
        for game in games:
            if game['home_score'] is not None:
                # In backtest mode, exclude games on or after the cutoff date
                if cutoff_date and str(game['date'])[:10] >= cutoff_date[:10]:
                    continue
                all_games.append((game, season_offset))

    if not all_games:
        return metrics

    # Sort by date descending
    all_games.sort(key=lambda x: x[0]['date'], reverse=True)

    # Calculate metrics
    total_weight = 0.0
    weighted_wins = 0.0
    weighted_point_diff = 0.0

    for idx, (game, season_offset) in enumerate(all_games):
        metrics.games_analyzed += 1

        is_home = game['home_team_id'] == team_id
        team_score = game['home_score'] if is_home else game['away_score']
        opp_score = game['away_score'] if is_home else game['home_score']

        # Basic stats
        metrics.points_for += team_score
        metrics.points_against += opp_score

        # Win/loss tracking
        if game['winner_id'] == team_id:
            metrics.overall_wins += 1
            if is_home:
                metrics.home_wins += 1
            else:
                metrics.away_wins += 1
            if season_offset == 0:
                metrics.current_season_wins += 1
        elif game['winner_id'] is None:
            metrics.overall_ties += 1
            if season_offset == 0:
                metrics.current_season_ties += 1
        else:
            metrics.overall_losses += 1
            if is_home:
                metrics.home_losses += 1
            else:
                metrics.away_losses += 1
            if season_offset == 0:
                metrics.current_season_losses += 1

        # Recent form (last N games)
        if idx < recent_games_count:
            if game['winner_id'] == team_id:
                metrics.recent_wins += 1
            elif game['winner_id'] is not None:
                metrics.recent_losses += 1
            metrics.recent_point_diff += (team_score - opp_score)

        # Weighted calculations
        game_weight = calculate_exponential_weight(idx) * calculate_season_weight(season_offset)
        total_weight += game_weight

        if game['winner_id'] == team_id:
            weighted_wins += game_weight
        elif game['winner_id'] is None:
            weighted_wins += 0.5 * game_weight

        weighted_point_diff += (team_score - opp_score) * game_weight

    # Calculate derived metrics
    total_games = metrics.overall_wins + metrics.overall_losses + metrics.overall_ties

    if total_games > 0:
        metrics.win_percentage = (metrics.overall_wins + 0.5 * metrics.overall_ties) / total_games
        metrics.avg_points_scored = metrics.points_for / total_games
        metrics.avg_points_allowed = metrics.points_against / total_games

    metrics.point_differential = metrics.points_for - metrics.points_against

    # Home/away percentages
    home_games = metrics.home_wins + metrics.home_losses
    away_games = metrics.away_wins + metrics.away_losses

    if home_games > 0:
        metrics.home_win_pct = metrics.home_wins / home_games
    if away_games > 0:
        metrics.away_win_pct = metrics.away_wins / away_games

    # Current season
    current_games = (metrics.current_season_wins + metrics.current_season_losses +
                     metrics.current_season_ties)
    if current_games > 0:
        metrics.current_season_win_pct = (
            (metrics.current_season_wins + 0.5 * metrics.current_season_ties) / current_games
        )

    # Recent form
    recent_total = metrics.recent_wins + metrics.recent_losses
    if recent_total > 0:
        metrics.recent_win_pct = metrics.recent_wins / recent_total

    # Weighted metrics
    if total_weight > 0:
        metrics.weighted_win_pct = weighted_wins / total_weight
        metrics.weighted_point_diff = weighted_point_diff / total_weight

    # Offensive/defensive strength (relative to league average)
    league_avg_ppg = _get_league_avg_ppg(db, current_season, seasons_to_analyze)
    if total_games > 0:
        metrics.offensive_strength = (metrics.avg_points_scored - league_avg_ppg) / league_avg_ppg
        metrics.defensive_strength = (league_avg_ppg - metrics.avg_points_allowed) / league_avg_ppg

    metrics.seasons_analyzed = seasons_to_analyze

    # Strength of schedule: average win% of opponents (cutoff-aware)
    metrics.strength_of_schedule = _calculate_sos(db, team_id, current_season, seasons_to_analyze, cutoff_date)

    # Dynamic home field advantage from historical data (cutoff-aware)
    metrics.dynamic_hfa = _calculate_dynamic_hfa(db, team_id, current_season, seasons_to_analyze, cutoff_date)

    # Rest days since last game (pass cutoff_date as reference in backtest mode)
    metrics.rest_days = _calculate_rest_days(db, team_id, current_season, reference_date=cutoff_date)

    # Advanced stats from team_advanced_stats table.
    # Fall back to the prior season when the current season isn't imported yet
    # (e.g. live predictions during a season whose PBP isn't available yet).
    adv = db.get_advanced_stats(team_id, current_season)
    if not adv and current_season > 2010:
        adv = db.get_advanced_stats(team_id, current_season - 1)
    if adv:
        metrics.turnover_margin    = adv['turnover_margin']
        metrics.third_down_pct     = adv['third_down_pct']
        metrics.redzone_efficiency = adv['redzone_efficiency']
        metrics.yards_per_play     = adv['yards_per_play']
        metrics.sack_rate_allowed  = adv['sack_rate_allowed']
        # qb_epa_per_play is optional (added in migration)
        try:
            metrics.qb_epa_per_play = float(adv['qb_epa_per_play'] or 0.0)
        except (IndexError, KeyError, TypeError):
            metrics.qb_epa_per_play = 0.0

    return metrics


def _calculate_sos(
    db: Database,
    team_id: int,
    current_season: int,
    seasons: int,
    cutoff_date: Optional[str] = None,
) -> float:
    """Calculate strength of schedule: average win% of all opponents faced.

    Uses only games played before cutoff_date so backtest predictions don't
    leak future results. Falls back to today when cutoff_date is None.
    """
    start_season = current_season - seasons + 1
    cutoff = cutoff_date or date.today().isoformat()
    row = db.fetchone(
        """
        SELECT AVG(opp_win_pct) as sos FROM (
            SELECT
                opponents.opp_id,
                CASE WHEN COUNT(*) > 0
                     THEN CAST(SUM(CASE WHEN g2.winner_id = opponents.opp_id THEN 1 ELSE 0 END) AS REAL) / COUNT(*)
                     ELSE 0.5
                END as opp_win_pct
            FROM (
                SELECT DISTINCT
                    CASE WHEN g.home_team_id = ? THEN g.away_team_id ELSE g.home_team_id END as opp_id
                FROM games g
                WHERE (g.home_team_id = ? OR g.away_team_id = ?)
                  AND g.home_score IS NOT NULL
                  AND g.season BETWEEN ? AND ?
                  AND g.date < ?
            ) opponents
            JOIN games g2
              ON (g2.home_team_id = opponents.opp_id OR g2.away_team_id = opponents.opp_id)
             AND g2.home_score IS NOT NULL
             AND g2.date < ?
            GROUP BY opponents.opp_id
        )
        """,
        (team_id, team_id, team_id, start_season, current_season, cutoff, cutoff),
    )
    if row and row['sos'] is not None:
        return row['sos']
    return 0.5


def _calculate_dynamic_hfa(
    db: Database,
    team_id: int,
    current_season: int,
    seasons: int,
    cutoff_date: Optional[str] = None,
) -> float:
    """Calculate team-specific home field advantage from historical home/away win rates.

    Respects cutoff_date so backtest predictions only see games before that date.
    """
    start_season = current_season - seasons + 1
    date_filter = "AND g.date < ?" if cutoff_date else ""
    params: list = [
        team_id, team_id, team_id, team_id, team_id, team_id,
        team_id, team_id, start_season, current_season,
    ]
    if cutoff_date:
        params.append(cutoff_date)
    row = db.fetchone(
        f"""
        SELECT
            SUM(CASE WHEN g.home_team_id = ? AND g.winner_id = ? THEN 1 ELSE 0 END) as home_wins,
            SUM(CASE WHEN g.home_team_id = ? THEN 1 ELSE 0 END) as home_games,
            SUM(CASE WHEN g.away_team_id = ? AND g.winner_id = ? THEN 1 ELSE 0 END) as away_wins,
            SUM(CASE WHEN g.away_team_id = ? THEN 1 ELSE 0 END) as away_games
        FROM games g
        WHERE (g.home_team_id = ? OR g.away_team_id = ?)
          AND g.season BETWEEN ? AND ?
          AND g.home_score IS NOT NULL
          {date_filter}
        """,
        tuple(params),
    )
    if not row or not row['home_games'] or not row['away_games']:
        return 0.032
    home_win_pct = row['home_wins'] / row['home_games']
    away_win_pct = row['away_wins'] / row['away_games']
    hfa = (home_win_pct - away_win_pct) / 2.0
    return max(0.0, min(0.10, hfa))


def _calculate_rest_days(
    db: Database,
    team_id: int,
    current_season: int,
    reference_date: Optional[str] = None,
) -> int:
    """Calculate days since the team's most recent completed game.

    In backtest mode pass reference_date (ISO "YYYY-MM-DD") so the search looks
    for the last game BEFORE that date across all seasons (handles week-1 teams
    whose most recent game was last season's playoffs).
    """
    from datetime import date as date_cls

    if reference_date:
        # Backtest mode: search all seasons, stop before this date
        row = db.fetchone(
            """
            SELECT MAX(date) as last_date
            FROM games
            WHERE (home_team_id = ? OR away_team_id = ?)
              AND home_score IS NOT NULL
              AND date < ?
            """,
            (team_id, team_id, reference_date),
        )
        try:
            ref = date_cls.fromisoformat(reference_date[:10])
        except ValueError:
            ref = date_cls.today()
    else:
        # Live mode: latest completed game in current season, reference is today
        row = db.fetchone(
            """
            SELECT MAX(date) as last_date
            FROM games
            WHERE (home_team_id = ? OR away_team_id = ?)
              AND home_score IS NOT NULL
              AND season = ?
            """,
            (team_id, team_id, current_season),
        )
        ref = date_cls.today()

    if row and row['last_date']:
        try:
            last = date_cls.fromisoformat(str(row['last_date']))
            return (ref - last).days
        except (ValueError, TypeError):
            pass
    return 7  # default


def calculate_head_to_head(
    db: Database,
    team1_id: int,
    team2_id: int,
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Calculate head-to-head record between two teams.

    Args:
        db: Database instance
        team1_id: First team ID
        team2_id: Second team ID
        limit: Maximum number of games to consider

    Returns:
        Dictionary with head-to-head stats
    """
    games = db.get_head_to_head(team1_id, team2_id, limit)

    result = {
        'team1_wins': 0,
        'team2_wins': 0,
        'ties': 0,
        'total_games': len(games),
        'team1_home_wins': 0,
        'team1_away_wins': 0,
        'team2_home_wins': 0,
        'team2_away_wins': 0,
        'last_meeting': None,
        'games': []
    }

    for game in games:
        result['games'].append(game)

        if result['last_meeting'] is None:
            result['last_meeting'] = game

        if game['winner_id'] == team1_id:
            result['team1_wins'] += 1
            if game['home_team_id'] == team1_id:
                result['team1_home_wins'] += 1
            else:
                result['team1_away_wins'] += 1
        elif game['winner_id'] == team2_id:
            result['team2_wins'] += 1
            if game['home_team_id'] == team2_id:
                result['team2_home_wins'] += 1
            else:
                result['team2_away_wins'] += 1
        else:
            result['ties'] += 1

    return result


def calculate_form_rating(metrics: TeamMetrics) -> float:
    """
    Calculate a form rating based on recent performance.

    Combines recent win percentage with point differential trend.

    Args:
        metrics: TeamMetrics object

    Returns:
        Form rating between 0 and 1
    """
    # Weight recent win percentage heavily
    form = metrics.recent_win_pct * 0.6

    # Add point differential component (normalized)
    # Average of ~3.5 point diff per game is strong
    pd_component = max(min(metrics.recent_point_diff / 35.0, 1.0), -1.0)
    form += (pd_component + 1) / 2 * 0.4

    return max(0.0, min(1.0, form))


def calculate_strength_rating(metrics: TeamMetrics) -> float:
    """
    Calculate overall strength rating for a team.

    Combines offensive and defensive strength indicators.

    Args:
        metrics: TeamMetrics object

    Returns:
        Strength rating (can be negative for weak teams)
    """
    # Combine offensive and defensive strength
    return (metrics.offensive_strength + metrics.defensive_strength) / 2
