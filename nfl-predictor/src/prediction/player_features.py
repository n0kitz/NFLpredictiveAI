"""
Feature builder for per-player per-week ML fantasy projections.

Produces a fixed-order feature vector for a single (player, week, season, opp)
tuple. Training and inference must use the exact same order — the constants in
this module are the single source of truth.

Features (13):
    1.  rolling_4wk_ppr       — avg PPR over last 4 weeks
    2.  rolling_8wk_ppr       — avg PPR over last 8 weeks
    3.  season_ppg_ppr        — season-to-date PPR per game
    4.  snap_pct_4wk          — avg snap % last 4 weeks
    5.  target_share_4wk      — avg target share last 4 weeks
    6.  adot_4wk              — avg depth of target last 4 weeks
    7.  rush_att_4wk          — avg rush attempts last 4 weeks
    8.  opp_dvp_pts_4wk       — opponent PPR allowed to this position (4 wks)
    9.  opp_yards_per_play    — opponent YPP (team_advanced_stats, prior fallback)
    10. vegas_team_total      — implied team points (O/U ± spread/2)
    11. is_home               — 0/1
    12. weather_is_adverse    — 0/1 (dome=0)
    13. weeks_of_experience   — player's weeks played this season up to current
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


FEATURE_NAMES: List[str] = [
    'rolling_4wk_ppr',
    'rolling_8wk_ppr',
    'season_ppg_ppr',
    'snap_pct_4wk',
    'target_share_4wk',
    'adot_4wk',
    'rush_att_4wk',
    'opp_dvp_pts_4wk',
    'opp_yards_per_play',
    'vegas_team_total',
    'is_home',
    'weather_is_adverse',
    'weeks_of_experience',
]

FEATURE_LABELS: Dict[str, str] = {
    'rolling_4wk_ppr':     'Last-4 PPR avg',
    'rolling_8wk_ppr':     'Last-8 PPR avg',
    'season_ppg_ppr':      'Season PPR/G',
    'snap_pct_4wk':        'Snap % (4w)',
    'target_share_4wk':    'Target share (4w)',
    'adot_4wk':            'aDOT (4w)',
    'rush_att_4wk':        'Rush att (4w)',
    'opp_dvp_pts_4wk':     'Opp DvP (4w)',
    'opp_yards_per_play':  'Opp YPP',
    'vegas_team_total':    'Vegas team total',
    'is_home':             'Home game',
    'weather_is_adverse':  'Adverse weather',
    'weeks_of_experience': 'Weeks played',
}

POSITIONS: Tuple[str, ...] = ('QB', 'RB', 'WR', 'TE')


# ── Feature helpers ──────────────────────────────────────────────────────────

def _rolling_avg(rows: List[Any], field: str, n: int) -> float:
    """Average a stat over the most recent n rows. Returns 0.0 if no rows."""
    if not rows:
        return 0.0
    vals = [float(r[field] or 0.0) for r in rows[:n]]
    return sum(vals) / len(vals) if vals else 0.0


def _vegas_team_total(spread: Optional[float], over_under: Optional[float], is_home: bool) -> float:
    """Implied points for this team given spread (home-negative) and O/U.

    team_total = (OU / 2) - (spread / 2 if home else -spread / 2)
    Falls back to 22.0 (league-average team total) when odds are missing.
    """
    if over_under is None or spread is None:
        return 22.0
    half = float(over_under) / 2.0
    if is_home:
        return max(0.0, half - float(spread) / 2.0)
    return max(0.0, half + float(spread) / 2.0)


# ── Public API ───────────────────────────────────────────────────────────────

def build_player_feature_vector(
    db,
    player_id: int,
    position: str,
    season: int,
    week: int,
    opponent_team_id: Optional[int],
    is_home: bool,
    spread: Optional[float] = None,
    over_under: Optional[float] = None,
    weather_is_adverse: bool = False,
) -> Dict[str, float]:
    """Assemble the feature dict for one (player, week) prediction.

    Only data strictly before `week` within `season` is used, plus prior-season
    advanced stats and vegas context (which reference the game itself). Callers
    must pass `opponent_team_id`, `is_home`, and optionally Vegas/weather.
    """
    # Historical weekly rows (newest first), strictly before this week
    hist = db.get_player_weekly_stats(player_id, season, before_week=week, limit=20)

    rolling_4 = _rolling_avg(hist, 'fantasy_points_ppr', 4)
    rolling_8 = _rolling_avg(hist, 'fantasy_points_ppr', 8)
    season_ppg = _rolling_avg(hist, 'fantasy_points_ppr', 20)  # all weeks so far

    snap_pct_4 = _rolling_avg(hist, 'snap_pct', 4)
    target_share_4 = _rolling_avg(hist, 'target_share', 4)
    adot_4 = _rolling_avg(hist, 'adot', 4)
    rush_att_4 = _rolling_avg(hist, 'rush_attempts', 4)

    # Opponent DvP — fantasy pts allowed to this position by opponent
    opp_dvp = 0.0
    opp_ypp = 5.5
    if opponent_team_id:
        opp_dvp = db.get_opponent_position_allowed(
            opponent_team_id, position, season, week, lookback=4,
        )
        adv = db.get_advanced_stats(opponent_team_id, season) \
            or db.get_advanced_stats(opponent_team_id, season - 1)
        if adv:
            opp_ypp = float(adv['yards_per_play'] or 5.5)

    vegas_total = _vegas_team_total(spread, over_under, is_home)

    return {
        'rolling_4wk_ppr':     rolling_4,
        'rolling_8wk_ppr':     rolling_8,
        'season_ppg_ppr':      season_ppg,
        'snap_pct_4wk':        snap_pct_4,
        'target_share_4wk':    target_share_4,
        'adot_4wk':            adot_4,
        'rush_att_4wk':        rush_att_4,
        'opp_dvp_pts_4wk':     opp_dvp,
        'opp_yards_per_play':  opp_ypp,
        'vegas_team_total':    vegas_total,
        'is_home':             1.0 if is_home else 0.0,
        'weather_is_adverse':  1.0 if weather_is_adverse else 0.0,
        'weeks_of_experience': float(len(hist)),
    }


def feature_dict_to_array(feats: Dict[str, float]) -> np.ndarray:
    """Convert feature dict to the canonical ordered 1-D array."""
    return np.array([float(feats[name]) for name in FEATURE_NAMES], dtype=np.float64)


def build_training_rows(db, seasons: List[int], position: str) -> Tuple[np.ndarray, np.ndarray]:
    """Build (X, y) for a position over given seasons using historical data only.

    For each (player, week) with recorded actuals, assembles the pre-week
    feature vector and targets the actual fantasy_points_ppr.
    Weeks 1-2 are skipped because the 4-week rolling window is empty.
    """
    X_rows: List[np.ndarray] = []
    y_rows: List[float] = []

    # Get all weekly rows for this position in these seasons
    placeholders = ','.join('?' * len(seasons))
    rows = db.fetchall(
        f"""
        SELECT pws.*, g.home_team_id, g.away_team_id
        FROM player_weekly_stats pws
        LEFT JOIN games g
          ON g.season = pws.season
         AND (CAST(g.week AS INTEGER) = pws.week OR g.week = CAST(pws.week AS TEXT))
         AND (g.home_team_id = pws.team_id OR g.away_team_id = pws.team_id)
        WHERE pws.position = ? AND pws.season IN ({placeholders})
        ORDER BY pws.season ASC, pws.week ASC
        """,
        (position, *seasons),
    )

    for r in rows:
        week = int(r['week'])
        if week <= 2:
            continue
        season = int(r['season'])
        player_id = int(r['player_id'])
        opp_id = r['opponent_team_id']
        home_id = r['home_team_id']
        is_home = (home_id is not None and home_id == r['team_id'])

        # Vegas: pull odds for this game if we can derive game_id
        spread, ou = None, None
        if home_id is not None:
            odds = db.fetchone(
                """
                SELECT opening_spread, over_under FROM game_odds
                WHERE home_team_id = ? AND game_date LIKE ?
                ORDER BY ABS(julianday(game_date) - julianday(?)) LIMIT 1
                """,
                (home_id, f"{season}-%", f"{season}-09-01"),  # rough filter
            )
            if odds:
                spread = odds['opening_spread']
                ou = odds['over_under']

        feats = build_player_feature_vector(
            db, player_id, position, season, week, opp_id, is_home,
            spread=spread, over_under=ou, weather_is_adverse=False,
        )
        X_rows.append(feature_dict_to_array(feats))
        y_rows.append(float(r['fantasy_points_ppr'] or 0.0))

    if not X_rows:
        return np.zeros((0, len(FEATURE_NAMES))), np.zeros(0)
    return np.vstack(X_rows), np.array(y_rows, dtype=np.float64)
