"""
Phase 2 — Advanced Matchup Engine.

Beat FantasyPros DvP with position-split, pace-adjusted, neutral-script metrics.

Public API
----------
opp_position_dvp(db, team_id, pos, season, week, lookback=6)
    Average PPR allowed to a position over the last `lookback` weeks.

pace_adjusted_plays(db, team_id, season)
    Estimated game pace (normalised around 1.0 = league average).
    Derived from average total points per game (proxy for plays per game).

pass_rate_over_expected(db, team_id, season)
    PROE proxy: qb_epa_per_play deviation from the league mean.
    Positive = pass-heavy tendency; negative = run-heavy.

neutral_script_rates(db, team_id, season)
    Pass/rush balance in close games (final margin ≤ 7).
    Returns {'pass_rate': float, 'rush_rate': float}.

matchup_grade(db, player_id, opp_team_id, position, season, week)
    Composite A/B/C/D/F grade + 0-100 score for a player vs opponent.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── League-average baselines ─────────────────────────────────────────────────

_AVG_TOTAL_POINTS_PER_GAME = 44.0   # ~22 per team
_AVG_YPP                   = 5.5
_AVG_QB_EPA                = 0.0    # EPA is zero-centred by construction

# Avg PPR allowed to each position per *player* per game (2020-2024 benchmarks)
_AVG_DVP: Dict[str, float] = {
    'QB': 20.0,
    'RB': 9.5,
    'WR': 11.0,
    'TE': 8.0,
    'K':  8.0,
}

# Grade thresholds (score → letter)
_GRADE_THRESHOLDS = [
    (85, 'A'),
    (70, 'B'),
    (50, 'C'),
    (35, 'D'),
]


# ── Core functions ────────────────────────────────────────────────────────────

def opp_position_dvp(
    db,
    team_id: int,
    pos: str,
    season: int,
    week: int,
    lookback: int = 6,
) -> float:
    """Return avg PPR allowed by `team_id` to `pos` over last `lookback` weeks.

    Queries player_weekly_stats for all players of `pos` who faced this team
    before `week` in `season` (or prior season as fallback).

    Returns league-average DvP for the position when insufficient data exists.
    """
    pos = pos.upper()
    avg_ppr = _query_dvp(db, team_id, pos, season, week, lookback)
    if avg_ppr is None and season > 2013:
        avg_ppr = _query_dvp(db, team_id, pos, season - 1, 19, lookback)
    if avg_ppr is None:
        return _AVG_DVP.get(pos, 10.0)
    return round(avg_ppr, 3)


def _query_dvp(db, team_id: int, pos: str, season: int, before_week: int, lookback: int) -> Optional[float]:
    rows = db.fetchall(
        """
        SELECT AVG(pws.fantasy_points_ppr) AS avg_ppr
        FROM (
            SELECT pws.fantasy_points_ppr
            FROM player_weekly_stats pws
            WHERE pws.opponent_team_id = ?
              AND pws.position = ?
              AND pws.season = ?
              AND pws.week < ?
            ORDER BY pws.week DESC
            LIMIT ?
        ) pws
        """,
        (team_id, pos, season, before_week, lookback * 22),
    )
    if not rows or rows[0]['avg_ppr'] is None:
        return None
    return float(rows[0]['avg_ppr'])


def pace_adjusted_plays(db, team_id: int, season: int) -> float:
    """Estimate opponent game pace normalised around 1.0 (league average).

    Uses average total scoring in recent home games as a proxy for plays-per-game.
    Faster-paced games produce more scoring opportunities.

    Returns a value in roughly [0.6, 1.4].
    """
    rows = db.fetchall(
        """
        SELECT AVG(g.home_score + g.away_score) AS avg_total
        FROM games g
        WHERE (g.home_team_id = ? OR g.away_team_id = ?)
          AND g.season = ?
          AND g.home_score IS NOT NULL
          AND g.game_type = 'regular'
        ORDER BY g.date DESC
        LIMIT 16
        """,
        (team_id, team_id, season),
    )
    if not rows or rows[0]['avg_total'] is None:
        # Fall back to prior season
        rows = db.fetchall(
            """
            SELECT AVG(g.home_score + g.away_score) AS avg_total
            FROM games g
            WHERE (g.home_team_id = ? OR g.away_team_id = ?)
              AND g.season = ?
              AND g.home_score IS NOT NULL
              AND g.game_type = 'regular'
            LIMIT 16
            """,
            (team_id, team_id, season - 1),
        )
    if not rows or rows[0]['avg_total'] is None:
        return 1.0

    avg_total = float(rows[0]['avg_total'])
    pace = avg_total / _AVG_TOTAL_POINTS_PER_GAME
    return round(max(0.6, min(1.5, pace)), 3)


def pass_rate_over_expected(db, team_id: int, season: int) -> float:
    """PROE proxy: qb_epa_per_play deviation from the league mean.

    Positive values indicate a pass-heavy team/game environment.
    Negative values indicate a run-heavy environment.

    Returns a value in roughly [-0.3, 0.3].
    """
    adv = db.fetchone(
        "SELECT qb_epa_per_play FROM team_advanced_stats WHERE team_id=? AND season=?",
        (team_id, season),
    ) or db.fetchone(
        "SELECT qb_epa_per_play FROM team_advanced_stats WHERE team_id=? ORDER BY season DESC LIMIT 1",
        (team_id,),
    )
    if not adv or adv['qb_epa_per_play'] is None:
        return 0.0
    proe = float(adv['qb_epa_per_play']) - _AVG_QB_EPA
    return round(max(-0.5, min(0.5, proe)), 4)


def neutral_script_rates(db, team_id: int, season: int) -> Dict[str, float]:
    """Pass/rush balance inferred from close-game scoring patterns.

    A 'neutral script' is defined as a game with a final margin ≤ 7 points.
    We approximate pass vs rush balance by looking at the YPP differential in
    those games vs the team's season average. High-YPP close games correlate
    with pass-heavy scripts.

    Returns {'pass_rate': float, 'rush_rate': float} summing to 1.0.
    """
    # Close games (decided by ≤ 7 points)
    close_rows = db.fetchall(
        """
        SELECT ABS(home_score - away_score) AS margin,
               home_team_id, away_team_id,
               home_score, away_score
        FROM games
        WHERE (home_team_id = ? OR away_team_id = ?)
          AND season = ?
          AND home_score IS NOT NULL
          AND game_type = 'regular'
          AND ABS(home_score - away_score) <= 7
        """,
        (team_id, team_id, season),
    )
    all_rows = db.fetchall(
        """
        SELECT home_score, away_score, home_team_id
        FROM games
        WHERE (home_team_id = ? OR away_team_id = ?)
          AND season = ?
          AND home_score IS NOT NULL
          AND game_type = 'regular'
        """,
        (team_id, team_id, season),
    )

    def _avg_points(rows: List[Any]) -> float:
        if not rows:
            return 22.0
        pts = []
        for g in rows:
            if g['home_team_id'] == team_id:
                pts.append(float(g['home_score'] or 0))
            else:
                pts.append(float(g['away_score'] or 0))
        return sum(pts) / len(pts) if pts else 22.0

    close_pts = _avg_points(close_rows)
    all_pts = _avg_points(all_rows) or 22.0

    # Ratio of close-game scoring to overall: > 1 means team scores well in neutral scripts
    neutrality = min(1.5, max(0.5, close_pts / all_pts))

    # Base NFL pass rate ~57%, adjust by neutrality signal and qb_epa
    proe = pass_rate_over_expected(db, team_id, season)
    base_pass_rate = 0.57 + (proe * 0.15) + (neutrality - 1.0) * 0.05
    pass_rate = round(max(0.40, min(0.72, base_pass_rate)), 3)
    return {
        'pass_rate': pass_rate,
        'rush_rate': round(1.0 - pass_rate, 3),
    }


# ── Composite grade ───────────────────────────────────────────────────────────

def matchup_grade(
    db,
    player_id: int,
    opp_team_id: int,
    position: str,
    season: int,
    week: int,
) -> Dict[str, Any]:
    """Compute a matchup grade (A/B/C/D/F + 0-100 score) for a player vs opponent.

    Weighting:
      45% — 6wk position DvP (vs league average)
      25% — YPP allowed (general defense quality)
      20% — Game pace (more plays = more opportunities)
      10% — PROE / game-script (position-dependent)

    Higher score = better matchup for the player.
    """
    pos = (position or '').upper()

    # ── 1. 6wk position DvP ─────────────────────────────────────────────────
    dvp_6wk = opp_position_dvp(db, opp_team_id, pos, season, week, lookback=6)
    avg_dvp = _AVG_DVP.get(pos, 10.0)
    # dvp_ratio > 1 → opponent allows more than average → better matchup
    dvp_ratio = dvp_6wk / avg_dvp if avg_dvp > 0 else 1.0
    dvp_score = _sigmoid_score(dvp_ratio, centre=1.0, steepness=80.0)  # 0-100

    # ── 2. YPP allowed ───────────────────────────────────────────────────────
    adv = (
        db.fetchone("SELECT yards_per_play FROM team_advanced_stats WHERE team_id=? AND season=?",
                    (opp_team_id, season))
        or db.fetchone("SELECT yards_per_play FROM team_advanced_stats WHERE team_id=? ORDER BY season DESC LIMIT 1",
                       (opp_team_id,))
    )
    opp_ypp = float(adv['yards_per_play'] or _AVG_YPP) if adv else _AVG_YPP
    ypp_ratio = opp_ypp / _AVG_YPP
    ypp_score = _sigmoid_score(ypp_ratio, centre=1.0, steepness=80.0)

    # ── 3. Pace ──────────────────────────────────────────────────────────────
    pace = pace_adjusted_plays(db, opp_team_id, season)
    pace_score = _sigmoid_score(pace, centre=1.0, steepness=80.0)

    # ── 4. PROE / game-script ────────────────────────────────────────────────
    proe = pass_rate_over_expected(db, opp_team_id, season)
    # Positive PROE = pass-heavy games = good for QB/WR/TE, bad for RB
    if pos in ('QB', 'WR', 'TE'):
        proe_score = 50.0 + proe * 100.0
    elif pos == 'RB':
        proe_score = 50.0 - proe * 100.0   # run-heavy = better for RB
    else:
        proe_score = 50.0

    proe_score = max(0.0, min(100.0, proe_score))

    # ── Composite ────────────────────────────────────────────────────────────
    composite = (
        dvp_score  * 0.45
        + ypp_score  * 0.25
        + pace_score * 0.20
        + proe_score * 0.10
    )
    score = round(max(0.0, min(100.0, composite)), 1)

    grade = 'F'
    for threshold, letter in _GRADE_THRESHOLDS:
        if score >= threshold:
            grade = letter
            break

    # Rank vs league: how does this opp rank among all 32 opponents?
    rank_vs_league = _compute_league_rank(db, opp_team_id, pos, season, week, score)

    explanation = _build_explanation(pos, dvp_6wk, avg_dvp, opp_ypp, pace, proe, grade)

    return {
        'grade':           grade,
        'score':           score,
        'rank_vs_league':  rank_vs_league,
        'explanation':     explanation,
        'dvp_6wk':         round(dvp_6wk, 2),
        'avg_league_dvp':  round(avg_dvp, 2),
        'opp_ypp':         round(opp_ypp, 2),
        'pace':            round(pace, 3),
        'proe':            round(proe, 4),
        'component_scores': {
            'dvp':   round(dvp_score, 1),
            'ypp':   round(ypp_score, 1),
            'pace':  round(pace_score, 1),
            'proe':  round(proe_score, 1),
        },
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _sigmoid_score(ratio: float, centre: float = 1.0, steepness: float = 80.0) -> float:
    """Map a ratio to [0, 100] via a linear interpolation clamped at extremes.

    ratio = 1.0 → 50 (league average)
    ratio > 1.0 → above 50 (favourable)
    ratio < 1.0 → below 50 (unfavourable)
    """
    raw = 50.0 + (ratio - centre) * steepness
    return max(0.0, min(100.0, raw))


def _compute_league_rank(
    db, opp_team_id: int, pos: str, season: int, week: int, own_score: float
) -> int:
    """Return rank of this matchup among all 32 teams (1 = hardest for player)."""
    teams = db.fetchall(
        """
        SELECT team_id FROM teams
        WHERE (active_from IS NULL OR active_from <= ?)
          AND (active_until IS NULL OR active_until >= ?)
        """,
        (season, season),
    )
    scores = []
    for t in teams:
        tid = t['team_id']
        if tid == opp_team_id:
            scores.append(own_score)
            continue
        dvp = opp_position_dvp(db, tid, pos, season, week, lookback=6)
        avg_dvp = _AVG_DVP.get(pos, 10.0)
        dvp_ratio = dvp / avg_dvp if avg_dvp > 0 else 1.0
        approx = _sigmoid_score(dvp_ratio)
        scores.append(approx)

    scores.sort(reverse=True)
    try:
        rank = scores.index(own_score) + 1
    except ValueError:
        rank = 16
    return rank


def _build_explanation(
    pos: str, dvp: float, avg_dvp: float, opp_ypp: float,
    pace: float, proe: float, grade: str,
) -> str:
    parts = []
    dvp_pct = round((dvp / avg_dvp - 1.0) * 100) if avg_dvp > 0 else 0
    if dvp_pct >= 10:
        parts.append(f"opponent allows {dvp_pct}% more PPR to {pos}s than league avg")
    elif dvp_pct <= -10:
        parts.append(f"opponent allows {abs(dvp_pct)}% fewer PPR to {pos}s than league avg")
    else:
        parts.append(f"opponent is near league avg for {pos} PPR allowed")

    if opp_ypp >= 5.9:
        parts.append("weak overall defense (high YPP)")
    elif opp_ypp <= 5.1:
        parts.append("strong overall defense (low YPP)")

    if pace >= 1.1:
        parts.append("fast-paced games (more opportunities)")
    elif pace <= 0.9:
        parts.append("slow-paced games (fewer plays)")

    if pos in ('QB', 'WR', 'TE') and proe > 0.05:
        parts.append("pass-heavy game script expected")
    elif pos == 'RB' and proe < -0.05:
        parts.append("run-heavy game script expected")

    return f"Grade {grade}: " + "; ".join(parts) + "."
