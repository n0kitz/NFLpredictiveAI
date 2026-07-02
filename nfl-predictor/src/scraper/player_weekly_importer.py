"""
Import per-player per-week stats from the nflverse data releases for ML
fantasy projections.

Primary source: the nflverse `stats_player/stats_player_week_{year}.parquet`
release asset (nfl_data_py's import_weekly_data points at the retired
`player_stats` release, which stopped updating after 2024). The new asset
covers all positions — including kickers with FG distance buckets and
defensive players — so kicker and DST imports read the same frame.
Supplements: nfl_data_py.import_snap_counts (offense_pct → snap_pct).
"""

import logging
from typing import Any, Dict, List, Optional

from .nfl_data_importer import _to_our_abbr

logger = logging.getLogger(__name__)

STATS_PLAYER_WEEK_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "stats_player/stats_player_week_{year}.parquet"
)


def fetch_stats_player_week(years: List[int]):
    """Download the nflverse per-player weekly stats frame for the given years."""
    import pandas as pd

    frames = []
    for year in years:
        url = STATS_PLAYER_WEEK_URL.format(year=year)
        logger.info("Fetching stats_player_week for %d …", year)
        frames.append(pd.read_parquet(url))
    return pd.concat(frames, ignore_index=True)


# ── Kicker support ────────────────────────────────────────────────────────────

def kicker_fantasy_points(fg_0_39: int, fg_40_49: int, fg_50_plus: int,
                          xp_made: int) -> float:
    """NFL.com default kicker scoring: FG 0-49yd = 3, FG 50+ = 5, XP = 1."""
    return float(3 * (fg_0_39 + fg_40_49) + 5 * fg_50_plus + xp_made)


def build_kicker_week_rows(df) -> List[Dict[str, Any]]:
    """Extract regular-season kicker week rows from a stats_player_week frame.

    Collapses nflverse FG distance buckets into the 0-39 / 40-49 / 50+ splits
    used by NFL.com scoring and computes fantasy points (nflverse leaves
    fantasy_points at 0 for kickers).
    """
    rows: List[Dict[str, Any]] = []
    kickers = df[(df['position'] == 'K') & (df['season_type'] == 'REG')]
    for _, r in kickers.iterrows():
        fg_0_39 = int(r.get('fg_made_0_19') or 0) + int(r.get('fg_made_20_29') or 0) \
            + int(r.get('fg_made_30_39') or 0)
        fg_40_49 = int(r.get('fg_made_40_49') or 0)
        fg_50_plus = int(r.get('fg_made_50_59') or 0) + int(r.get('fg_made_60_') or 0)
        xp_made = int(r.get('pat_made') or 0)
        rows.append({
            'full_name': str(r.get('player_display_name') or r.get('player_name') or '').strip(),
            'position': 'K',
            'team_abbr': str(r.get('team') or '').strip(),
            'opp_abbr': str(r.get('opponent_team') or '').strip(),
            'season': int(r.get('season') or 0),
            'week': int(r.get('week') or 0),
            'fg_made_0_39': fg_0_39,
            'fg_made_40_49': fg_40_49,
            'fg_made_50_plus': fg_50_plus,
            'fg_missed': int(r.get('fg_missed') or 0),
            'xp_made': xp_made,
            'xp_missed': int(r.get('pat_missed') or 0),
            'fantasy_points': kicker_fantasy_points(
                fg_0_39, fg_40_49, fg_50_plus, xp_made),
        })
    return rows


