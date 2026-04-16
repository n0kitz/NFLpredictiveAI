"""Convert TeamMetrics + H2H + game metadata into a fixed-length feature vector."""

from typing import Any, Dict, Optional, Union

import numpy as np

from .metrics import TeamMetrics, calculate_form_rating, calculate_strength_rating

# Fixed feature order — used for both training and inference.
# Any change to this list invalidates existing saved models.
# 34 features total.
# NOTE: vegas_home_implied_prob was removed (feature #33) — it was 0.5 for ~95% of
# training data (2013-2022 have no odds in DB), so the GBM learned nothing from it.
# Using real odds at inference on a model trained with 0.5 is silent data leakage.
# Features #33-34 are rolling 4-game starter QB EPA (replaced season aggregate).
# IMPORTANT: Delete data/nfl_model.joblib and retrain with: python scripts/train_model.py
FEATURE_NAMES: list[str] = [
    "home_win_pct",
    "away_win_pct",
    "home_weighted_win_pct",
    "away_weighted_win_pct",
    "home_ppg",
    "away_ppg",
    "home_pag",
    "away_pag",
    "home_point_diff_per_game",
    "away_point_diff_per_game",
    "home_sos",
    "away_sos",
    "home_form_rating",
    "away_form_rating",
    "home_strength",
    "away_strength",
    "home_home_win_pct",
    "away_away_win_pct",
    "h2h_home_win_pct",
    "home_rest_days",
    "away_rest_days",
    "home_turnover_margin",
    "away_turnover_margin",
    "home_third_down_pct",
    "away_third_down_pct",
    "home_yards_per_play",
    "away_yards_per_play",
    "home_redzone_efficiency",
    "away_redzone_efficiency",
    "is_playoff",
    "week_of_season",
    "home_dynamic_hfa",          # 32nd: team-specific home field advantage
    "home_starter_qb_epa_l4",   # 33rd: rolling 4-game starter QB EPA (home)
    "away_starter_qb_epa_l4",   # 34th: rolling 4-game starter QB EPA (away)
]

assert len(FEATURE_NAMES) == 34, f"Expected 34 features, got {len(FEATURE_NAMES)}"


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b != 0 else default


def get_rolling_starter_qb_epa(
    db,
    team_id: int,
    before_week: int,
    season: int,
    window: int = 4,
    fallback: float = 0.0,
) -> float:
    """
    Return average EPA per play for the starting QB over the last *window* games
    played before *before_week* in *season*.

    Falls back to *fallback* (typically the season-aggregate from TeamMetrics)
    when fewer than 2 games are available in weekly_qb_starts.

    Args:
        db:          Database instance.
        team_id:     Team to look up.
        before_week: Current game week — only prior weeks are included.
        season:      NFL season year.
        window:      Number of prior games to average (default 4).
        fallback:    Value to return when insufficient data exists.

    Returns:
        Rolling mean epa_per_play (float), or *fallback*.
    """
    try:
        rows = db.fetchall(
            """
            SELECT epa_per_play FROM weekly_qb_starts
            WHERE team_id = ? AND season = ? AND week < ?
              AND epa_per_play IS NOT NULL
            ORDER BY week DESC
            LIMIT ?
            """,
            (team_id, season, before_week, window),
        )
    except Exception:
        return fallback

    if len(rows) < 2:
        return fallback

    return float(sum(r["epa_per_play"] for r in rows) / len(rows))


