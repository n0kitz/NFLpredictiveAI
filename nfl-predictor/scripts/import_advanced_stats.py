#!/usr/bin/env python3
"""
Import advanced team stats from nflverse (nfl_data_py) into team_advanced_stats.

Run from nfl-predictor/ directory:
    python scripts/import_advanced_stats.py

Downloads play-by-play data for each season (one at a time) and aggregates:
  turnover_margin, third_down_pct, redzone_efficiency,
  yards_per_play, sack_rate_allowed

Data is stored in the team_advanced_stats table (INSERT OR REPLACE).
"""

import sys
import logging
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

from src.database.db import Database
from src.scraper.nfl_data_importer import (
    fetch_team_advanced_stats,
    import_qb_epa,
    import_weekly_qb_starts,
)

YEARS = list(range(2010, 2025))   # 2010 – 2024 inclusive


def main() -> None:
    db = Database()

    print("=" * 60)
    print("  NFL Advanced Stats Importer (nfl_data_py)")
    print(f"  Seasons: {min(YEARS)} – {max(YEARS)}")
    print("  Includes: team advanced stats + QB EPA per play + weekly QB starts")
    print("=" * 60)
    print()
    print("[1/3] Importing team advanced stats...")

    try:
        stats = fetch_team_advanced_stats(YEARS)
    except ImportError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    if not stats:
        print("No stats returned — check nfl_data_py connectivity.")
        sys.exit(1)

    inserted   = 0
    unresolved: list[str] = []

    for row in stats:
        team = db.find_team(row['our_abbr'])
        if not team:
            # Second-chance: try the raw nflverse abbr
            team = db.find_team(row['nfl_abbr'])

        if not team:
            unresolved.append(f"{row['season']}/{row['nfl_abbr']}")
            continue

        db.upsert_advanced_stats(team['team_id'], row['season'], row)
        inserted += 1

    db.commit()

    # ── QB EPA import ─────────────────────────────────────────────────────────
    print("\n[2/3] Importing QB EPA per play...")
    try:
        qb_epa_rows = import_qb_epa(YEARS)
        qb_inserted = 0
        qb_unresolved: list[str] = []
        for row in qb_epa_rows:
            team = db.find_team(row['our_abbr'])
            if not team:
                team = db.find_team(row['nfl_abbr'])
            if not team:
                qb_unresolved.append(f"{row['season']}/{row['nfl_abbr']}")
                continue
            # Update only qb_epa_per_play — merge into existing row
            db.execute(
                """
                INSERT INTO team_advanced_stats (team_id, season, qb_epa_per_play)
                VALUES (?, ?, ?)
                ON CONFLICT(team_id, season) DO UPDATE SET
                    qb_epa_per_play = excluded.qb_epa_per_play
                """,
                (team['team_id'], row['season'], row['qb_epa_per_play']),
            )
            qb_inserted += 1
        db.commit()
        print(f"  QB EPA rows updated: {qb_inserted}")
        if qb_unresolved:
            print(f"  Unresolved: {sorted(set(qb_unresolved))}")
    except Exception as exc:
        print(f"  QB EPA import failed (non-fatal): {exc}")

    print()
    print("Import complete")
    print(f"  Advanced stats rows inserted / updated : {inserted}")
    print(f"  Unresolved team abbrvs                 : {len(unresolved)}")

    if unresolved:
        print("\n  Unresolved entries (season/nflverse_abbr):")
        for entry in sorted(set(unresolved)):
            print(f"    {entry}")

    # Quick sanity check
    sample = db.fetchall(
        "SELECT season, COUNT(*) AS n FROM team_advanced_stats GROUP BY season ORDER BY season DESC LIMIT 5"
    )
    if sample:
        print("\n  Latest seasons in DB:")
        for row in sample:
            print(f"    {row['season']}: {row['n']} teams")

    # ── Weekly QB starts ───────────────────────────────────────────────────────
    print("\n[3/3] Importing weekly QB starts (rolling EPA)...")
    try:
        wqb_inserted = import_weekly_qb_starts(db, YEARS)
        print(f"  weekly_qb_starts rows inserted / updated: {wqb_inserted}")

        wqb_sample = db.fetchall(
            "SELECT season, COUNT(*) AS n FROM weekly_qb_starts GROUP BY season ORDER BY season DESC LIMIT 5"
        )
        if wqb_sample:
            print("\n  Latest seasons in weekly_qb_starts:")
            for row in wqb_sample:
                print(f"    {row['season']}: {row['n']} game-team rows")
    except Exception as exc:
        print(f"  Weekly QB starts import failed (non-fatal): {exc}")

    db.close()


if __name__ == "__main__":
    main()
