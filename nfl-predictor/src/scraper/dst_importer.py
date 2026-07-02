"""
Team-defense (DST) fantasy data built from the nflverse stats_player_week feed.

DST is modeled as 32 synthetic "players" (position='DST', espn_id='DST-{abbr}')
so the whole fantasy pipeline — rankings, projections, optimizer, trade values,
roster import — works through the existing players/roster_entries joins.

Weekly stats come from summing per-player defensive columns by (team, week):
sacks, interceptions, opponent-fumble recoveries, defensive TDs, safeties,
plus special-teams return TDs (credited to the returning team) and blocked
kicks (credited to the blocking defense via the opposing kicker's rows).
Points allowed comes from the games table.

NFL.com default DST scoring:
    sack +1, INT +2, fumble recovery +2, safety +2, def/ST TD +6, block +2,
    points allowed: 0 → +10, 1-6 → +7, 7-13 → +4, 14-20 → +1, 21-27 → 0,
    28-34 → -1, 35+ → -4.
"""

import logging
from typing import Any, Dict, List, Tuple

from .nfl_data_importer import _to_our_abbr

logger = logging.getLogger(__name__)


def dst_points_allowed_score(points_allowed: int) -> int:
    """NFL.com default points-allowed bracket score."""
    if points_allowed == 0:
        return 10
    if points_allowed <= 6:
        return 7
    if points_allowed <= 13:
        return 4
    if points_allowed <= 20:
        return 1
    if points_allowed <= 27:
        return 0
    if points_allowed <= 34:
        return -1
    return -4


def dst_fantasy_points(sacks: int, interceptions: int, fumbles_recovered: int,
                       tds: int, safeties: int, blocks: int,
                       points_allowed: int) -> float:
    """NFL.com default DST scoring (see module docstring)."""
    return float(
        sacks
        + 2 * interceptions
        + 2 * fumbles_recovered
        + 6 * tds
        + 2 * safeties
        + 2 * blocks
        + dst_points_allowed_score(points_allowed)
    )


def build_dst_week_rows(df, points_allowed: Dict[Tuple[str, int, int], int]
                        ) -> List[Dict[str, Any]]:
    """Aggregate a stats_player_week frame into per-team-week DST rows.

    `points_allowed` maps (team_abbr, season, week) — nflverse abbreviations —
    to points the defense allowed. Team-weeks missing from the lookup are
    skipped (no way to score them).
    """
    reg = df[df['season_type'] == 'REG']

    agg: Dict[Tuple[str, int, int], Dict[str, Any]] = {}

    def bucket(team: str, season: int, week: int) -> Dict[str, Any]:
        key = (team, season, week)
        if key not in agg:
            agg[key] = {
                'team_abbr': team, 'season': season, 'week': week,
                'opp_abbr': '', 'dst_sacks': 0.0, 'dst_interceptions': 0,
                'dst_fumbles_recovered': 0, 'dst_tds': 0, 'dst_safeties': 0,
                'dst_blocks': 0,
            }
        return agg[key]

    for _, r in reg.iterrows():
        team = str(r.get('team') or '').strip()
        opp = str(r.get('opponent_team') or '').strip()
        season = int(r.get('season') or 0)
        week = int(r.get('week') or 0)
        if not team or not season or not week:
            continue

        b = bucket(team, season, week)
        if opp:
            b['opp_abbr'] = opp
        b['dst_sacks'] += float(r.get('def_sacks') or 0.0)
        b['dst_interceptions'] += int(r.get('def_interceptions') or 0)
        b['dst_fumbles_recovered'] += int(r.get('fumble_recovery_opp') or 0)
        b['dst_tds'] += int(r.get('def_tds') or 0) + int(r.get('special_teams_tds') or 0)
        b['dst_safeties'] += int(r.get('def_safeties') or 0)

        # Blocked kicks live on the opposing kicker's row — credit the defense.
        blocked = int(r.get('fg_blocked') or 0) + int(r.get('pat_blocked') or 0)
        if blocked and opp:
            bucket(opp, season, week)['dst_blocks'] += blocked

    rows: List[Dict[str, Any]] = []
    for (team, season, week), b in agg.items():
        pa = points_allowed.get((team, season, week))
        if pa is None:
            continue
        sacks = int(round(b['dst_sacks']))
        rows.append({
            **b,
            'dst_sacks': sacks,
            'dst_points_allowed': int(pa),
            'fantasy_points': dst_fantasy_points(
                sacks, b['dst_interceptions'], b['dst_fumbles_recovered'],
                b['dst_tds'], b['dst_safeties'], b['dst_blocks'], int(pa)),
        })
    return rows


