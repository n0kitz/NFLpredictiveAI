"""Basic tests for NFL Prediction System."""

import pytest
from pathlib import Path
import tempfile

from src.database.db import Database
from src.database.models import Team, Game, FactorType
from src.scraper.team_mappings import TeamMappings, CURRENT_TEAMS
from src.prediction.metrics import calculate_exponential_weight, calculate_season_weight
from src.utils.helpers import format_record, format_percentage, parse_team_input


class TestTeamMappings:
    """Tests for team mappings module."""

    def test_current_teams_count(self):
        """Verify we have all 32 NFL teams."""
        assert len(CURRENT_TEAMS) == 32

    def test_team_mappings_initialization(self):
        """Test TeamMappings initializes correctly."""
        mappings = TeamMappings()
        assert len(mappings.pfr_to_team) > 0
        assert len(mappings.name_to_team) > 0

    def test_find_team_by_abbreviation(self):
        """Test finding team by abbreviation."""
        mappings = TeamMappings()
        team = mappings.find_team("KC")
        assert team is not None
        assert team.name == "Chiefs"

    def test_find_team_by_name(self):
        """Test finding team by name."""
        mappings = TeamMappings()
        team = mappings.find_team("Chiefs")
        assert team is not None
        assert team.city == "Kansas City"

    def test_find_team_by_city(self):
        """Test finding team by city."""
        mappings = TeamMappings()
        team = mappings.find_team("Kansas City")
        assert team is not None
        assert team.abbreviation == "KC"

    def test_get_team_by_pfr_abbr(self):
        """Test getting team by PFR abbreviation."""
        mappings = TeamMappings()
        team = mappings.get_team_by_pfr_abbr("kan")
        assert team is not None
        assert team.abbreviation == "KC"


class TestDatabase:
    """Tests for database module."""

    def test_database_initialization(self):
        """Test database can be initialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.init_schema()
            assert db_path.exists()
            db.close()

    def test_insert_and_get_team(self):
        """Test inserting and retrieving a team."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.init_schema()

            team_id = db.insert_team(
                name="Test Team",
                city="Test City",
                conference="AFC",
                division="East",
                abbreviation="TST"
            )

            team = db.get_team_by_abbreviation("TST")
            assert team is not None
            assert team['name'] == "Test Team"
            assert team['team_id'] == team_id

            db.close()


class TestMetrics:
    """Tests for metrics calculation."""

    def test_exponential_weight_decay(self):
        """Test exponential weight decays over time."""
        weight_0 = calculate_exponential_weight(0)
        weight_5 = calculate_exponential_weight(5)
        weight_10 = calculate_exponential_weight(10)

        assert weight_0 > weight_5 > weight_10
        assert weight_0 == 1.0  # Most recent game has weight 1

    def test_season_weight(self):
        """Test season weighting."""
        current = calculate_season_weight(0)
        last_year = calculate_season_weight(1)
        two_years_ago = calculate_season_weight(2)

        assert current > last_year > two_years_ago
        assert current == 3.0  # Current season multiplier


class TestHelpers:
    """Tests for helper utilities."""

    def test_format_record(self):
        """Test record formatting."""
        assert format_record(10, 4) == "10-4"
        assert format_record(10, 4, 1) == "10-4-1"
        assert format_record(0, 0) == "0-0"

    def test_format_percentage(self):
        """Test percentage formatting."""
        assert format_percentage(0.75) == "75.0%"
        assert format_percentage(0.5) == "50.0%"
        assert format_percentage(1.0) == "100.0%"

    def test_parse_team_input(self):
        """Test team input parsing."""
        assert parse_team_input("the Chiefs") == "Chiefs"
        assert parse_team_input("  Eagles  ") == "Eagles"
        assert parse_team_input("The Patriots") == "Patriots"


class TestModels:
    """Tests for data models."""

    def test_factor_type_enum(self):
        """Test FactorType enum values."""
        assert FactorType.BETTER_DEFENSE.value == "better_defense"
        assert FactorType.INJURY_IMPACT.value == "injury_impact"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
