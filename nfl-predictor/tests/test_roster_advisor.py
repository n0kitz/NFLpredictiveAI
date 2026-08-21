"""Roster-aware lineup advice: "give me my team, tell me what to change".

The existing optimizer builds its pool from cached projections across every
position, i.e. it answers "who are the best players in the league" — a DFS
question. This module answers the season-long one: given MY roster, what is
the best legal lineup and which specific swaps get me there.
"""

import pytest

from src.prediction.league_settings import LeagueSettings
from src.prediction.lineup_optimizer import LineupPlayer
from src.prediction.roster_advisor import (
    lineup_advice,
    naive_lineup,
    slots_from_settings,
    swap_list,
)

pulp = pytest.importorskip("pulp")


def _p(pid, name, pos, pts, team_id=1):
    return LineupPlayer(
        player_id=pid,
        full_name=name,
        position=pos,
        team_id=team_id,
        team_abbr=f"T{team_id}",
        projected_points=pts,
        salary=0,
    )


def _roster():
    """A legal 9-slot roster plus bench, with a deliberate FLEX trap.

    WR3 (12.0) outscores RB2 (8.0), so a greedy per-slot fill that stops at
    two WRs leaves points on the bench.
    """
    return [
        _p(1, "QB1", "QB", 20.0),
        _p(2, "RB1", "RB", 15.0),
        _p(3, "RB2", "RB", 8.0),
        _p(4, "RB3", "RB", 4.0),
        _p(5, "WR1", "WR", 14.0),
        _p(6, "WR2", "WR", 13.0),
        _p(7, "WR3", "WR", 12.0),
        _p(8, "TE1", "TE", 9.0),
        _p(9, "K1", "K", 8.0),
        _p(10, "DST1", "DST", 7.0),
    ]


class TestBuildRosterPool:
    """The pool must come from live per-player projections, not the cache.

    `fantasy_projections` for an upcoming season is unreliable — the bulk
    generator produced Jake Haener (backup QB) at 12.0 and Bijan Robinson at
    5.4, exactly inverted — while `calculate_projection` returns 1.65 and
    17.16. A roster is at most 25 players, so projecting each directly is both
    affordable and trustworthy, and keeps lineup advice consistent with
    start/sit.
    """

    class _FakeScorer:
        def __init__(self, by_id):
            self.by_id = by_id
            self.calls = []

        def calculate_projection(self, pid, week, season, opp):
            self.calls.append(pid)
            return dict(self.by_id.get(pid, {}))

        def _enrich_projection(self, proj, pid):
            proj.setdefault("full_name", f"P{pid}")
            proj.setdefault("team_abbr", "KC")
            proj["headshot_url"] = None
            return proj

    def _scorer(self):
        return self._FakeScorer(
            {
                1: {
                    "position": "RB",
                    "projected_points_ppr": 21.8,
                    "projected_points_std": 17.2,
                },
                2: {
                    "position": "QB",
                    "projected_points_ppr": 1.65,
                    "projected_points_std": 1.65,
                },
            }
        )

    def test_projects_each_requested_player(self):
        from src.prediction.roster_advisor import build_roster_pool

        scorer = self._scorer()
        pool = build_roster_pool(scorer, [1, 2], week=1, season=2026)
        assert sorted(scorer.calls) == [1, 2]
        assert {p.player_id for p in pool} == {1, 2}

    def test_uses_league_scoring(self):
        from src.prediction.roster_advisor import build_roster_pool

        pool = build_roster_pool(
            self._scorer(), [1], week=1, season=2026, settings=LeagueSettings()
        )
        assert pool[0].projected_points == pytest.approx(17.2)  # standard

        pool_ppr = build_roster_pool(
            self._scorer(),
            [1],
            week=1,
            season=2026,
            settings=LeagueSettings(scoring="ppr"),
        )
        assert pool_ppr[0].projected_points == pytest.approx(21.8)

    def test_unprojectable_player_is_skipped(self):
        from src.prediction.roster_advisor import build_roster_pool

        pool = build_roster_pool(self._scorer(), [1, 999], week=1, season=2026)
        assert [p.player_id for p in pool] == [1]


