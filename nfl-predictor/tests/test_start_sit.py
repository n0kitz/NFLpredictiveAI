"""Start/sit advice must rank in the league's scoring and handle N players.

Two problems this covers:

1. ``start_sit_recommendation`` ranked on ``projected_points_ppr`` even though
   the default league is NFL.com **Standard**, systematically over-valuing
   high-reception, low-yardage players.
2. It compared exactly two players, so "which of my three WRs do I start?" —
   the question actually asked on Sunday morning — had no answer.
"""

from unittest.mock import MagicMock

import pytest

from src.prediction.fantasy_scorer import FantasyScorer
from src.prediction.league_settings import LeagueSettings


class TestPointsFromProjection:
    """Selecting the scoring column is the whole bug, so pin it directly."""

    PROJ = {"projected_points_ppr": 20.0, "projected_points_std": 12.0}

    def test_standard_uses_std(self):
        assert (
            LeagueSettings(scoring="standard").points_from_projection(self.PROJ) == 12.0
        )

    def test_ppr_uses_ppr(self):
        assert LeagueSettings(scoring="ppr").points_from_projection(self.PROJ) == 20.0

    def test_half_ppr_averages(self):
        assert (
            LeagueSettings(scoring="half_ppr").points_from_projection(self.PROJ) == 16.0
        )

    def test_missing_keys_default_to_zero(self):
        assert LeagueSettings().points_from_projection({}) == 0.0


@pytest.fixture
def scorer():
    """A scorer whose projections are stubbed per player id."""
    db = MagicMock()
    db.get_all_current_injuries.return_value = []
    db.fetchone.return_value = None
    db.fetchall.return_value = []
    return FantasyScorer(db)


def _stub_projections(scorer, by_id):
    """Make calculate_projection return canned dicts keyed by player id."""

    def _calc(player_id, week, season, opponent_team_id, *a, **kw):
        return dict(by_id[player_id])

    scorer.calculate_projection = _calc  # type: ignore[method-assign]


# A volume receiver vs a big-play receiver: PPR and Standard disagree.
PPR_WINNER = {
    "player_id": 1,
    "full_name": "Slot Guy",
    "position": "WR",
    "projected_points_ppr": 18.0,
    "projected_points_std": 9.0,  # 9 catches, few yards
    "matchup_score": 1.0,
    "confidence": "medium",
    "injury_status": None,
    "weather_impact": False,
}
STD_WINNER = {
    "player_id": 2,
    "full_name": "Deep Threat",
    "position": "WR",
    "projected_points_ppr": 16.0,
    "projected_points_std": 14.0,  # fewer catches, more yards/TDs
    "matchup_score": 1.0,
    "confidence": "medium",
    "injury_status": None,
    "weather_impact": False,
}


class TestScoringDrivesTheAnswer:
    def test_standard_league_prefers_the_standard_winner(self, scorer):
        _stub_projections(scorer, {1: PPR_WINNER, 2: STD_WINNER})
        result = scorer.start_sit_recommendation(1, 2, week=1, season=2026)
        assert result["start"]["player_id"] == 2, "Standard scoring must win by default"
        assert result["sit"]["player_id"] == 1

    def test_ppr_league_prefers_the_ppr_winner(self, scorer):
        _stub_projections(scorer, {1: PPR_WINNER, 2: STD_WINNER})
        result = scorer.rank_start_sit(
            [1, 2], week=1, season=2026, settings=LeagueSettings(scoring="ppr")
        )
        assert result["ranked"][0]["player_id"] == 1

    def test_reasoning_quotes_the_ranked_scoring(self, scorer):
        """It must not rank on Standard and then justify with a PPR number."""
        _stub_projections(scorer, {1: PPR_WINNER, 2: STD_WINNER})
        result = scorer.rank_start_sit([1, 2], week=1, season=2026)
        top = result["ranked"][0]
        assert "18.0" not in top["reasoning"], "quoted the PPR number"
        assert f"{top['projected_points']:.1f}" in top["reasoning"]


