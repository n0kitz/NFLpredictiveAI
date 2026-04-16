#!/usr/bin/env python3
"""Fetch injury reports and game weather, then store them in the database.

Usage:
    python scripts/fetch_conditions.py

Injuries: ESPN public API (no auth required).
Weather:  Open-Meteo (no auth required).
Both are display-only enrichment — never used as prediction inputs.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.database.db import Database
from src.scraper.injury_scraper import InjuryScraper, STADIUM_COORDS
from src.scraper.weather_scraper import WeatherScraper


def main() -> int:
    db = Database()
    inj_scraper = InjuryScraper()
    wx_scraper = WeatherScraper()

    # ── Injuries ──────────────────────────────────────────
    print("Fetching injury reports from ESPN...")
    all_injuries = inj_scraper.fetch_injuries()
    key_injuries = inj_scraper.filter_key_players(all_injuries)

    # Group by team abbreviation
    by_team: dict[str, list[dict]] = {}
    for inj in key_injuries:
        abbr = inj["team_abbr"]
        by_team.setdefault(abbr, []).append(inj)

    inj_stored = 0
    for abbr, injuries in by_team.items():
        team = db.get_team_by_abbreviation(abbr)
        if not team:
            continue
        db.upsert_injuries(team["team_id"], injuries)
        inj_stored += len(injuries)

    print(f"Stored {inj_stored} key injury record(s) across {len(by_team)} team(s).")

    # ── Weather for upcoming games (next 14 days) ─────────
    today = date.today()
    window_end = today + timedelta(days=14)

    upcoming = db.fetchall(
        """
        SELECT g.game_id, g.date, g.home_team_id, t.abbreviation AS home_abbr
        FROM games g
        JOIN teams t ON g.home_team_id = t.team_id
        WHERE g.date BETWEEN ? AND ?
          AND g.home_score IS NULL
        ORDER BY g.date ASC
        """,
        (str(today), str(window_end)),
    )

    print(f"Fetching weather for {len(upcoming)} upcoming game(s)...")
    wx_stored = 0
    wx_skipped = 0

    for row in upcoming:
        game_id = row["game_id"]
        game_date = str(row["date"])
        home_team_id = row["home_team_id"]
        home_abbr = row["home_abbr"]

        wx = wx_scraper.fetch_game_weather(home_abbr, game_date)
        if wx is None:
            wx_skipped += 1
            continue

        db.upsert_game_weather({
            "game_id":         game_id,
            "home_team_id":    home_team_id,
            "game_date":       game_date,
            "is_dome":         wx.get("is_dome", False),
            "temperature_c":   wx.get("temperature_c"),
            "wind_speed_kmh":  wx.get("wind_speed_kmh"),
            "precipitation_mm": wx.get("precipitation_mm"),
            "weather_code":    wx.get("weather_code"),
            "condition":       wx.get("condition", "Unknown"),
            "is_adverse":      wx.get("is_adverse", False),
            "fetched_at":      str(today),
        })
        wx_stored += 1

    print(f"Stored weather for {wx_stored} game(s). Skipped: {wx_skipped}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