def build_feature_vector(
    home_metrics: TeamMetrics,
    away_metrics: TeamMetrics,
    h2h: Dict[str, Any],
    is_playoff: Union[bool, int] = False,
    week: Union[str, int] = 0,
    vegas_implied_prob: float = 0.5,
    home_starter_qb_epa: Optional[float] = None,
    away_starter_qb_epa: Optional[float] = None,
) -> Dict[str, float]:
    """
    Build a feature dict from two TeamMetrics objects plus game context.

    Args:
        home_metrics:        Metrics for the home team (computed with cutoff_date).
        away_metrics:        Metrics for the away team (computed with cutoff_date).
        h2h:                 Dict with keys team1_wins, team2_wins, total_games.
        is_playoff:          1/True for playoff game, 0/False for regular season.
        week:                Integer week of season (1-22), or string ('Wild Card').
        vegas_implied_prob:  Unused — kept for interface compatibility.
        home_starter_qb_epa: Pre-computed rolling QB EPA for home team.  When None,
                             falls back to home_metrics.qb_epa_per_play (season avg).
        away_starter_qb_epa: Pre-computed rolling QB EPA for away team.  Same fallback.

    Returns:
        Dict mapping each FEATURE_NAME to a float value.
    """
    home_games = home_metrics.games_analyzed or 1
    away_games = away_metrics.games_analyzed or 1

    h2h_total = h2h.get("total_games", 0)
    if h2h_total >= 2:
        h2h_home_pct = _safe_div(h2h.get("team1_wins", 0), h2h_total, 0.5)
    else:
        h2h_home_pct = 0.5

    week_int = _parse_week(week)

    # Rolling starter QB EPA — fall back to season aggregate when not supplied
    home_qb_epa = home_starter_qb_epa if home_starter_qb_epa is not None else home_metrics.qb_epa_per_play
    away_qb_epa = away_starter_qb_epa if away_starter_qb_epa is not None else away_metrics.qb_epa_per_play

    return {
        "home_win_pct":              home_metrics.win_percentage,
        "away_win_pct":              away_metrics.win_percentage,
        "home_weighted_win_pct":     home_metrics.weighted_win_pct,
        "away_weighted_win_pct":     away_metrics.weighted_win_pct,
        "home_ppg":                  home_metrics.avg_points_scored,
        "away_ppg":                  away_metrics.avg_points_scored,
        "home_pag":                  home_metrics.avg_points_allowed,
        "away_pag":                  away_metrics.avg_points_allowed,
        "home_point_diff_per_game":  _safe_div(home_metrics.point_differential, home_games),
        "away_point_diff_per_game":  _safe_div(away_metrics.point_differential, away_games),
        "home_sos":                  home_metrics.strength_of_schedule,
        "away_sos":                  away_metrics.strength_of_schedule,
        "home_form_rating":          calculate_form_rating(home_metrics),
        "away_form_rating":          calculate_form_rating(away_metrics),
        "home_strength":             calculate_strength_rating(home_metrics),
        "away_strength":             calculate_strength_rating(away_metrics),
        "home_home_win_pct":         home_metrics.home_win_pct,
        "away_away_win_pct":         away_metrics.away_win_pct,
        "h2h_home_win_pct":          h2h_home_pct,
        "home_rest_days":            float(home_metrics.rest_days),
        "away_rest_days":            float(away_metrics.rest_days),
        "home_turnover_margin":      home_metrics.turnover_margin,
        "away_turnover_margin":      away_metrics.turnover_margin,
        "home_third_down_pct":       home_metrics.third_down_pct,
        "away_third_down_pct":       away_metrics.third_down_pct,
        "home_yards_per_play":       home_metrics.yards_per_play,
        "away_yards_per_play":       away_metrics.yards_per_play,
        "home_redzone_efficiency":   home_metrics.redzone_efficiency,
        "away_redzone_efficiency":   away_metrics.redzone_efficiency,
        "is_playoff":                float(int(is_playoff)),
        "week_of_season":            float(week_int),
        "home_dynamic_hfa":          home_metrics.dynamic_hfa,
        "home_starter_qb_epa_l4":   home_qb_epa,
        "away_starter_qb_epa_l4":   away_qb_epa,
    }


def feature_dict_to_array(feature_dict: Dict[str, float]) -> np.ndarray:
    """
    Convert a feature dict (from build_feature_vector) to a 1-D ndarray.

    Values are placed in the canonical FEATURE_NAMES order.
    Missing keys default to 0.0.

    Returns:
        np.ndarray of shape (35,), dtype float64.
    """
    return np.array([feature_dict.get(name, 0.0) for name in FEATURE_NAMES], dtype=np.float64)


# ── Private helpers ──────────────────────────────────────────────────────────

_PLAYOFF_WEEK_MAP: Dict[str, int] = {
    "wild card":   19,
    "wildcard":    19,
    "divisional":  20,
    "division":    20,
    "conference":  21,
    "championship": 21,
    "super bowl":  22,
    "superbowl":   22,
}


def _parse_week(week: Union[str, int]) -> int:
    """Convert a week value (str or int) to an integer 1-22, or 0 if unknown."""
    if isinstance(week, int):
        return week
    try:
        return int(week)
    except (ValueError, TypeError):
        key = str(week).lower().strip()
        return _PLAYOFF_WEEK_MAP.get(key, 0)
