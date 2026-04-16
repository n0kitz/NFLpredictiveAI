"""Tests for InjuryScraper and related constants."""

import pytest

from src.scraper.injury_scraper import (
    InjuryScraper,
    ESPN_TEAM_MAP,
    STADIUM_COORDS,
)


class TestKeyPlayerFilter:
    """filter_key_players() keeps position + significant status only."""

    def _make_injury(self, position: str, status: str, team: str = "KC") -> dict:
        return {
            "team_abbr": team,
            "player_name": "Test Player",
            "position": position,
            "injury_status": status,
            "report_date": "2026-04-13",
        }

    def test_keeps_key_position_significant_status(self):
        scraper = InjuryScraper()
        injuries = [self._make_injury("QB", "Out")]
        result = scraper.filter_key_players(injuries)
        assert len(result) == 1

    def test_drops_non_key_position(self):
        scraper = InjuryScraper()
        injuries = [self._make_injury("K", "Out")]
        result = scraper.filter_key_players(injuries)
        assert result == []

    def test_drops_questionable_status(self):
        scraper = InjuryScraper()
        injuries = [self._make_injury("WR", "Questionable")]
        result = scraper.filter_key_players(injuries)
        assert result == []

    def test_keeps_ir_status(self):
        scraper = InjuryScraper()
        injuries = [self._make_injury("RB", "IR")]
        result = scraper.filter_key_players(injuries)
        assert len(result) == 1

    def test_keeps_doubtful_status(self):
        scraper = InjuryScraper()
        injuries = [self._make_injury("TE", "Doubtful")]
        result = scraper.filter_key_players(injuries)
        assert len(result) == 1

    def test_mixed_list(self):
        scraper = InjuryScraper()
        injuries = [
            self._make_injury("QB", "Out"),
            self._make_injury("K", "Out"),        # dropped: non-key position
            self._make_injury("WR", "Questionable"),  # dropped: non-significant status
            self._make_injury("CB", "IR"),
        ]
        result = scraper.filter_key_players(injuries)
        assert len(result) == 2


class TestEspnMappingComplete:
    """ESPN_TEAM_MAP covers all 32 current teams (internal abbreviations)."""

    def test_all_32_teams_covered(self):
        """Every internal abbreviation in STADIUM_COORDS appears as a value in ESPN_TEAM_MAP."""
        internal_abbrs = set(STADIUM_COORDS.keys())
        mapped_abbrs = set(ESPN_TEAM_MAP.values())
        missing = internal_abbrs - mapped_abbrs
        assert missing == set(), f"Internal abbreviations not in ESPN_TEAM_MAP values: {missing}"

    def test_known_remaps(self):
        """ESPN-specific remaps are present."""
        assert ESPN_TEAM_MAP.get("JAC") == "JAX"
        assert ESPN_TEAM_MAP.get("LA") == "LAR"
        assert ESPN_TEAM_MAP.get("WSH") == "WAS"

    def test_stadium_coords_all_32(self):
        assert len(STADIUM_COORDS) == 32

    def test_dome_teams_flagged(self):
        dome_teams = {"ARI", "ATL", "DAL", "DET", "HOU", "IND", "LAC", "LAR", "LV", "MIN", "NO"}
        for abbr in dome_teams:
            assert abbr in STADIUM_COORDS, f"{abbr} missing from STADIUM_COORDS"
            _, _, is_dome = STADIUM_COORDS[abbr]
            assert is_dome, f"{abbr} should be flagged as dome"
