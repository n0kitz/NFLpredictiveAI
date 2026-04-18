"""
Import per-player per-week stats from nfl_data_py for ML fantasy projections.

Primary source: nfl_data_py.import_weekly_data (fantasy points + usage per week).
Supplements: import_snap_counts (offense_pct → snap_pct). Routes not available
from a single free source at weekly granularity; target_share and adot are
derived from the weekly data where present.
"""

import logging
from typing import Any, Dict, List, Optional

from .nfl_data_importer import _to_our_abbr

logger = logging.getLogger(__name__)


def _match_player_id(db, full_name: str, position: str) -> Optional[int]:
    """Resolve a weekly-data name to our internal player_id.

    Tries exact full_name first, then last-name + position as a fallback.
    Returns None if no confident match.
    """
    if not full_name:
        return None
    row = db.fetchone(
        "SELECT player_id FROM players WHERE full_name = ? LIMIT 1",
        (full_name,),
    )
    if row:
        return int(row['player_id'])
    parts = full_name.strip().split()
    if len(parts) >= 2:
        last = parts[-1]
        row = db.fetchone(
            "SELECT player_id FROM players WHERE last_name = ? AND position = ? LIMIT 1",
            (last, position),
        )
        if row:
            return int(row['player_id'])
    return None


def import_player_weekly_stats(db, years: List[int]) -> int:
    """Fetch weekly stats from nfl_data_py and persist into player_weekly_stats.

    Returns the number of rows upserted. Non-matching players are skipped
    (they will appear later once rosters catch up).
    """
    try:
        import nfl_data_py as nfl
    except ImportError as exc:
        raise ImportError(
            "nfl_data_py is not installed. Run: pip install nfl-data-py"
        ) from exc

    logger.info("Fetching weekly data for years %s …", years)
    weekly = nfl.import_weekly_data(years)

    # Snap counts (offensive) keyed by (player, season, week)
    snap_lookup: Dict[tuple, float] = {}
    try:
        snaps = nfl.import_snap_counts(years)
        for _, r in snaps.iterrows():
            key = (str(r.get('player') or '').strip().lower(),
                   int(r.get('season') or 0), int(r.get('week') or 0))
            pct = r.get('offense_pct')
            if pct is not None and pct == pct:  # not NaN
                snap_lookup[key] = float(pct)
    except Exception as exc:
        logger.warning("Snap counts unavailable — snap_pct will be 0: %s", exc)

    # Team total targets per (team, season, week) for target_share calc
    team_targets: Dict[tuple, int] = {}
    for _, row in weekly.iterrows():
        team_raw = str(row.get('recent_team') or row.get('team') or '').strip()
        if not team_raw:
            continue
        key = (team_raw, int(row.get('season') or 0), int(row.get('week') or 0))
        tgt = int(row.get('targets') or 0)
        team_targets[key] = team_targets.get(key, 0) + tgt

    upserted = 0
    skipped = 0

    for _, row in weekly.iterrows():
        full_name = str(row.get('player_display_name') or row.get('player_name') or '').strip()
        position = str(row.get('position') or '').strip().upper()
        if position not in ('QB', 'RB', 'WR', 'TE'):
            continue

        player_id = _match_player_id(db, full_name, position)
        if player_id is None:
            skipped += 1
            continue

        team_raw = str(row.get('recent_team') or row.get('team') or '').strip()
        opp_raw = str(row.get('opponent_team') or '').strip()
        team_abbr = _to_our_abbr(team_raw) if team_raw else ''
        opp_abbr = _to_our_abbr(opp_raw) if opp_raw else ''

        team_row = db.find_team(team_abbr) if team_abbr else None
        opp_row = db.find_team(opp_abbr) if opp_abbr else None
        team_id = team_row['team_id'] if team_row else None
        opp_id = opp_row['team_id'] if opp_row else None

        season = int(row.get('season') or 0)
        week = int(row.get('week') or 0)
        if season == 0 or week == 0:
            continue

        targets = int(row.get('targets') or 0)
        team_total_tgt = team_targets.get((team_raw, season, week), 0)
        target_share = (targets / team_total_tgt) if team_total_tgt > 0 else 0.0

        snap_pct_key = (full_name.lower(), season, week)
        snap_pct = snap_lookup.get(snap_pct_key, 0.0) / 100.0 if snap_pct_key in snap_lookup else 0.0

        air_yards = int(row.get('receiving_air_yards') or 0)
        adot = (air_yards / targets) if targets > 0 else 0.0

        stats = {
            'player_id': player_id,
            'season': season,
            'week': week,
            'team_id': team_id,
            'opponent_team_id': opp_id,
            'position': position,
            'is_home': False,  # filled in at prediction time from games table
            'snaps': 0,
            'snap_pct': snap_pct,
            'routes': 0,
            'route_pct': 0.0,
            'targets': targets,
            'receptions': int(row.get('receptions') or 0),
            'rec_yards': int(row.get('receiving_yards') or 0),
            'rec_tds': int(row.get('receiving_tds') or 0),
            'target_share': target_share,
            'air_yards': air_yards,
            'adot': adot,
            'rush_attempts': int(row.get('carries') or 0),
            'rush_yards': int(row.get('rushing_yards') or 0),
            'rush_tds': int(row.get('rushing_tds') or 0),
            'pass_attempts': int(row.get('attempts') or 0),
            'pass_completions': int(row.get('completions') or 0),
            'pass_yards': int(row.get('passing_yards') or 0),
            'pass_tds': int(row.get('passing_tds') or 0),
            'interceptions': int(row.get('interceptions') or 0),
            'fantasy_points_ppr': float(row.get('fantasy_points_ppr') or 0.0),
            'fantasy_points_standard': float(row.get('fantasy_points') or 0.0),
        }
        db.upsert_player_weekly_stats(stats)
        upserted += 1

    db.commit()
    logger.info(
        "Weekly stats imported: %d rows persisted, %d skipped (name not matched)",
        upserted, skipped,
    )
    return upserted
