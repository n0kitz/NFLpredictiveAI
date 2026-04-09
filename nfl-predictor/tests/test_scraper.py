"""Scraper tests — HTML parsing and team mapping resolution."""

import pytest
from pathlib import Path

from src.scraper.pfr_scraper import PFRScraper
from src.scraper.team_mappings import PFR_TEAM_ABBR_MAP, TeamMappings, CURRENT_TEAMS
from src.database.db import Database

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_html():
    return (FIXTURES_DIR / "sample_pfr_games.htm").read_text(encoding="utf-8")


@pytest.fixture
def scraper(tmp_path):
    db = Database(tmp_path / "test.db")
    db.init_schema()
    s = PFRScraper(db)
    s.initialize_teams()
    return s


# ── HTML Parsing ──────────────────────────────────────


class TestHTMLParsing:
    def test_parse_season_from_html(self, scraper, sample_html):
        games = scraper.parse_season_from_html(sample_html, 2024)
        assert len(games) == 4

    def test_game_fields(self, scraper, sample_html):
        games = scraper.parse_season_from_html(sample_html, 2024)
        g = games[0]  # KC vs BAL
        assert g.season == 2024
        assert g.week == "1"
        assert g.game_type == "regular"
        assert g.home_score == 27
        assert g.away_score == 20
        assert g.overtime is False

    def test_away_game_parsing(self, scraper, sample_html):
        """PHI @ DAL — winner column shows PHI with @ indicator."""
        games = scraper.parse_season_from_html(sample_html, 2024)
        g = games[1]
        assert g.home_team_pfr == "dal"
        assert g.away_team_pfr == "phi"
        assert g.home_score == 29
        assert g.away_score == 34
        assert g.overtime is True

    def test_playoff_game_parsed(self, scraper, sample_html):
        games = scraper.parse_season_from_html(sample_html, 2024)
        playoff_games = [g for g in games if g.game_type == "playoff"]
        assert len(playoff_games) == 1
        assert playoff_games[0].week == "Wild Card"

    def test_header_rows_skipped(self, scraper, sample_html):
        """The fixture has a thead row in the middle; it should be skipped."""
        games = scraper.parse_season_from_html(sample_html, 2024)
        assert len(games) == 4

    def test_date_parsing(self, scraper, sample_html):
        games = scraper.parse_season_from_html(sample_html, 2024)
        assert games[0].date == "2024-09-05"
        # January game should be 2025
        playoff = [g for g in games if g.game_type == "playoff"][0]
        assert playoff.date == "2025-01-11"

    def test_store_games(self, scraper, sample_html):
        games = scraper.parse_season_from_html(sample_html, 2024)
        inserted, skipped = scraper.store_games(games)
        assert inserted == 4
        assert skipped == 0


# ── Team Mappings ─────────────────────────────────────


class TestTeamMappingResolution:
    def test_pfr_map_covers_all_current_teams(self):
        for team in CURRENT_TEAMS:
            if team.pfr_abbr:
                assert team.pfr_abbr in PFR_TEAM_ABBR_MAP, (
                    f"{team.abbreviation} pfr_abbr '{team.pfr_abbr}' not in PFR_TEAM_ABBR_MAP"
                )

    def test_pfr_map_returns_valid_abbr(self):
        for pfr, nfl in PFR_TEAM_ABBR_MAP.items():
            abbrs = [t.abbreviation for t in CURRENT_TEAMS]
            assert nfl in abbrs, f"PFR map value '{nfl}' for key '{pfr}' not a valid team abbr"

    def test_mappings_find_all_32(self):
        mappings = TeamMappings()
        for team in CURRENT_TEAMS:
            found = mappings.find_team(team.abbreviation)
            assert found is not None, f"Cannot find {team.abbreviation}"

    def test_historical_abbreviations(self):
        """Some historical PFR abbreviations should map to current teams."""
        assert PFR_TEAM_ABBR_MAP.get("sdg") == "LAC"  # San Diego → LA Chargers
        assert PFR_TEAM_ABBR_MAP.get("rai") == "LV"   # Raiders → Las Vegas
