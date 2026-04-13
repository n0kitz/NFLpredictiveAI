"""
Weekly scraper script.

Scrapes the current and previous season to catch any updates.
Designed to be run via cron every Wednesday.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import timedelta

from src.database.db import create_database
from src.scraper.pfr_scraper import PFRScraper
from src.scraper.odds_scraper import OddsScraper
from src.scraper.injury_scraper import InjuryScraper
from src.scraper.weather_scraper import WeatherScraper

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

    # Fetch upcoming odds (silently skip if ODDS_API_KEY not set)
    odds_api_key = os.environ.get("ODDS_API_KEY", "").strip()
    if odds_api_key:
        try:
            odds_scraper = OddsScraper()
            games_odds = odds_scraper.fetch_upcoming_odds(odds_api_key)
            stored = 0
            for g in games_odds:
                home_team = db.get_team_by_abbreviation(g["home_team"])
                away_team = db.get_team_by_abbreviation(g["away_team"])
                if not home_team or not away_team:
                    continue
                home_team_id = home_team["team_id"]
                away_team_id = away_team["team_id"]
                game_date = g["game_date"]
                db_game = db.fetchone(
                    """SELECT game_id FROM games
                       WHERE home_team_id=? AND away_team_id=?
                         AND date BETWEEN date(?,' -1 day') AND date(?,' +1 day')
                       LIMIT 1""",
                    (home_team_id, away_team_id, game_date, game_date),
                )
                db.upsert_game_odds({
                    "game_id":           db_game["game_id"] if db_game else None,
                    "external_game_id":  g["external_game_id"],
                    "home_team_id":      home_team_id,
                    "away_team_id":      away_team_id,
                    "game_date":         game_date,
                    "opening_spread":    g["spread"],
                    "over_under":        g["over_under"],
                    "home_implied_prob": g["home_implied_prob"],
                    "away_implied_prob": g["away_implied_prob"],
                    "fetched_at":        g["fetched_at"],
                })
                stored += 1
            logger.info(f"Odds fetch complete: {stored} game(s) stored")
            if odds_scraper.last_requests_remaining is not None:
                logger.info(
                    "API quota — used: %s, remaining: %s",
                    odds_scraper.last_requests_used,
                    odds_scraper.last_requests_remaining,
                )
        except Exception as e:
            logger.error(f"Odds fetch failed (non-fatal): {e}")
    else:
        logger.info("ODDS_API_KEY not set — skipping odds fetch")

    # Fetch injury reports and weather conditions
    try:
        inj_scraper = InjuryScraper()
        wx_scraper = WeatherScraper()

        all_injuries = inj_scraper.fetch_injuries()
        key_injuries = inj_scraper.filter_key_players(all_injuries)

        by_team: dict = {}
        for inj in key_injuries:
            by_team.setdefault(inj["team_abbr"], []).append(inj)

        inj_stored = 0
        for abbr, injuries in by_team.items():
            team = db.get_team_by_abbreviation(abbr)
            if team:
                db.upsert_injuries(team["team_id"], injuries)
                inj_stored += len(injuries)
        logger.info(f"Conditions: stored {inj_stored} key injury record(s)")

        today = datetime.now().date()
        window_end = today + timedelta(days=14)
        upcoming = db.fetchall(
            """
            SELECT g.game_id, g.date, g.home_team_id, t.abbreviation AS home_abbr
            FROM games g JOIN teams t ON g.home_team_id = t.team_id
            WHERE g.date BETWEEN ? AND ? AND g.home_score IS NULL
            ORDER BY g.date ASC
            """,
            (str(today), str(window_end)),
        )
        wx_stored = 0
        for row in upcoming:
            wx = wx_scraper.fetch_game_weather(row["home_abbr"], str(row["date"]))
            if wx is None:
                continue
            db.upsert_game_weather({
                "game_id":          row["game_id"],
                "home_team_id":     row["home_team_id"],
                "game_date":        str(row["date"]),
                "is_dome":          wx.get("is_dome", False),
                "temperature_c":    wx.get("temperature_c"),
                "wind_speed_kmh":   wx.get("wind_speed_kmh"),
                "precipitation_mm": wx.get("precipitation_mm"),
                "weather_code":     wx.get("weather_code"),
                "condition":        wx.get("condition", "Unknown"),
                "is_adverse":       wx.get("is_adverse", False),
                "fetched_at":       str(today),
            })
            wx_stored += 1
        logger.info(f"Conditions: stored weather for {wx_stored} upcoming game(s)")
    except Exception as e:
        logger.error(f"Conditions fetch failed (non-fatal): {e}")

    db.close()
    logger.info("Weekly scrape complete.")


if __name__ == "__main__":
    main()
