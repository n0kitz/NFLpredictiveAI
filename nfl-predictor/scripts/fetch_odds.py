#!/usr/bin/env python3
"""Fetch upcoming NFL odds from The Odds API and store them in the database.

Usage:
    ODDS_API_KEY=<key> python scripts/fetch_odds.py

If ODDS_API_KEY is not set the script exits silently (non-zero exit code).
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.database.db import Database
from src.scraper.odds_scraper import OddsScraper


def main() -> int:
    api_key = os.environ.get("ODDS_API_KEY", "").strip()
    if not api_key:
        print("ODDS_API_KEY not set — skipping odds fetch.")
        return 1

    db = Database()
    scraper = OddsScraper()

    print("Fetching upcoming NFL odds from The Odds API...")
    games = scraper.fetch_upcoming_odds(api_key)

    if not games:
        print("No odds returned.")
        return 0

    matched = 0
    unmatched = 0

    for g in games:
        home_abbr = g["home_team"]
        away_abbr = g["away_team"]
        game_date = g["game_date"]

        home_team = db.get_team_by_abbreviation(home_abbr)
        away_team = db.get_team_by_abbreviation(away_abbr)

        if not home_team or not away_team:
            print(f"  UNRESOLVED: {away_abbr} @ {home_abbr} on {game_date}")
            unmatched += 1
            continue

        home_team_id = home_team["team_id"]
        away_team_id = away_team["team_id"]

        # Try to find a matching game in the DB (±1 day)
        db_game = db.fetchone(
            """
            SELECT game_id FROM games
            WHERE home_team_id = ? AND away_team_id = ?
              AND date BETWEEN date(?, '-1 day') AND date(?, '+1 day')
            LIMIT 1
            """,
            (home_team_id, away_team_id, game_date, game_date),
        )
        game_id = db_game["game_id"] if db_game else None

        db.upsert_game_odds({
            "game_id":          game_id,
            "external_game_id": g["external_game_id"],
            "home_team_id":     home_team_id,
            "away_team_id":     away_team_id,
            "game_date":        game_date,
            "opening_spread":   g["spread"],
            "over_under":       g["over_under"],
            "home_implied_prob": g["home_implied_prob"],
            "away_implied_prob": g["away_implied_prob"],
            "fetched_at":       g["fetched_at"],
        })
        matched += 1

    print(f"Stored odds for {matched} game(s). Unresolved: {unmatched}.")
    if scraper.last_requests_remaining is not None:
        print(
            f"API quota — used: {scraper.last_requests_used}, "
            f"remaining: {scraper.last_requests_remaining}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
