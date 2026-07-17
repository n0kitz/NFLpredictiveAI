"""Tests for the LeagueSettings abstraction (scoring + league size + slots)."""

import pytest

from src.database.db import DEFAULT_DB_PATH, Database
from src.prediction.league_settings import LeagueSettings, NFL_DEFAULT_SLOTS


class TestReplacementRanks:
    def test_12_team_matches_conventional_cutoffs(self):
        ranks = LeagueSettings(league_size=12).replacement_ranks()
        assert ranks["QB"] == 12
        assert ranks["RB"] == 30  # ceil(12 * (2 + 0.45))
        assert ranks["WR"] == 30
        assert ranks["TE"] == 14  # ceil(12 * (1 + 0.10))
        assert ranks["K"] == 12
        assert ranks["DST"] == 12

    def test_8_team_shrinks(self):
        ranks = LeagueSettings(league_size=8).replacement_ranks()
        assert ranks["QB"] == 8
        assert ranks["RB"] == 20  # ceil(8 * 2.45)
        assert ranks["WR"] == 20
        assert ranks["DST"] == 8

    def test_20_team_grows(self):
        ranks = LeagueSettings(league_size=20).replacement_ranks()
        assert ranks["QB"] == 20
        assert ranks["RB"] == 49  # ceil(20 * 2.45)

    def test_monotone_in_league_size(self):
        for pos in ("QB", "RB", "WR", "TE", "K", "DST"):
            prev = 0
            for n in range(8, 21):
                r = LeagueSettings(league_size=n).replacement_ranks()[pos]
                assert r >= prev
                prev = r


class TestTierBoundaries:
    def test_scales_with_league_size(self):
        assert LeagueSettings(league_size=12).tier_boundaries() == [
            12,
            36,
            60,
            84,
            108,
            132,
            156,
            180,
        ]
        assert LeagueSettings(league_size=8).tier_boundaries() == [
            8,
            24,
            40,
            56,
            72,
            88,
            104,
            120,
        ]


class TestPointsExpr:
    def test_standard(self):
        assert (
            LeagueSettings(scoring="standard").points_expr("pss")
            == "pss.fantasy_points_standard"
        )

    def test_ppr(self):
        assert (
            LeagueSettings(scoring="ppr").points_expr("pss") == "pss.fantasy_points_ppr"
        )

    def test_half_ppr(self):
        expr = LeagueSettings(scoring="half_ppr").points_expr("pss")
        assert "fantasy_points_ppr" in expr and "fantasy_points_standard" in expr
        assert "/ 2" in expr or "/2" in expr


class TestValidation:
    def test_league_size_bounds(self):
        with pytest.raises(ValueError):
            LeagueSettings(league_size=7)
        with pytest.raises(ValueError):
            LeagueSettings(league_size=21)

    def test_scoring_values(self):
        with pytest.raises(ValueError):
            LeagueSettings(scoring="superflex")

    def test_defaults_are_nfl_com(self):
        s = LeagueSettings()
        assert s.scoring == "standard"
        assert s.league_size == 10
        assert s.roster_slots == NFL_DEFAULT_SLOTS
        assert s.roster_slots["DST"] == 1


class TestBlendedSeasonPoints:
    def test_two_season_blend(self):
        from src.prediction.fantasy_scorer import blend_projected_season_points

        # 0.65×(170/17) + 0.35×(136/17) = 6.5 + 2.8 = 9.3 ppg → ×17 = 158.1
        assert blend_projected_season_points(170.0, 17, 136.0, 17) == 158.1

    def test_only_last_season(self):
        from src.prediction.fantasy_scorer import blend_projected_season_points

        assert blend_projected_season_points(170.0, 17, 0.0, 0) == 170.0

    def test_only_prior_season(self):
        from src.prediction.fantasy_scorer import blend_projected_season_points

        assert blend_projected_season_points(0.0, 0, 136.0, 17) == 136.0

    def test_no_data(self):
        from src.prediction.fantasy_scorer import blend_projected_season_points

        assert blend_projected_season_points(0.0, 0, 0.0, 0) == 0.0

    def test_partial_season_extrapolates_per_game(self):
        from src.prediction.fantasy_scorer import blend_projected_season_points

        # 10 ppg over 8 games last season, no prior → 10 × 17 = 170
        # (8 games is enough sample — no shrinkage)
        assert blend_projected_season_points(80.0, 8, 0.0, 0) == 170.0

    def test_tiny_sample_shrinks(self):
        from src.prediction.fantasy_scorer import blend_projected_season_points

        # One 19.2-point game must not extrapolate to a 326-point season:
        # shrinkage = 1/8 → 19.2 × 17 × 0.125 = 40.8
        assert blend_projected_season_points(19.2, 1, 0.0, 0) == 40.8


# ── Integration: rankings honor league settings (needs real DB) ─────────────

pytestmark_db = pytest.mark.skipif(
    not DEFAULT_DB_PATH.exists(), reason="real nfl.db not present"
)


@pytest.fixture(scope="module")
def scorer():
    from src.prediction.fantasy_scorer import FantasyScorer

    db = Database(DEFAULT_DB_PATH)
    yield FantasyScorer(db)
    db.close()


@pytestmark_db
class TestRankingsWithLeagueSettings:
    def test_rankings_include_k_and_dst(self, scorer):
        rankings = scorer.generate_draft_rankings(2026, "standard")
        positions = {r["position"] for r in rankings}
        assert "K" in positions
        assert "DST" in positions

    def test_league_size_changes_vbd(self, scorer):
        r8 = scorer.generate_draft_rankings(2026, "standard", league_size=8)
        r20 = scorer.generate_draft_rankings(2026, "standard", league_size=20)
        vbd8 = {r["player_id"]: r["vbd"] for r in r8 if r["vbd"]}
        vbd20 = {r["player_id"]: r["vbd"] for r in r20 if r["vbd"]}
        common = [pid for pid in vbd8 if pid in vbd20]
        assert common
        # Deeper league → scarcer replacement → VBD should mostly grow
        grew = sum(1 for pid in common if vbd20[pid] > vbd8[pid])
        assert grew > len(common) * 0.5

    def test_half_ppr_accepted(self, scorer):
        rankings = scorer.generate_draft_rankings(2026, "half_ppr", league_size=10)
        assert rankings

    def test_overall_rank_ordered_by_vbd(self, scorer):
        rankings = scorer.generate_draft_rankings(2026, "standard", league_size=10)
        vbds = [r["vbd"] for r in rankings if r["vbd"] is not None]
        assert vbds == sorted(vbds, reverse=True)
        # Draft board must not be a wall of QBs: top-10 by value should mix positions
        top10_pos = {r["position"] for r in rankings[:10]}
        assert len(top10_pos) >= 2
