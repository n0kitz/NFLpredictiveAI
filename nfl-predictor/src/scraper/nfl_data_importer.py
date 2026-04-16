"""Import advanced team stats from nfl_data_py (nflverse) play-by-play data."""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Columns to pull from the play-by-play endpoint — everything else is discarded
# immediately to keep memory usage low.
_PBP_COLS = [
    'game_id', 'season', 'season_type',
    'posteam', 'defteam',
    'play_type',
    'yards_gained',
    'pass_attempt', 'rush_attempt',
    'sack',
    'third_down_converted', 'third_down_failed',
    'yardline_100', 'touchdown',
    'interception',
    'fumble_lost',
]

# nfl-data-py uses nflverse abbreviations which differ from ours in several cases.
# Map nflverse → search term passed to db.find_team().
# Only entries that differ are listed; everything else is pass-through.
_NFL_DATA_TO_OUR: Dict[str, str] = {
    'LA':  'LAR',   # Los Angeles Rams (nflverse "LA", our DB "LAR")
    'JAC': 'JAX',   # Jacksonville Jaguars (nflverse "JAC", our DB "JAX")
    # Historical teams map to their historical abbreviations in our DB
    'OAK': 'OAK',   # Oakland Raiders (in our DB as historical team)
    'STL': 'STL',   # St. Louis Rams
    'SD':  'SD',    # San Diego Chargers
    # These are identical but listed explicitly for documentation
    'LV':  'LV',
    'LAC': 'LAC',
    'WAS': 'WAS',   # Washington (all eras use 'WAS' in nflverse)
}


def _to_our_abbr(nfl_abbr: str) -> str:
    """Map nflverse abbreviation to our DB search term."""
    return _NFL_DATA_TO_OUR.get(nfl_abbr, nfl_abbr)


def import_qb_epa(years: List[int]) -> List[Dict[str, Any]]:
    """
    Fetch QB EPA per pass play from nflverse play-by-play data.

    Filters to REG season pass plays (play_type == 'pass', qb_epa is not null).
    Groups by season + posteam (offense team), calculates mean qb_epa per play.

    Args:
        years: List of season years (e.g. [2013, ..., 2024])

    Returns:
        List of dicts: {season, nfl_abbr, our_abbr, qb_epa_per_play, pass_play_count}
    """
    try:
        import nfl_data_py as nfl
    except ImportError as exc:
        raise ImportError(
            "nfl_data_py is not installed. Run: pip install nfl-data-py"
        ) from exc

    _EPA_COLS = ['game_id', 'season', 'season_type', 'posteam', 'play_type', 'qb_epa']
    results: List[Dict[str, Any]] = []

    for year in years:
        logger.info("Fetching QB EPA PBP for %s ...", year)
        try:
            pbp = nfl.import_pbp_data([year], columns=_EPA_COLS)
        except Exception as exc:
            logger.warning("Failed to fetch PBP for QB EPA %s: %s", year, exc)
            continue

        reg = pbp[
            (pbp['season_type'] == 'REG') &
            (pbp['play_type'] == 'pass') &
            pbp['qb_epa'].notna() &
            pbp['posteam'].notna() &
            (pbp['posteam'] != '')
        ].copy()

        if reg.empty:
            logger.warning("No REG pass plays with qb_epa for %s", year)
            continue

        for team, group in reg.groupby('posteam'):
            epa_mean = float(group['qb_epa'].mean())
            count = int(len(group))
            results.append({
                'season':          year,
                'nfl_abbr':        team,
                'our_abbr':        _to_our_abbr(team),
                'qb_epa_per_play': round(epa_mean, 4),
                'pass_play_count': count,
            })

        logger.info("  → QB EPA: %d teams for %s", len(reg['posteam'].unique()), year)

    return results