class TestRankStartSit:
    def _three_wrs(self):
        def mk(pid, name, std, ppr, matchup=1.0, injury=None):
            return {
                "player_id": pid,
                "full_name": name,
                "position": "WR",
                "projected_points_ppr": ppr,
                "projected_points_std": std,
                "matchup_score": matchup,
                "confidence": "medium",
                "injury_status": injury,
                "weather_impact": False,
            }

        return {
            1: mk(1, "Best WR", 15.0, 19.0, matchup=1.2),
            2: mk(2, "Middle WR", 11.0, 14.0),
            3: mk(3, "Worst WR", 6.0, 8.0, matchup=0.8),
        }

    def test_ranks_all_three(self, scorer):
        _stub_projections(scorer, self._three_wrs())
        result = scorer.rank_start_sit([1, 2, 3], week=1, season=2026)
        assert [r["player_id"] for r in result["ranked"]] == [1, 2, 3]
        assert [r["rank"] for r in result["ranked"]] == [1, 2, 3]

    def test_slots_controls_how_many_start(self, scorer):
        _stub_projections(scorer, self._three_wrs())
        result = scorer.rank_start_sit([1, 2, 3], week=1, season=2026, slots=2)
        verdicts = [r["verdict"] for r in result["ranked"]]
        assert verdicts == ["start", "start", "sit"]

    def test_edge_over_next_is_zero_on_the_last_entry(self, scorer):
        _stub_projections(scorer, self._three_wrs())
        ranked = scorer.rank_start_sit([1, 2, 3], week=1, season=2026)["ranked"]
        assert ranked[0]["edge_over_next"] == pytest.approx(4.0)
        assert ranked[-1]["edge_over_next"] == 0.0

    def test_ruled_out_player_sinks_to_last(self, scorer):
        players = self._three_wrs()
        players[1]["injury_status"] = "Out"
        players[1]["projected_points_std"] = 0.0
        players[1]["projected_points_ppr"] = 0.0
        _stub_projections(scorer, players)
        ranked = scorer.rank_start_sit([1, 2, 3], week=1, season=2026)["ranked"]
        assert ranked[-1]["player_id"] == 1
        assert "out" in ranked[-1]["reasoning"].lower()

    def test_close_call_is_flagged_as_a_coin_flip(self, scorer):
        players = self._three_wrs()
        players[2]["projected_points_std"] = 14.8  # within a point of Best WR
        _stub_projections(scorer, players)
        ranked = scorer.rank_start_sit([1, 2], week=1, season=2026)["ranked"]
        assert "coin flip" in ranked[0]["reasoning"].lower()

    def test_single_player_does_not_raise(self, scorer):
        _stub_projections(scorer, self._three_wrs())
        result = scorer.rank_start_sit([1], week=1, season=2026)
        assert len(result["ranked"]) == 1
        assert result["ranked"][0]["verdict"] == "start"

    def test_empty_list_returns_empty_ranking(self, scorer):
        _stub_projections(scorer, self._three_wrs())
        assert scorer.rank_start_sit([], week=1, season=2026)["ranked"] == []

    def test_unknown_player_is_skipped(self, scorer):
        players = self._three_wrs()

        def _calc(player_id, week, season, opponent_team_id, *a, **kw):
            return dict(players[player_id]) if player_id in players else {}

        scorer.calculate_projection = _calc  # type: ignore[method-assign]
        ranked = scorer.rank_start_sit([1, 999], week=1, season=2026)["ranked"]
        assert [r["player_id"] for r in ranked] == [1]


class TestLegacyDelegation:
    """The two-player endpoint keeps its exact contract."""

    def test_returns_legacy_shape(self, scorer):
        _stub_projections(scorer, {1: PPR_WINNER, 2: STD_WINNER})
        result = scorer.start_sit_recommendation(1, 2, week=1, season=2026)
        assert set(result) == {"start", "sit", "confidence"}
        for side in ("start", "sit"):
            assert set(result[side]) >= {
                "player_id",
                "full_name",
                "position",
                "team_abbr",
                "headshot_url",
                "projected_points_ppr",
                "matchup_score",
                "reasoning",
            }
