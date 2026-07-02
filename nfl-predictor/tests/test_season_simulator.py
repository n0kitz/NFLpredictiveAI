"""Unit tests for the Monte Carlo season simulator + shared standings helper."""

from types import SimpleNamespace

from src.prediction.season_simulator import simulate_season
from src.prediction.standings import conference_seeding, finalize_win_pct


class StubDB:
    def __init__(self, teams, games):
        self._teams = teams
        self._games = games

    def fetchall(self, sql, params=()):
        if "FROM teams" in sql:
            return self._teams
        return self._games


class StubEngine:
    """Always predicts the given home win probability."""

    def __init__(self, p_home=0.5):
        self.p_home = p_home
        self.calls = 0

    def predict(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(home_win_probability=self.p_home)


def _team(tid, abbr, conf, div):
    return {
        "team_id": tid, "name": abbr, "city": "City",
        "abbreviation": abbr, "conference": conf, "division": div,
    }


def _game(gid, week, h, a, hs=None, as_=None, date="2024-10-01"):
    winner = None
    if hs is not None and as_ is not None:
        winner = h if hs > as_ else (a if as_ > hs else None)
    return {
        "game_id": gid, "date": date, "week": str(week),
        "home_team_id": h, "away_team_id": a,
        "home_score": hs, "away_score": as_, "winner_id": winner,
    }


TEAMS = [
    _team(1, "AE1", "AFC", "East"), _team(2, "AE2", "AFC", "East"),
    _team(3, "AW1", "AFC", "West"), _team(4, "AW2", "AFC", "West"),
    _team(5, "NE1", "NFC", "East"), _team(6, "NE2", "NFC", "East"),
    _team(7, "NW1", "NFC", "West"), _team(8, "NW2", "NFC", "West"),
]


def _mini_season():
    return [
        # Week 1 completed: team 1/3/5/7 win at home
        _game(1, 1, 1, 2, 21, 10),
        _game(2, 1, 3, 4, 28, 7),
        _game(3, 1, 5, 6, 17, 14),
        _game(4, 1, 7, 8, 30, 3),
        # Week 2 remaining (unplayed)
        _game(5, 2, 2, 1),
        _game(6, 2, 4, 3),
        _game(7, 2, 6, 5),
        _game(8, 2, 8, 7),
    ]


class TestSimulateSeason:
    def test_returns_none_without_teams_or_games(self):
        assert simulate_season(StubDB([], []), StubEngine(), 2024) is None
        assert simulate_season(StubDB(TEAMS, []), StubEngine(), 2024) is None

    def test_shape_and_probability_bounds(self):
        result = simulate_season(StubDB(TEAMS, _mini_season()), StubEngine(0.6), 2024, n_sims=200, seed=1)
        assert result["games_simulated"] == 4
        assert result["weeks_completed"] == 1
        assert len(result["teams"]) == 8
        for t in result["teams"]:
            assert 0.0 <= t["playoff_pct"] <= 100.0
            assert 0.0 <= t["division_pct"] <= 100.0
            assert t["top_seed_pct"] <= t["playoff_pct"]
            assert set(t["seed_distribution"].keys()) == {str(i) for i in range(1, 8)}

    def test_deterministic_with_seed(self):
        db = StubDB(TEAMS, _mini_season())
        r1 = simulate_season(db, StubEngine(0.55), 2024, n_sims=300, seed=42)
        r2 = simulate_season(db, StubEngine(0.55), 2024, n_sims=300, seed=42)
        assert r1["teams"] == r2["teams"]

    def test_certain_home_wins_resolve_exactly(self):
        # p_home = 1.0 → week-2 home teams always win → every team finishes 1-1;
        # both division races are decided by tiebreakers, never by record.
        result = simulate_season(StubDB(TEAMS, _mini_season()), StubEngine(1.0), 2024, n_sims=100, seed=7)
        for t in result["teams"]:
            assert t["mean_wins"] == 1.0

    def test_as_of_week_moves_played_games_back_to_simulation(self):
        games = _mini_season()
        # Play week 2 as well
        games[4:] = [
            _game(5, 2, 2, 1, 20, 10), _game(6, 2, 4, 3, 20, 10),
            _game(7, 2, 6, 5, 20, 10), _game(8, 2, 8, 7, 20, 10),
        ]
        full = simulate_season(StubDB(TEAMS, games), StubEngine(0.5), 2024, n_sims=50, seed=1)
        retro = simulate_season(StubDB(TEAMS, games), StubEngine(0.5), 2024, as_of_week=1, n_sims=50, seed=1)
        assert full["games_simulated"] == 0
        assert retro["games_simulated"] == 4
        assert retro["weeks_completed"] == 1

    def test_engine_failure_falls_back_to_coin_flip(self):
        class ExplodingEngine:
            def predict(self, **kwargs):
                raise RuntimeError("boom")

        result = simulate_season(StubDB(TEAMS, _mini_season()), ExplodingEngine(), 2024, n_sims=50, seed=1)
        assert result is not None
        assert result["games_simulated"] == 4


class TestConferenceSeeding:
    def test_leaders_and_wildcards(self):
        stats = {}
        recs = [
            (1, "AFC", "AFC East", 10, 2), (2, "AFC", "AFC East", 8, 4),
            (3, "AFC", "AFC West", 9, 3), (4, "AFC", "AFC West", 11, 1),
        ]
        for tid, conf, div, w, l in recs:
            stats[tid] = {
                "team_id": tid, "conference": conf, "division": div,
                "wins": w, "losses": l, "ties": 0,
                "conf_wins": w, "conf_losses": l, "point_diff": w * 10,
            }
        finalize_win_pct(stats)
        leaders, others = conference_seeding(stats.values(), "AFC")
        assert [t["team_id"] for t in leaders] == [4, 1]
        assert [t["team_id"] for t in others] == [3, 2]