class TestSlotsFromSettings:
    def test_drops_bench_slot(self):
        slots, flex = slots_from_settings(LeagueSettings())
        assert "BN" not in slots
        assert slots["QB"] == 1 and slots["RB"] == 2 and slots["WR"] == 2

    def test_flex_positions_returned(self):
        _, flex = slots_from_settings(LeagueSettings())
        assert flex == {"RB", "WR", "TE"}

    def test_respects_custom_slots(self):
        settings = LeagueSettings(
            roster_slots={"QB": 1, "RB": 2, "WR": 3, "TE": 1, "FLEX": 2, "BN": 6}
        )
        slots, _ = slots_from_settings(settings)
        assert slots["WR"] == 3 and slots["FLEX"] == 2 and "BN" not in slots


class TestNaiveLineup:
    def test_fills_each_slot_with_best_available(self):
        slots, flex = slots_from_settings(LeagueSettings())
        chosen = naive_lineup(_roster(), slots, flex)
        names = {p.full_name for p in chosen}
        assert "QB1" in names and "RB1" in names and "WR1" in names

    def test_does_not_exceed_slot_counts(self):
        slots, flex = slots_from_settings(LeagueSettings())
        chosen = naive_lineup(_roster(), slots, flex)
        assert len(chosen) == sum(slots.values())


class TestOptimalLineup:
    def test_lineup_uses_only_my_roster(self):
        """The guard for the bug this module exists to fix."""
        roster = _roster()
        result = lineup_advice(roster, settings=LeagueSettings())
        roster_ids = {p.player_id for p in roster}
        assert {p["player_id"] for p in result["lineup"]} <= roster_ids

    def test_lineup_is_legal_under_settings(self):
        slots, _ = slots_from_settings(LeagueSettings())
        result = lineup_advice(_roster(), settings=LeagueSettings())
        assert len(result["lineup"]) == sum(slots.values())
        by_slot: dict = {}
        for p in result["lineup"]:
            by_slot[p["slot"]] = by_slot.get(p["slot"], 0) + 1
        for slot, count in slots.items():
            assert by_slot.get(slot, 0) == count

    def test_flex_takes_the_best_leftover(self):
        """WR3 (12.0) must beat RB2 (8.0) for the FLEX spot."""
        result = lineup_advice(_roster(), settings=LeagueSettings())
        flex = [p for p in result["lineup"] if p["slot"] == "FLEX"]
        assert len(flex) == 1
        assert flex[0]["full_name"] == "WR3"

    def test_bench_is_everyone_not_starting(self):
        roster = _roster()
        result = lineup_advice(roster, settings=LeagueSettings())
        starters = {p["player_id"] for p in result["lineup"]}
        bench = {p["player_id"] for p in result["bench"]}
        assert starters | bench == {p.player_id for p in roster}
        assert not (starters & bench)

    def test_warns_when_a_forced_starter_scores_nothing(self):
        """Real case: the only TE on the roster was ruled Out.

        The optimizer must still fill the slot, so it starts him at 0.00 — the
        right lineup, but silently telling someone to start a player who cannot
        play is the opposite of advice. Say so.
        """
        roster = [p for p in _roster() if p.position != "TE"]
        roster.append(_p(11, "Hurt TE", "TE", 0.0))
        result = lineup_advice(roster, settings=LeagueSettings())
        assert any("Hurt TE" in w for w in result["warnings"]), result["warnings"]

    def test_no_zero_warning_when_everyone_scores(self):
        result = lineup_advice(_roster(), settings=LeagueSettings())
        assert not any("projects 0" in w for w in result["warnings"])

    def test_missing_position_is_a_warning_not_a_crash(self):
        roster = [p for p in _roster() if p.position != "K"]
        result = lineup_advice(roster, settings=LeagueSettings())
        assert any("K" in w for w in result["warnings"])


