#!/usr/bin/env python3
"""
Import current NFL rosters and player season stats.

Step 1: ESPN roster API → players + roster_entries for current season
Step 2: nfl_data_py seasonal data → player_season_stats for 2022-2024

Run from nfl-predictor/ directory:
    python scripts/import_rosters.py
"""

import re
import sys
import difflib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

from src.database.db import Database
from src.scraper.roster_scraper import RosterScraper
from src.scraper.nfl_data_importer import import_player_season_stats

CURRENT_SEASON = datetime.now().year if datetime.now().month >= 9 else datetime.now().year - 1
STAT_SEASONS = [2022, 2023, 2024]

# ── Name normalisation helpers ────────────────────────────────────────────────

_SUFFIXES = {'jr', 'sr', 'ii', 'iii', 'iv', 'v'}


def normalize_name(name: str) -> str:
    """Lowercase, strip non-alpha chars, remove trailing Jr/II/etc., collapse spaces."""
    cleaned = re.sub(r'[^a-z\s]', '', name.lower())
    tokens = cleaned.split()
    while tokens and tokens[-1] in _SUFFIXES:
        tokens.pop()
    return ' '.join(tokens)


def extract_last_name(name: str) -> str:
    """Return last name (lowercase) from 'First Last', 'F.Last', 'First Last Jr.' etc."""
    # Strip punctuation and split
    tokens = re.sub(r'[^a-z\s]', '', name.lower()).split()
    while tokens and tokens[-1] in _SUFFIXES:
        tokens.pop()
    if not tokens:
        return ''
    last = tokens[-1]
    # Handle "flast" left after stripping a dot abbreviation like "T.Kelce" → "tkelce"
    # In that case tokens would be ['tkelce'] — keep it as-is (best we can do).
    return last


# ── In-memory DB lookup builder ───────────────────────────────────────────────

def build_db_lookups(db: Database) -> Tuple[Dict, Dict, List[str]]:
    """
    Return three structures built from the players table:

    by_norm  : {normalize(full_name): [{'player_id', 'full_name', 'position'}, ...]}
    by_last  : {(last_name, POSITION): [{'player_id', 'full_name'}, ...]}
    all_norms: flat list of all normalized names (for difflib)
    """
    rows = db.fetchall(
        "SELECT player_id, full_name, position FROM players", ()
    )
    by_norm: Dict[str, List[Dict]] = {}
    by_last: Dict[Tuple[str, str], List[Dict]] = {}
    all_norms: List[str] = []

    for r in rows:
        pid   = r['player_id']
        fname = r['full_name'] or ''
        pos   = (r['position'] or '').upper()
        norm  = normalize_name(fname)
        last  = extract_last_name(fname)

        entry = {'player_id': pid, 'full_name': fname, 'position': pos}

        by_norm.setdefault(norm, []).append(entry)
        if last:
            by_last.setdefault((last, pos), []).append(entry)

        all_norms.append(norm)

    return by_norm, by_last, all_norms


# ── 3-tier player matcher ─────────────────────────────────────────────────────

def match_player(
    full_name: str,
    position: str,
    by_norm: Dict,
    by_last: Dict,
    all_norms: List[str],
) -> Tuple[Optional[int], Optional[str]]:
    """
    Try three matching strategies in order.

    Returns (player_id, strategy_label) or (None, None).
    """
    if not full_name:
        return None, None

    pos = position.upper() if position else ''
    norm = normalize_name(full_name)

    # ── Strategy 1: exact normalized name ─────────────────────────────────────
    candidates = by_norm.get(norm, [])
    if candidates:
        if len(candidates) == 1:
            return candidates[0]['player_id'], 'exact'
        # Disambiguate by position
        if pos:
            pos_match = [c for c in candidates if c['position'] == pos]
            if len(pos_match) == 1:
                return pos_match[0]['player_id'], 'exact'
        return candidates[0]['player_id'], 'exact'

    # ── Strategy 2: last name + position ──────────────────────────────────────
    last = extract_last_name(full_name)
    if last and pos:
        hits = by_last.get((last, pos), [])
        if len(hits) == 1:
            return hits[0]['player_id'], 'lastname'

    # ── Strategy 3: fuzzy match (difflib) ─────────────────────────────────────
    close = difflib.get_close_matches(norm, all_norms, n=3, cutoff=0.85)
    if len(close) == 1:
        candidates = by_norm.get(close[0], [])
        if candidates:
            return candidates[0]['player_id'], 'fuzzy'
    elif close:
        # Multiple close — try position to pick one
        all_candidates = [c for k in close for c in by_norm.get(k, [])]
        if pos:
            pos_match = [c for c in all_candidates if c['position'] == pos]
            if len(pos_match) == 1:
                return pos_match[0]['player_id'], 'fuzzy'

    return None, None