def ensure_dst_players(db, seasons: List[int]) -> int:
    """Create one synthetic DST player per active team plus roster entries.

    Idempotent: keyed on espn_id 'DST-{abbr}'. Returns the number of DST
    players newly created (0 on re-runs).
    """
    from datetime import datetime, timezone

    teams = db.fetchall(
        "SELECT team_id, city, name, abbreviation FROM teams "
        "WHERE active_until IS NULL", ()
    )
    created = 0
    fetched_at = datetime.now(timezone.utc).isoformat()
    for t in teams:
        espn_id = f"DST-{t['abbreviation']}"
        existing = db.fetchone(
            "SELECT player_id FROM players WHERE espn_id = ?", (espn_id,)
        )
        if existing:
            player_id = existing['player_id']
        else:
            full_name = f"{t['city']} {t['name']} DST"
            cursor = db.execute(
                "INSERT INTO players (espn_id, full_name, last_name, position) "
                "VALUES (?, ?, ?, 'DST')",
                (espn_id, full_name, t['name']),
            )
            player_id = cursor.lastrowid
            created += 1
        for season in seasons:
            db.execute(
                "INSERT OR REPLACE INTO roster_entries "
                "(player_id, team_id, season, roster_status, fetched_at) "
                "VALUES (?, ?, ?, 'Active', ?)",
                (player_id, t['team_id'], season, fetched_at),
            )
    db.commit()
    return created


def _points_allowed_lookup(db, years: List[int]) -> Dict[Tuple[str, int, int], int]:
    """Build {(nflverse_abbr, season, week): points_allowed} from the games table."""
    lookup: Dict[Tuple[str, int, int], int] = {}
    for season in years:
        rows = db.fetchall(
            """
            SELECT g.week, g.home_score, g.away_score,
                   ht.abbreviation AS home_abbr, at2.abbreviation AS away_abbr
            FROM games g
            JOIN teams ht ON ht.team_id = g.home_team_id
            JOIN teams at2 ON at2.team_id = g.away_team_id
            WHERE g.season = ? AND g.game_type = 'regular'
              AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL
            """,
            (season,),
        )
        for r in rows:
            try:
                week = int(r['week'])
            except (TypeError, ValueError):
                continue
            lookup[(r['home_abbr'], season, week)] = int(r['away_score'])
            lookup[(r['away_abbr'], season, week)] = int(r['home_score'])
    return lookup


def import_dst_weekly_stats(db, years: List[int], df=None) -> int:
    """Persist per-team-week DST rows into player_weekly_stats.

    Creates synthetic DST players as needed. Pass a pre-fetched
    stats_player_week frame via `df` to reuse the offense import's download.
    """
    if df is None:
        from .player_weekly_importer import fetch_stats_player_week
        df = fetch_stats_player_week(years)

    ensure_dst_players(db, years)

    # espn_id → player_id / team_id for the 32 DSTs
    dst_players: Dict[str, Dict[str, int]] = {}
    for r in db.fetchall(
        "SELECT p.player_id, t.team_id, t.abbreviation "
        "FROM players p JOIN teams t ON 'DST-' || t.abbreviation = p.espn_id "
        "WHERE p.position = 'DST'", ()
    ):
        dst_players[r['abbreviation']] = {
            'player_id': r['player_id'], 'team_id': r['team_id'],
        }

    pa_lookup_raw = _points_allowed_lookup(db, years)

    upserted = 0
    skipped = 0

    # The games-table lookup is keyed by our abbreviations; alias any nflverse
    # abbreviations that differ (e.g. LA → LAR) so frame rows match directly.
    pa_lookup: Dict[Tuple[str, int, int], int] = dict(pa_lookup_raw)
    frame_teams = {str(t) for t in df['team'].dropna().unique()}
    for t in frame_teams:
        mapped = _to_our_abbr(t)
        if mapped != t:
            for (our_abbr, season, week), pa in pa_lookup_raw.items():
                if our_abbr == mapped:
                    pa_lookup[(t, season, week)] = pa

    for row in build_dst_week_rows(df, pa_lookup):
        our_abbr = _to_our_abbr(row['team_abbr'])
        dst = dst_players.get(our_abbr)
        if dst is None:
            skipped += 1
            continue
        opp_abbr = _to_our_abbr(row['opp_abbr']) if row['opp_abbr'] else ''
        opp_row = db.find_team(opp_abbr) if opp_abbr else None
        db.upsert_player_weekly_stats({
            'player_id': dst['player_id'],
            'season': row['season'],
            'week': row['week'],
            'team_id': dst['team_id'],
            'opponent_team_id': opp_row['team_id'] if opp_row else None,
            'position': 'DST',
            'dst_sacks': row['dst_sacks'],
            'dst_interceptions': row['dst_interceptions'],
            'dst_fumbles_recovered': row['dst_fumbles_recovered'],
            'dst_tds': row['dst_tds'],
            'dst_safeties': row['dst_safeties'],
            'dst_blocks': row['dst_blocks'],
            'dst_points_allowed': row['dst_points_allowed'],
            'fantasy_points_ppr': row['fantasy_points'],
            'fantasy_points_standard': row['fantasy_points'],
        })
        upserted += 1

    db.commit()
    logger.info("DST weekly stats: %d rows persisted, %d skipped", upserted, skipped)
    return upserted
