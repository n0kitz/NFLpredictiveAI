#!/usr/bin/env python3
"""
Import NFL schedule from ESPN public API.

Usage:
    cd nfl-predictor
    python scripts/import_schedule.py           # current season
    python scripts/import_schedule.py --season 2025
    python scripts/import_schedule.py --season 2025 --week 1  # single week
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.database.db import Database
from src.scraper.schedule_scraper import ScheduleScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def get_current_season() -> int:
    now = datetime.now()
    return now.year if now.month >= 9 else now.year - 1


def main():
    parser = argparse.ArgumentParser(description="Import NFL schedule from ESPN")
    parser.add_argument("--season", type=int, default=get_current_season())
    parser.add_argument("--week", type=int, default=None, help="Single week (1-18); omit for full season")
    args = parser.parse_args()

    db = Database()
    scraper = ScheduleScraper(db)

    if args.week:
        logger.info(f"Fetching season={args.season} week={args.week}")
        games = scraper.fetch_week(args.season, args.week)
        inserted, skipped = scraper.store_games(games)
    else:
        logger.info(f"Fetching full season={args.season} (regular + playoffs)")
        games = scraper.fetch_season(args.season)
        # Also calculate team season stats after bulk insert
        inserted, skipped = scraper.store_games(games)
        if inserted > 0:
            db.calculate_team_season_stats(args.season)
            logger.info(f"Recalculated team_season_stats for {args.season}")

    logger.info(f"Done — {inserted} inserted/updated, {skipped} skipped")
    db.close()


if __name__ == "__main__":
    main()
