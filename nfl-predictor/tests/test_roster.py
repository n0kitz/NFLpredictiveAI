"""Tests for the roster DB methods."""

import pytest
from pathlib import Path

from src.database.db import Database, DEFAULT_DB_PATH

# Skip if no real database
pytestmark = pytest.mark.skipif(
    not DEFAULT_DB_PATH.exists(),
    reason="Real database not found — run scraper first",
)


@pytest.fixture(scope="module")
def db():
    database = Database(DEFAULT_DB_PATH)
    yield database
    database.close()


class TestPlayerUpsert:
    def test_upsert_and_retrieve_player(self, db: Database):
        """Upserting a player then fetching by espn_id returns the same record."""
        player_data = {
            "espn_id": "TEST_ESPN_999",
            "full_name": "Test Player",
            "first_name": "Test",
            "last_name": "Player",
            "position": "QB",
            "jersey_number": "0",
            "date_of_birth": None,
            "height_cm": 190.5,
            "weight_kg": 102.0,
            "college": "Test University",
            "experience_years": 3,
            "status": "Active",
            "headshot_url": None,
        }
        player_id = db.upsert_player(player_data)
        assert isinstance(player_id, int)
        assert player_id > 0

        fetched = db.get_player_by_espn_id("TEST_ESPN_999")
        assert fetched is not None
        assert fetched["full_name"] == "Test Player"
        assert fetched["position"] == "QB"


class TestRosterEntry:
    def test_upsert_roster_entry(self, db: Database):
        """Upserting a roster entry succeeds without error."""
        player_data = {
            "espn_id": "TEST_ESPN_998",
            "full_name": "Roster Tester",
            "first_name": "Roster",
            "last_name": "Tester",
            "position": "WR",
            "jersey_number": "88",
            "date_of_birth": None,
            "height_cm": 183.0,
            "weight_kg": 88.0,
            "college": None,
            "experience_years": 1,
            "status": "Active",
            "headshot_url": None,
        }
        player_id = db.upsert_player(player_data)

        # Use the first real team in the DB
        teams = db.fetchall("SELECT team_id FROM teams LIMIT 1", ())
        assert teams, "No teams in database"
        team_id = teams[0]["team_id"]

        db.upsert_roster_entry({
            "player_id": player_id,
            "team_id": team_id,
            "season": 2024,
            "depth_position": None,
            "is_starter": False,
            "roster_status": "Active",
        })

        roster = db.get_team_roster(team_id, season=2024)
        player_ids = [p["player_id"] for p in roster]
        assert player_id in player_ids


class TestPlayerStats:
    def test_upsert_and_get_player_stats(self, db: Database):
        """Upserting stats then reading them back returns correct values."""
        player_data = {
            "espn_id": "TEST_ESPN_997",
            "full_name": "Stats Tester",
            "first_name": "Stats",
            "last_name": "Tester",
            "position": "QB",
            "jersey_number": "7",
            "date_of_birth": None,
            "height_cm": 188.0,
            "weight_kg": 100.0,
            "college": None,
            "experience_years": 5,
            "status": "Active",
            "headshot_url": None,
        }
        player_id = db.upsert_player(player_data)

        teams = db.fetchall("SELECT team_id FROM teams LIMIT 1", ())
        team_id = teams[0]["team_id"]

        db.upsert_player_season_stats({
            "player_id": player_id,
            "team_id": team_id,
            "season": 2024,
            "games_played": 16,
            "pass_attempts": 500,
            "pass_completions": 330,
            "pass_yards": 4200,
            "pass_tds": 32,
            "interceptions": 10,
            "passer_rating": 101.5,
            "rush_attempts": 50,
            "rush_yards": 250,
            "rush_tds": 3,
            "yards_per_carry": 5.0,
            "targets": 0,
            "receptions": 0,
            "rec_yards": 0,
            "rec_tds": 0,
            "yards_per_reception": 0.0,
            "fantasy_points_ppr": 340.5,
            "fantasy_points_standard": 340.5,
        })

        stats = db.get_player_stats(player_id, season=2024)
        assert stats is not None
        assert stats["pass_yards"] == 4200
        assert stats["pass_tds"] == 32


class TestStartersOrdering:
    def test_starters_come_before_backups(self, db: Database):
        """get_team_starters returns starters with is_starter=True before backups."""
        teams = db.fetchall("SELECT team_id FROM teams LIMIT 1", ())
        team_id = teams[0]["team_id"]

        roster = db.get_team_starters(team_id, season=2024)
        # If any starters exist, they should appear first
        if len(roster) > 1:
            starter_indices = [i for i, p in enumerate(roster) if p.get("is_starter")]
            backup_indices = [i for i, p in enumerate(roster) if not p.get("is_starter")]
            if starter_indices and backup_indices:
                assert max(starter_indices) < min(backup_indices), (
                    "Starters should precede backups in get_team_starters()"
                )
