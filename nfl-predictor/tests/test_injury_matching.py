"""Injury reports must attach to the right player.

Every injury lookup used to key on the lowercase LAST TOKEN of the name, so
``"Marvin Harrison Jr.".split()[-1]`` was ``"jr."`` and the LIKE '%jr.%' query
returned whichever "Jr." happened to be first in the table. Measured against
the live 2026-08-21 data: **168 of 1013 rostered fantasy players inherited a
stranger's injury**, and an "Out" row multiplies a projection by 0.0.
"""

import pytest

from src.database.db import Database
from src.prediction.fantasy_scorer import build_injury_index, lookup_injury


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    from src.scraper.team_mappings import CURRENT_TEAMS

    for t in CURRENT_TEAMS:
        database.insert_team(
            t.name,
            t.city,
            t.conference,
            t.division,
            t.abbreviation,
            t.franchise_id,
            t.active_from,
            t.active_until,
        )
    yield database
    database.close()


def _rows(*entries):
    """entries: (player_name, position, status, team_id)"""
    return [
        {
            "player_name": n,
            "position": p,
            "injury_status": s,
            "team_id": t,
        }
        for n, p, s, t in entries
    ]


class TestSuffixCollisions:
    def test_jr_suffix_does_not_match_unrelated_jr(self):
        """The exact failure seen live: Harrison Jr. inherited Penix Jr."""
        index = build_injury_index(
            _rows(("Michael Penix Jr.", "QB", "Questionable", 1))
        )
        assert lookup_injury(index, "Marvin Harrison Jr.", position="WR") is None

    def test_iii_suffix_does_not_match_unrelated_iii(self):
        index = build_injury_index(_rows(("Luther Burden III", "WR", "Out", 1)))
        assert lookup_injury(index, "James Cook III", position="RB") is None

    def test_shared_last_name_does_not_match(self):
        """DJ Moore must not inherit Elijah Moore's status."""
        index = build_injury_index(_rows(("Elijah Moore", "WR", "Questionable", 1)))
        assert lookup_injury(index, "DJ Moore", position="WR") is None

    def test_substring_last_name_does_not_match(self):
        """LIKE '%Hill%' used to match Hilliard."""
        index = build_injury_index(_rows(("Justice Hill", "RB", "Out", 1)))
        assert lookup_injury(index, "Dontrell Hilliard", position="RB") is None


class TestCorrectMatches:
    def test_exact_name_matches(self):
        index = build_injury_index(_rows(("Puka Nacua", "WR", "Questionable", 1)))
        assert lookup_injury(index, "Puka Nacua", position="WR") == "Questionable"

    def test_suffix_difference_still_matches_same_player(self):
        """Feed says "Kenneth Walker", roster says "Kenneth Walker III"."""
        index = build_injury_index(_rows(("Kenneth Walker", "RB", "Out", 1)))
        assert lookup_injury(index, "Kenneth Walker III", position="RB") == "Out"

    def test_accent_difference_still_matches(self):
        index = build_injury_index(_rows(("Eddy Piñeiro", "K", "Doubtful", 1)))
        assert lookup_injury(index, "Eddy Pineiro", position="K") == "Doubtful"

    def test_position_disambiguates_identical_names(self):
        index = build_injury_index(
            _rows(
                ("Mike Williams", "WR", "Out", 1),
                ("Mike Williams", "TE", "Questionable", 2),
            )
        )
        assert lookup_injury(index, "Mike Williams", position="TE") == "Questionable"
        assert lookup_injury(index, "Mike Williams", position="WR") == "Out"

    def test_ambiguous_without_position_returns_none(self):
        index = build_injury_index(
            _rows(
                ("Mike Williams", "WR", "Out", 1),
                ("Mike Williams", "TE", "Questionable", 2),
            )
        )
        assert lookup_injury(index, "Mike Williams") is None

    def test_unknown_player_returns_none(self):
        index = build_injury_index(_rows(("Puka Nacua", "WR", "Out", 1)))
        assert lookup_injury(index, "Nobody Here", position="WR") is None

    def test_empty_index(self):
        assert (
            lookup_injury(build_injury_index([]), "Puka Nacua", position="WR") is None
        )


class TestProjectionIntegration:
    """The 0.7x Questionable rule must fire for the right player only."""

    def _seed_player(self, db, name, position, team_id=1):
        cur = db.execute(
            "INSERT INTO players (espn_id, full_name, last_name, position) "
            "VALUES (?, ?, ?, ?)",
            (name, name, name.split()[-1], position),
        )
        db.commit()
        return cur.lastrowid

    def test_questionable_discounts_the_named_player(self, db):
        from src.prediction.fantasy_scorer import FantasyScorer

        pid = self._seed_player(db, "Puka Nacua", "WR")
        db.execute(
            "INSERT INTO injury_reports (team_id, player_name, position, "
            "injury_status, report_date) VALUES (1, 'Puka Nacua', 'WR', "
            "'Questionable', '2026-08-21')",
            (),
        )
        db.commit()

        scorer = FantasyScorer(db)
        proj = scorer.calculate_projection(
            pid, week=1, season=2026, opponent_team_id=None
        )
        assert proj.get("injury_status") == "Questionable"

    def test_unrelated_jr_does_not_zero_a_healthy_player(self, db):
        """Regression: an 'Out' Jr. must not zero a different Jr."""
        from src.prediction.fantasy_scorer import FantasyScorer

        pid = self._seed_player(db, "Marvin Harrison Jr.", "WR")
        db.execute(
            "INSERT INTO injury_reports (team_id, player_name, position, "
            "injury_status, report_date) VALUES (1, 'Michael Penix Jr.', 'QB', "
            "'Out', '2026-08-21')",
            (),
        )
        db.commit()

        scorer = FantasyScorer(db)
        proj = scorer.calculate_projection(
            pid, week=1, season=2026, opponent_team_id=None
        )
        assert proj.get("injury_status") is None