class TestSwapList:
    def test_no_swaps_when_current_is_optimal(self):
        roster = _roster()
        optimal = lineup_advice(roster, settings=LeagueSettings())
        current_ids = [p["player_id"] for p in optimal["lineup"]]
        result = lineup_advice(
            roster, settings=LeagueSettings(), current_starter_ids=current_ids
        )
        assert result["swaps"] == []
        assert result["points_gained"] == 0.0

    def test_suggests_swap_when_a_starter_is_worse_than_a_bench_player(self):
        roster = _roster()
        # Start RB3 (4.0) instead of WR3 (12.0) in the FLEX.
        optimal = lineup_advice(roster, settings=LeagueSettings())
        current_ids = [p["player_id"] for p in optimal["lineup"]]
        wr3 = next(p for p in roster if p.full_name == "WR3")
        rb3 = next(p for p in roster if p.full_name == "RB3")
        current_ids = [pid for pid in current_ids if pid != wr3.player_id]
        current_ids.append(rb3.player_id)

        result = lineup_advice(
            roster, settings=LeagueSettings(), current_starter_ids=current_ids
        )
        assert result["swaps"], "expected a suggested swap"
        swap = result["swaps"][0]
        assert swap["start_name"] == "WR3"
        assert swap["sit_name"] == "RB3"
        assert swap["point_delta"] == pytest.approx(8.0)
        assert result["points_gained"] > 0

    def test_swap_entries_carry_a_reason(self):
        roster = _roster()
        optimal = lineup_advice(roster, settings=LeagueSettings())
        current_ids = [p["player_id"] for p in optimal["lineup"]]
        wr3 = next(p for p in roster if p.full_name == "WR3")
        rb3 = next(p for p in roster if p.full_name == "RB3")
        current_ids = [pid for pid in current_ids if pid != wr3.player_id] + [
            rb3.player_id
        ]
        result = lineup_advice(
            roster, settings=LeagueSettings(), current_starter_ids=current_ids
        )
        assert result["swaps"][0]["reason"]

    def test_never_suggests_a_swap_that_loses_points(self):
        """A swap with a non-positive delta is not advice, it is noise.

        Pairing the best upgrade with the worst downgrade can produce a
        negative delta when lineups differ only by ties — which rendered as
        "worth only +-0.9 pts" alongside points_gained of 0.0.
        """
        pool = {p.player_id: p for p in _roster()}
        optimal = [
            {"player_id": 2, "slot": "RB", "full_name": "RB1"},  # 15.0
            {"player_id": 6, "slot": "WR", "full_name": "WR2"},  # 13.0
        ]
        current = [
            {"player_id": 5, "slot": "WR", "full_name": "WR1"},  # 14.0
            {"player_id": 7, "slot": "WR", "full_name": "WR3"},  # 12.0
        ]
        swaps = swap_list(optimal, current, pool)
        assert all(s["point_delta"] > 0 for s in swaps), swaps
        assert all("+-" not in s["reason"] for s in swaps)

    def test_equal_value_lineups_produce_no_swaps(self):
        pool = {p.player_id: p for p in _roster()}
        optimal = [{"player_id": 5, "slot": "WR", "full_name": "WR1"}]
        current = [{"player_id": 5, "slot": "WR", "full_name": "WR1"}]
        assert swap_list(optimal, current, pool) == []

    def test_swaps_sorted_by_impact(self):
        pool = {p.player_id: p for p in _roster()}
        optimal = [
            {"player_id": 5, "slot": "WR", "full_name": "WR1"},
            {"player_id": 2, "slot": "RB", "full_name": "RB1"},
        ]
        current = [
            {"player_id": 7, "slot": "WR", "full_name": "WR3"},
            {"player_id": 4, "slot": "RB", "full_name": "RB3"},
        ]
        swaps = swap_list(optimal, current, pool)
        deltas = [s["point_delta"] for s in swaps]
        assert deltas == sorted(deltas, reverse=True)


class TestScoringRespected:
    def test_points_gained_never_negative(self):
        roster = _roster()
        result = lineup_advice(roster, settings=LeagueSettings())
        assert result["points_gained"] >= 0.0

    def test_projected_points_matches_lineup_sum(self):
        result = lineup_advice(_roster(), settings=LeagueSettings())
        total = sum(p["projected_points"] for p in result["lineup"])
        assert result["projected_points"] == pytest.approx(total, abs=0.01)