def aggregate_kicker_dst_season_stats(db, seasons: List[int],
                                      positions=('K', 'DST')) -> int:
    """Roll weekly K/DST rows up into player_season_stats.

    Draft rankings and leaderboards read player_season_stats, which the
    nfl_data_py seasonal import never covers for kickers or team defenses.
    games_played = weeks with a stat row; team_id = latest week's team.
    Returns the number of season rows upserted.
    """
    upserted = 0
    placeholders = ','.join('?' for _ in positions)
    for season in seasons:
        rows = db.fetchall(
            f"""
            SELECT player_id,
                   COUNT(*) AS games_played,
                   SUM(fantasy_points_ppr) AS fp_ppr,
                   SUM(fantasy_points_standard) AS fp_std,
                   (SELECT team_id FROM player_weekly_stats w2
                     WHERE w2.player_id = w.player_id AND w2.season = w.season
                     ORDER BY w2.week DESC LIMIT 1) AS team_id
            FROM player_weekly_stats w
            WHERE season = ? AND position IN ({placeholders})
            GROUP BY player_id
            """,
            (season, *positions),
        )
        for r in rows:
            if r['team_id'] is None:
                continue
            db.upsert_player_season_stats({
                'player_id': r['player_id'],
                'team_id': r['team_id'],
                'season': season,
                'games_played': r['games_played'],
                'fantasy_points_ppr': round(r['fp_ppr'] or 0.0, 1),
                'fantasy_points_standard': round(r['fp_std'] or 0.0, 1),
            })
            upserted += 1
    db.commit()
    logger.info("K/DST season aggregates: %d rows for seasons %s", upserted, seasons)
    return upserted


def import_kicker_weekly_stats(db, years: List[int], df=None) -> int:
    """Persist kicker weekly rows into player_weekly_stats.

    Pass a pre-fetched stats_player_week frame via `df` to avoid a second
    download when the offense import already pulled it.
    """
    if df is None:
        df = fetch_stats_player_week(years)

    upserted = 0
    skipped = 0
    for row in build_kicker_week_rows(df):
        if not row['season'] or not row['week']:
            continue
        player_id = _match_player_id(db, row['full_name'], 'K')
        if player_id is None:
            skipped += 1
            continue
        team_abbr = _to_our_abbr(row['team_abbr']) if row['team_abbr'] else ''
        opp_abbr = _to_our_abbr(row['opp_abbr']) if row['opp_abbr'] else ''
        team_row = db.find_team(team_abbr) if team_abbr else None
        opp_row = db.find_team(opp_abbr) if opp_abbr else None
        db.upsert_player_weekly_stats({
            'player_id': player_id,
            'season': row['season'],
            'week': row['week'],
            'team_id': team_row['team_id'] if team_row else None,
            'opponent_team_id': opp_row['team_id'] if opp_row else None,
            'position': 'K',
            'fg_made_0_39': row['fg_made_0_39'],
            'fg_made_40_49': row['fg_made_40_49'],
            'fg_made_50_plus': row['fg_made_50_plus'],
            'fg_missed': row['fg_missed'],
            'xp_made': row['xp_made'],
            'xp_missed': row['xp_missed'],
            'fantasy_points_ppr': row['fantasy_points'],
            'fantasy_points_standard': row['fantasy_points'],
        })
        upserted += 1
    db.commit()
    logger.info("Kicker weekly stats: %d rows persisted, %d skipped (unmatched)",
                upserted, skipped)
    return upserted


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


def import_player_weekly_stats(db, years: List[int], df=None) -> int:
    """Fetch weekly stats from the nflverse feed and persist into player_weekly_stats.

    Returns the number of rows upserted. Non-matching players are skipped
    (they will appear later once rosters catch up). Pass a pre-fetched
    stats_player_week frame via `df` to skip the download.
    """
    if df is None:
        logger.info("Fetching weekly data for years %s …", years)
        df = fetch_stats_player_week(years)
    weekly = df[df['season_type'] == 'REG']

    # Snap counts (offensive) keyed by (player, season, week)
    snap_lookup: Dict[tuple, float] = {}
    try:
        import nfl_data_py as nfl
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
            'interceptions': int(row.get('passing_interceptions')
                                 if row.get('passing_interceptions') is not None
                                 else row.get('interceptions') or 0),
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