def import_player_season_stats(years: List[int]) -> List[Dict[str, Any]]:
    """
    Fetch per-player per-season stats from nfl_data_py seasonal data.

    import_seasonal_data() only returns player_id + stat columns (no names,
    teams, or positions).  We merge it with import_seasonal_rosters() which
    carries player_name, position, team, and the same player_id key.

    Returns:
        List of dicts with: full_name, position, team_abbr, season,
        games, completions, attempts, passing_yards, passing_tds,
        interceptions, carries, rushing_yards, rushing_tds,
        targets, receptions, receiving_yards, receiving_tds,
        fantasy_points_ppr, fantasy_points_standard
    """
    try:
        import nfl_data_py as nfl
    except ImportError as exc:
        raise ImportError(
            "nfl_data_py is not installed. Run: pip install nfl-data-py"
        ) from exc

    try:
        df_stats = nfl.import_seasonal_data(years, s_type='REG')
    except Exception as exc:
        logger.warning("Failed to fetch seasonal data: %s", exc)
        return []

    # Merge with seasonal rosters to get player names, positions, and teams.
    # seasonal_rosters has one row per player per week; deduplicate to one row
    # per (player_id, season) by keeping the last (highest) week.
    try:
        df_roster = nfl.import_seasonal_rosters(years)
        df_roster = (
            df_roster
            .sort_values('week', na_position='last')
            .drop_duplicates(subset=['player_id', 'season'], keep='last')
        )
        # Build full name: prefer player_name field; fall back to first+last.
        df_roster['_full_name'] = df_roster['player_name'].fillna('')
        mask_empty = df_roster['_full_name'].str.strip() == ''
        df_roster.loc[mask_empty, '_full_name'] = (
            df_roster.loc[mask_empty, 'first_name'].fillna('') + ' '
            + df_roster.loc[mask_empty, 'last_name'].fillna('')
        ).str.strip()
        df = df_stats.merge(
            df_roster[['player_id', 'season', '_full_name', 'position', 'team']],
            on=['player_id', 'season'],
            how='left',
        )
        logger.info(
            "Merged %d stat rows with %d roster rows for years %s",
            len(df_stats), len(df_roster), years,
        )
    except Exception as exc:
        logger.warning("Roster merge failed: %s — name/team fields will be empty", exc)
        df = df_stats
        df['_full_name'] = ''
        df['position'] = ''
        df['team'] = ''

    results: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        try:
            full_name = str(row.get('_full_name', '') or '').strip()
            team_raw  = str(row.get('team', '') or '').strip()
            position  = str(row.get('position', '') or '').strip()
            results.append({
                'full_name':             full_name,
                'position':              position,
                'team_abbr':             _to_our_abbr(team_raw) if team_raw else '',
                'season':                int(row.get('season', 0)),
                'games':                 int(row.get('games', 0) or 0),
                'completions':           int(row.get('completions', 0) or 0),
                'attempts':              int(row.get('attempts', 0) or 0),
                'passing_yards':         int(row.get('passing_yards', 0) or 0),
                'passing_tds':           int(row.get('passing_tds', 0) or 0),
                'interceptions':         int(row.get('interceptions', 0) or 0),
                'carries':               int(row.get('carries', 0) or 0),
                'rushing_yards':         int(row.get('rushing_yards', 0) or 0),
                'rushing_tds':           int(row.get('rushing_tds', 0) or 0),
                'targets':               int(row.get('targets', 0) or 0),
                'receptions':            int(row.get('receptions', 0) or 0),
                'receiving_yards':       int(row.get('receiving_yards', 0) or 0),
                'receiving_tds':         int(row.get('receiving_tds', 0) or 0),
                'fantasy_points_ppr':    float(row.get('fantasy_points_ppr', 0.0) or 0.0),
                'fantasy_points_standard': float(row.get('fantasy_points', 0.0) or 0.0),
            })
        except Exception:
            continue

    logger.info("Fetched %d player-season rows for years %s", len(results), years)
    return results


def fetch_team_advanced_stats(years: List[int]) -> List[Dict[str, Any]]:
    """
    Fetch and aggregate team-level advanced stats from nflverse PBP data.

    Processes one season at a time to limit memory usage.  Only regular-season
    plays are included.

    Args:
        years: List of season years (e.g. [2010, 2011, ..., 2024])

    Returns:
        List of dicts, each with keys:
            season, nfl_abbr, our_abbr,
            turnover_margin, third_down_pct, redzone_efficiency,
            yards_per_play, sack_rate_allowed
    """
    try:
        import nfl_data_py as nfl
    except ImportError as exc:
        raise ImportError(
            "nfl_data_py is not installed. Run: pip install nfl-data-py"
        ) from exc

    all_results: List[Dict[str, Any]] = []

    for year in years:
        logger.info("Fetching PBP data for %s ...", year)
        try:
            pbp = nfl.import_pbp_data([year], columns=_PBP_COLS)
        except Exception as exc:
            logger.warning("Failed to fetch PBP for %s: %s", year, exc)
            continue

        # Regular season only, plays that have a possessing team
        reg = pbp[
            (pbp['season_type'] == 'REG') &
            pbp['posteam'].notna() &
            (pbp['posteam'] != '')
        ].copy()

        if reg.empty:
            logger.warning("No regular-season plays found for %s", year)
            continue

        teams = sorted(reg['posteam'].dropna().unique())

        for team in teams:
            off = reg[reg['posteam'] == team]   # plays where team had ball
            dfn = reg[reg['defteam'] == team]   # plays where team was on defense

            # ── Yards per play (offense) ──────────────────────────────────
            scrimmage = off[off['play_type'].isin(['pass', 'run'])]
            ypp = float(scrimmage['yards_gained'].mean()) if len(scrimmage) > 0 else 5.5

            # ── Third-down conversion rate ────────────────────────────────
            td3_conv  = int(off['third_down_converted'].sum())
            td3_fail  = int(off['third_down_failed'].sum())
            td3_total = td3_conv + td3_fail
            third_down_pct = td3_conv / td3_total if td3_total > 0 else 0.38

            # ── Red-zone efficiency (TD% on scrimmage plays inside opp 20) ─
            rz = off[
                (off['yardline_100'] <= 20) &
                off['play_type'].isin(['pass', 'run'])
            ]
            rz_tds  = int(rz['touchdown'].sum())
            rz_plays = len(rz)
            rz_eff   = rz_tds / rz_plays if rz_plays > 0 else 0.0

            # ── Turnovers ─────────────────────────────────────────────────
            giveaways = int(off['interception'].sum()) + int(off['fumble_lost'].sum())
            takeaways = int(dfn['interception'].sum()) + int(dfn['fumble_lost'].sum())
            turnover_margin = takeaways - giveaways

            # ── Sack rate allowed (sacks taken per dropback) ──────────────
            sacks_taken = int(off['sack'].sum())
            dropbacks   = int(off['pass_attempt'].sum()) + sacks_taken
            sack_rate   = sacks_taken / dropbacks if dropbacks > 0 else 0.07

            all_results.append({
                'season':             year,
                'nfl_abbr':           team,
                'our_abbr':           _to_our_abbr(team),
                'turnover_margin':    float(turnover_margin),
                'third_down_pct':     round(third_down_pct, 4),
                'redzone_efficiency': round(rz_eff, 4),
                'yards_per_play':     round(ypp, 4),
                'sack_rate_allowed':  round(sack_rate, 4),
            })

        logger.info("  → %d teams processed for %s", len(teams), year)

    return all_results