# ── Passer rating (NFL formula) ───────────────────────────────────────────────

def _passer_rating(comp: int, att: int, yds: int, tds: int, ints: int) -> float:
    if att == 0:
        return 0.0
    a = max(0.0, min(((comp / att) - 0.3) * 5, 2.375))
    b = max(0.0, min(((yds / att) - 3) * 0.25, 2.375))
    c = max(0.0, min((tds / att) * 20, 2.375))
    d = max(0.0, min(2.375 - ((ints / att) * 25), 2.375))
    return round(((a + b + c + d) / 6) * 100, 1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    db = Database()

    print("=" * 60)
    print("  NFL Roster Importer")
    print(f"  Current season:  {CURRENT_SEASON}")
    print(f"  Stat seasons:    {STAT_SEASONS}")
    print("=" * 60)

    # ── Step 1: ESPN rosters ──────────────────────────────────────────────────
    print(f"\n[1/2] Fetching rosters from ESPN for all 32 teams (season {CURRENT_SEASON})…")
    scraper = RosterScraper(request_delay=1.0)
    all_rosters = scraper.fetch_all_rosters()

    players_upserted = 0
    roster_entries_upserted = 0
    fetched_at = datetime.utcnow().isoformat()

    for team_abbr, players in all_rosters.items():
        team = db.find_team(team_abbr)
        if not team:
            logger.warning("Team not found in DB: %s", team_abbr)
            continue

        team_id = team['team_id']

        for player in players:
            if not player.get('espn_id') or not player.get('full_name'):
                continue
            try:
                player_id = db.upsert_player(player)
                db.upsert_roster_entry({
                    'player_id':     player_id,
                    'team_id':       team_id,
                    'season':        CURRENT_SEASON,
                    'roster_status': player.get('status', 'Active'),
                    'fetched_at':    fetched_at,
                })
                players_upserted += 1
                roster_entries_upserted += 1
            except Exception as exc:
                logger.debug("Failed to upsert %s: %s", player.get('full_name'), exc)

    db.commit()
    print(f"  Players upserted:        {players_upserted}")
    print(f"  Roster entries upserted: {roster_entries_upserted}")

    # ── Step 2: nfl_data_py player season stats ───────────────────────────────
    print(f"\n[2/2] Importing player season stats from nfl_data_py (seasons {STAT_SEASONS})…")
    try:
        player_rows = import_player_season_stats(STAT_SEASONS)
    except ImportError as exc:
        print(f"  ERROR: {exc}")
        print("  Skipping player stats import.")
        db.close()
        return

    # ── Diagnostic: reveal the actual name formats ────────────────────────────
    print("\n--- DIAGNOSTIC ---")
    print("First 10 nfl_data_py rows:")
    for r in player_rows[:10]:
        print(f"  full_name={r.get('full_name', '')!r:30s}  "
              f"team={r.get('team_abbr', '')!r:6s}  season={r.get('season', '')}")

    db_sample = db.fetchall("SELECT full_name FROM players LIMIT 10", ())
    print("First 10 DB player names:")
    for r in db_sample:
        print(f"  {r['full_name']!r}")
    print("--- END DIAGNOSTIC ---\n")

    # ── Build in-memory lookups from the players table ────────────────────────
    by_norm, by_last, all_norms = build_db_lookups(db)
    print(f"  DB lookup built: {len(by_norm)} unique normalized names, "
          f"{len(by_last)} (lastname, pos) pairs")

    # ── Match and upsert ──────────────────────────────────────────────────────
    stats_upserted   = 0
    matched_exact    = 0
    matched_lastname = 0
    matched_fuzzy    = 0
    unmatched: List[str] = []
    skipped_no_name  = 0

    for row in player_rows:
        full_name = row.get('full_name', '').strip()
        season    = row.get('season', 0)
        position  = row.get('position', '')

        if not full_name or not season:
            skipped_no_name += 1
            continue

        player_id, strategy = match_player(
            full_name, position, by_norm, by_last, all_norms
        )

        if player_id is None:
            unmatched.append(f"{season}/{full_name}/{position}/{row.get('team_abbr','')}")
            continue

        # Resolve team for the stat entry; fall back to any team that has a
        # roster entry for this player if the nfl_data_py team isn't in DB.
        team_abbr = row.get('team_abbr', '')
        team      = db.find_team(team_abbr) if team_abbr else None
        if not team:
            # Try to look up via roster_entries
            re_row = db.fetchone(
                "SELECT team_id FROM roster_entries WHERE player_id=? LIMIT 1",
                (player_id,),
            )
            team_id = re_row['team_id'] if re_row else None
        else:
            team_id = team['team_id']

        if not team_id:
            unmatched.append(
                f"{season}/{full_name}/{position}/{team_abbr} [no team]"
            )
            continue

        pass_att  = row.get('attempts', 0)
        pass_comp = row.get('completions', 0)
        pass_yds  = row.get('passing_yards', 0)
        pass_tds  = row.get('passing_tds', 0)
        ints      = row.get('interceptions', 0)
        rush_att  = row.get('carries', 0)
        rush_yds  = row.get('rushing_yards', 0)
        rec       = row.get('receptions', 0)
        rec_yds   = row.get('receiving_yards', 0)

        try:
            db.upsert_player_season_stats({
                'player_id':               player_id,
                'team_id':                 team_id,
                'season':                  season,
                'games_played':            row.get('games', 0),
                'pass_attempts':           pass_att,
                'pass_completions':        pass_comp,
                'pass_yards':              pass_yds,
                'pass_tds':                pass_tds,
                'interceptions':           ints,
                'passer_rating':           _passer_rating(pass_comp, pass_att, pass_yds, pass_tds, ints),
                'rush_attempts':           rush_att,
                'rush_yards':              rush_yds,
                'rush_tds':                row.get('rushing_tds', 0),
                'yards_per_carry':         round(rush_yds / rush_att, 2) if rush_att else 0.0,
                'targets':                 row.get('targets', 0),
                'receptions':              rec,
                'rec_yards':               rec_yds,
                'rec_tds':                 row.get('receiving_tds', 0),
                'yards_per_reception':     round(rec_yds / rec, 2) if rec else 0.0,
                'fantasy_points_ppr':      row.get('fantasy_points_ppr', 0.0),
                'fantasy_points_standard': row.get('fantasy_points_standard', 0.0),
            })
            stats_upserted += 1
            if strategy == 'exact':
                matched_exact += 1
            elif strategy == 'lastname':
                matched_lastname += 1
            elif strategy == 'fuzzy':
                matched_fuzzy += 1
        except Exception as exc:
            logger.debug("Failed to upsert stats for %s: %s", full_name, exc)

    db.commit()

    # ── Write unmatched log ───────────────────────────────────────────────────
    unmatched_path = ROOT / "data" / "unmatched_players.txt"
    with open(unmatched_path, 'w') as fh:
        for line in sorted(unmatched):
            fh.write(line + '\n')

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"  Matched via exact name:     {matched_exact}")
    print(f"  Matched via last name+pos:  {matched_lastname}")
    print(f"  Matched via fuzzy:          {matched_fuzzy}")
    print(f"  Unmatched (logged to file): {len(unmatched)}")
    print(f"  Stat rows upserted:         {stats_upserted}")
    if skipped_no_name:
        print(f"  Skipped (no name/season):  {skipped_no_name}")
    print(f"\n  Unmatched log: {unmatched_path}")

    db.close()
    print("\nRoster import complete.")


if __name__ == "__main__":
    main()
