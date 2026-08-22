"""FAAB waiver advisor: rank targets by value over YOUR roster's replacement level.

VBD ranks a player against the league; this ranks a candidate against the
worst player *you* already roster at that position — the number that
actually determines whether a waiver claim helps this specific team. Reuses
`roster_advisor.build_roster_pool` for both sides (roster and candidates)
since that's the verified cache-independent projection path (the bulk
`fantasy_projections` generator is unreliable for a future season).

Non-positive value is filtered out entirely, mirroring `swap_list`'s
established rule: a $0 bid on a below-replacement player is noise, not
advice.
"""

from unittest.mock import MagicMock, patch

from src.prediction.lineup_optimizer import LineupPlayer
from src.prediction.waiver_advisor import BID_TIERS, faab_recommendations


def _p(pid, name, pos, pts):
    return LineupPlayer(
        player_id=pid,
        full_name=name,
        position=pos,
        team_id=1,
        team_abbr="XX",
        projected_points=pts,
        salary=0,
    )


def _db(candidate_ids=()):
    db = MagicMock()
    db.fetchall.return_value = [{"player_id": pid} for pid in candidate_ids]
    return db


class TestReplacementLevel:
    @patch("src.prediction.waiver_advisor.build_roster_pool")
    def test_candidate_above_weakest_starter_gets_positive_delta(self, mock_pool):
        db = _db(candidate_ids=[20])
        mock_pool.side_effect = [
            [_p(1, "WR1", "WR", 15.0), _p(2, "WR2", "WR", 5.0)],  # my roster
            [_p(20, "Candidate", "WR", 9.0)],  # candidates
        ]
        result = faab_recommendations(db, MagicMock(), [1, 2], week=1, season=2026)
        assert len(result) == 1
        assert result[0]["player_id"] == 20
        assert result[0]["replacement_points"] == 5.0
        assert result[0]["delta"] == 4.0

    @patch("src.prediction.waiver_advisor.build_roster_pool")
    def test_position_absent_from_roster_has_zero_replacement(self, mock_pool):
        db = _db(candidate_ids=[30])
        mock_pool.side_effect = [
            [_p(1, "QB1", "QB", 20.0)],  # no TE on roster at all
            [_p(30, "Streamer TE", "TE", 6.0)],
        ]
        result = faab_recommendations(db, MagicMock(), [1], week=1, season=2026)
        assert result[0]["replacement_points"] == 0.0
        assert result[0]["delta"] == 6.0


class TestFiltering:
    @patch("src.prediction.waiver_advisor.build_roster_pool")
    def test_non_positive_delta_is_excluded(self, mock_pool):
        db = _db(candidate_ids=[20, 21])
        mock_pool.side_effect = [
            [_p(1, "WR1", "WR", 15.0)],
            [_p(20, "Worse", "WR", 10.0), _p(21, "Better", "WR", 18.0)],
        ]
        result = faab_recommendations(db, MagicMock(), [1], week=1, season=2026)
        assert [c["player_id"] for c in result] == [21]


class TestBidTiers:
    @patch("src.prediction.waiver_advisor.build_roster_pool")
    def test_bid_tier_thresholds(self, mock_pool):
        db = _db(candidate_ids=[10, 11, 12, 13])
        mock_pool.side_effect = [
            [_p(1, "Base", "WR", 5.0)],
            [
                _p(10, "Speculative", "WR", 6.5),  # delta 1.5
                _p(11, "Solid", "WR", 8.5),  # delta 3.5
                _p(12, "Priority", "WR", 12.0),  # delta 7.0
                _p(13, "MustAdd", "WR", 20.0),  # delta 15.0
            ],
        ]
        result = faab_recommendations(
            db, MagicMock(), [1], week=1, season=2026, budget_remaining=100
        )
        by_id = {c["player_id"]: c for c in result}
        assert by_id[10]["tier"] == "speculative"
        assert by_id[10]["suggested_bid_pct"] == BID_TIERS[0][1]
        assert by_id[11]["tier"] == "solid"
        assert by_id[12]["tier"] == "priority"
        assert by_id[13]["tier"] == "must-add"
        assert by_id[13]["suggested_bid_amount"] == round(100 * BID_TIERS[-1][1] / 100)


class TestRankingAndLimit:
    @patch("src.prediction.waiver_advisor.build_roster_pool")
    def test_sorted_best_delta_first(self, mock_pool):
        db = _db(candidate_ids=[10, 11])
        mock_pool.side_effect = [
            [_p(1, "Base", "WR", 5.0)],
            [_p(10, "Small", "WR", 6.0), _p(11, "Big", "WR", 15.0)],
        ]
        result = faab_recommendations(db, MagicMock(), [1], week=1, season=2026)
        assert [c["player_id"] for c in result] == [11, 10]

    @patch("src.prediction.waiver_advisor.build_roster_pool")
    def test_limit_truncates(self, mock_pool):
        db = _db(candidate_ids=[10, 11, 12])
        mock_pool.side_effect = [
            [_p(1, "Base", "WR", 5.0)],
            [
                _p(10, "A", "WR", 6.0),
                _p(11, "B", "WR", 7.0),
                _p(12, "C", "WR", 8.0),
            ],
        ]
        result = faab_recommendations(
            db, MagicMock(), [1], week=1, season=2026, limit=2
        )
        assert len(result) == 2
        assert [c["player_id"] for c in result] == [12, 11]

    @patch("src.prediction.waiver_advisor.build_roster_pool")
    def test_position_filter(self, mock_pool):
        db = _db(candidate_ids=[10, 11])
        mock_pool.side_effect = [
            [_p(1, "Base", "WR", 5.0), _p(2, "BaseTE", "TE", 5.0)],
            [_p(10, "GoodWR", "WR", 12.0), _p(11, "GoodTE", "TE", 12.0)],
        ]
        result = faab_recommendations(
            db, MagicMock(), [1, 2], week=1, season=2026, position="WR"
        )
        assert [c["player_id"] for c in result] == [10]


class TestCandidatePoolExcludesRoster:
    @patch("src.prediction.waiver_advisor.build_roster_pool")
    def test_candidate_query_excludes_roster_ids(self, mock_pool):
        db = _db(candidate_ids=[])
        mock_pool.return_value = []
        faab_recommendations(db, MagicMock(), [1, 2, 3], week=1, season=2026)

        # The candidate-id SQL must have been parameterised with the roster
        # ids to exclude, not run unfiltered.
        args, _kwargs = db.fetchall.call_args
        params = args[1]
        assert 1 in params and 2 in params and 3 in params
