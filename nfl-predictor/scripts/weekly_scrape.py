"""
Weekly scraper script.

Scrapes the current and previous season to catch any updates.
Designed to be run via cron every Wednesday.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.db import create_database
from src.scraper.pfr_scraper import PFRScraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def get_current_nfl_season() -> int:
    """NFL season year: Sept-Dec = current year, Jan-Aug = previous year."""
    now = datetime.now()
    return now.year if now.month >= 9 else now.year - 1


def main():
    current_season = get_current_nfl_season()
    start = current_season - 1  # Also refresh prior season for corrections
    end = current_season

    logger.info(f"Weekly scrape: seasons {start}–{end}")

    db = create_database()
    scraper = PFRScraper(db, rate_limit=4.0)
    scraper.initialize_teams()

    # Force re-scrape current season (don't skip completed)
    for season in range(start, end + 1):
        logger.info(f"Scraping season {season}...")
        try:
            games = scraper.scrape_season_schedule(season)
            if games:
                inserted, skipped = scraper.store_games(games)
                db.calculate_team_season_stats(season)
                db.update_scrape_status(season, 'full', 'completed')
                logger.info(f"Season {season}: {inserted} inserted, {skipped} skipped")
            else:
                logger.warning(f"No games found for season {season}")
        except Exception as e:
            logger.error(f"Error scraping season {season}: {e}")

    # Enrich prediction history with completed game results
    try:
        enriched = db.enrich_prediction_history()
        if enriched:
            logger.info(f"Enriched {enriched} prediction(s) with game results")
    except Exception as e:
        logger.error(f"Error enriching prediction history: {e}")

    db.close()
    logger.info("Weekly scrape complete.")


if __name__ == "__main__":
    main()
