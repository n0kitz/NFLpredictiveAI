"""Tests for WeatherScraper dome logic and WMO code mapping."""

import pytest

from src.scraper.weather_scraper import WeatherScraper, _wmo_condition
from src.scraper.injury_scraper import STADIUM_COORDS


class TestDomeReturnsImmediately:
    """Dome teams should return immediately without making any HTTP call."""

    # Pick a representative set of dome teams
    DOME_TEAMS = ["ATL", "DET", "IND", "MIN", "NO", "LV", "DAL", "ARI", "HOU", "LAR", "LAC"]

    def test_dome_teams_return_is_dome_true(self):
        scraper = WeatherScraper()
        for abbr in self.DOME_TEAMS:
            result = scraper.fetch_game_weather(abbr, "2026-09-07")
            assert result is not None, f"Expected result for dome team {abbr}, got None"
            assert result["is_dome"] is True, f"{abbr} should have is_dome=True"

    def test_dome_result_has_expected_keys(self):
        scraper = WeatherScraper()
        result = scraper.fetch_game_weather("ATL", "2026-09-07")
        assert result is not None
        expected_keys = {"is_dome", "condition", "temperature_c", "wind_speed_kmh",
                         "precipitation_mm", "weather_code", "is_adverse"}
        assert expected_keys == set(result.keys())

    def test_dome_condition_string(self):
        scraper = WeatherScraper()
        result = scraper.fetch_game_weather("LV", "2026-09-07")
        assert result is not None
        assert result["condition"] == "Dome"

    def test_dome_is_adverse_false(self):
        scraper = WeatherScraper()
        result = scraper.fetch_game_weather("MIN", "2026-09-07")
        assert result is not None
        assert result["is_adverse"] is False

    def test_unknown_team_returns_none(self):
        scraper = WeatherScraper()
        result = scraper.fetch_game_weather("XXX", "2026-09-07")
        assert result is None


class TestWeatherCodeMapping:
    """_wmo_condition maps WMO codes to correct condition strings."""

    def test_clear_code_0(self):
        assert _wmo_condition(0) == "Clear"

    def test_partly_cloudy_range(self):
        for code in range(1, 4):
            assert _wmo_condition(code) == "Partly Cloudy", f"code {code}"

    def test_fog_range(self):
        for code in (45, 48):
            assert _wmo_condition(code) == "Fog", f"code {code}"

    def test_rain_range(self):
        for code in (51, 67):
            assert _wmo_condition(code) == "Rain", f"code {code}"

    def test_snow_range(self):
        for code in (71, 77):
            assert _wmo_condition(code) == "Snow", f"code {code}"

    def test_thunderstorm_range(self):
        for code in (95, 99):
            assert _wmo_condition(code) == "Thunderstorm", f"code {code}"

    def test_unknown_for_unmapped_code(self):
        assert _wmo_condition(999) == "Unknown"
        assert _wmo_condition(-1) == "Unknown"
