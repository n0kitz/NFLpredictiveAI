"""Tests for the improvement-round endpoints: data coverage, accuracy detail,
model feature importance, playoff odds, QB history."""

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.database.db import DEFAULT_DB_PATH

pytestmark = pytest.mark.skipif(
    not DEFAULT_DB_PATH.exists(),
    reason="Real database not found — run scraper first",
)

client = TestClient(app)


# ── Data coverage ───────────────────────────────────────────────────────────────

class TestDataCoverage:
    def test_coverage_shape(self):
        r = client.get("/api/data/coverage")
        assert r.status_code == 200
        data = r.json()
        assert "tables" in data and "generated_at" in data
        tables = {t["table"]: t for t in data["tables"]}
        assert "games" in tables
        assert "player_weekly_stats" in tables
        for entry in data["tables"]:
            assert entry["rows"] >= 0
            assert entry["powers"]

    def test_coverage_games_season_range(self):
        r = client.get("/api/data/coverage")
        games = next(t for t in r.json()["tables"] if t["table"] == "games")
        assert games["season_min"] == 1990
        assert games["season_max"] >= 2024
        assert games["rows"] > 9000


# ── Accuracy detail ─────────────────────────────────────────────────────────────

class TestAccuracyDetail:
    def test_detail_shape_2024(self):
        r = client.get("/api/accuracy/detail?season=2024")
        assert r.status_code == 200
        data = r.json()
        assert data["season"] == 2024
        assert data["total_games"] > 200
        assert 0.0 <= data["accuracy"] <= 1.0
        assert len(data["weekly"]) >= 17
        for wk in data["weekly"]:
            assert wk["correct"] <= wk["total"]
            assert 0.0 <= wk["accuracy"] <= 1.0
        assert len(data["best_calls"]) == 5
        assert len(data["biggest_misses"]) == 5
        assert all(g["correct"] for g in data["best_calls"])
        assert not any(g["correct"] for g in data["biggest_misses"])
        # Notable games sorted by confidence descending
        probs = [g["winner_prob"] for g in data["biggest_misses"]]
        assert probs == sorted(probs, reverse=True)
        assert all(g["game_id"] > 0 for g in data["best_calls"])

    def test_detail_cached_second_call_identical(self):
        r1 = client.get("/api/accuracy/detail?season=2024")
        r2 = client.get("/api/accuracy/detail?season=2024")
        assert r1.json() == r2.json()

    def test_detail_season_bounds(self):
        assert client.get("/api/accuracy/detail?season=1800").status_code == 422
        assert client.get("/api/accuracy/detail?season=99999999999").status_code == 422

    def test_detail_missing_season_param(self):
        assert client.get("/api/accuracy/detail").status_code == 422

    def test_detail_empty_season_graceful(self):
        r = client.get("/api/accuracy/detail?season=2099")
        assert r.status_code == 200
        data = r.json()
        assert data["total_games"] == 0
        assert data["weekly"] == []
        assert data["best_calls"] == []


# ── Playoff odds ────────────────────────────────────────────────────────────────

class TestPlayoffOdds:
    def test_playoff_odds_retro_2024(self):
        # as_of_week=17 leaves only week 18 to simulate — fast
        r = client.get("/api/seasons/2024/playoff-odds?as_of_week=17&sims=100")
        assert r.status_code == 200
        data = r.json()
        assert data["season"] == 2024
        assert data["n_sims"] == 100
        assert data["games_simulated"] > 0
        assert len(data["teams"]) == 32
        for conf in ("AFC", "NFC"):
            mass = sum(t["playoff_pct"] for t in data["teams"] if t["conference"] == conf)
            assert abs(mass - 700.0) < 1.0  # 7 seeds × 100%
        for t in data["teams"]:
            assert t["top_seed_pct"] <= t["division_pct"] + 0.11  # seed 1 is always a division winner

    def test_playoff_odds_deterministic_cache(self):
        r1 = client.get("/api/seasons/2024/playoff-odds?as_of_week=17&sims=100")
        r2 = client.get("/api/seasons/2024/playoff-odds?as_of_week=17&sims=100")
        assert r1.json()["teams"] == r2.json()["teams"]

    def test_playoff_odds_bounds(self):
        assert client.get("/api/seasons/1800/playoff-odds").status_code == 422
        assert client.get("/api/seasons/2024/playoff-odds?as_of_week=25").status_code == 422
        assert client.get("/api/seasons/2024/playoff-odds?sims=5").status_code == 422
        assert client.get("/api/seasons/2024/playoff-odds?sims=999999").status_code == 422

    def test_playoff_odds_missing_season(self):
        assert client.get("/api/seasons/2098/playoff-odds").status_code == 404


# ── Team advanced stats + QB history ────────────────────────────────────────────

class TestTeamAdvancedStats:
    def test_advanced_latest_season(self):
        r = client.get("/api/teams/KC/advanced")
        assert r.status_code == 200
        data = r.json()
        assert data["team_abbr"] == "KC"
        assert data["season"] >= 2020
        assert data["yards_per_play"] is not None
        for col, rank in data["ranks"].items():
            assert 1 <= rank <= 32, col

    def test_advanced_specific_season(self):
        r = client.get("/api/teams/KC/advanced?season=2024")
        assert r.status_code == 200
        assert r.json()["season"] == 2024

    def test_advanced_missing_season(self):
        assert client.get("/api/teams/KC/advanced?season=1991").status_code == 404

    def test_advanced_unknown_team(self):
        assert client.get("/api/teams/ZZZZ/advanced").status_code == 404


class TestTeamQBHistory:
    def test_qb_history_shape(self):
        r = client.get("/api/teams/KC/qb-history")
        assert r.status_code == 200
        data = r.json()
        assert data["team_abbr"] == "KC"
        assert len(data["seasons"]) >= 10  # 2010+ coverage
        latest = data["seasons"][0]
        assert latest["starters"][0]["starts"] >= 1
        # weekly detail matches detail_season and covers a full-ish season
        assert data["detail_season"] == latest["season"]
        assert len(data["weeks"]) >= 15
        assert all(1 <= w["week"] <= 22 for w in data["weeks"])

    def test_qb_history_specific_season(self):
        r = client.get("/api/teams/KC/qb-history?season=2018")
        assert r.status_code == 200
        data = r.json()
        assert data["detail_season"] == 2018
        assert all(w["qb_name"] for w in data["weeks"])

    def test_qb_history_starters_sorted_by_starts(self):
        r = client.get("/api/teams/KC/qb-history")
        for season in r.json()["seasons"]:
            starts = [s["starts"] for s in season["starters"]]
            assert starts == sorted(starts, reverse=True)

    def test_qb_history_unknown_team(self):
        assert client.get("/api/teams/ZZZZ/qb-history").status_code == 404


# ── Spread sign convention ──────────────────────────────────────────────────────

class TestSpreadSignConvention:
    """predicted_spread = home_score - away_score (positive = home favored).

    Regression guard: the Monte Carlo simulate endpoint and the frontend once
    interpreted it Vegas-style (negative = home favored), inverting margins.
    """

    def test_retrodiction_spread_agrees_with_pick(self):
        # Find a decisively predicted played game and check sign coherence
        r = client.get("/api/accuracy/detail?season=2024")
        best = r.json()["best_calls"][0]  # most confident correct pick
        retro = client.get(f"/api/games/{best['game_id']}/retrodiction").json()
        if retro.get("predicted_spread") is None:
            pytest.skip("spread model not loaded")
        home_picked = retro["home_prob"] > retro["away_prob"]
        if home_picked:
            assert retro["predicted_spread"] > 0
        else:
            assert retro["predicted_spread"] < 0

    def test_simulated_favorite_outscores_on_average(self):
        r = client.post(
            "/api/games/simulate",
            json={"home_team": "PHI", "away_team": "KC", "n": 500},
        )
        assert r.status_code == 200
        d = r.json()
        if d["home_win_pct"] >= 0.65:
            assert d["avg_home_score"] > d["avg_away_score"]
        elif d["home_win_pct"] <= 0.35:
            assert d["avg_away_score"] > d["avg_home_score"]


# ── Model info feature importance ───────────────────────────────────────────────

class TestModelFeatureImportance:
    def test_importance_present_when_ml_loaded(self):
        r = client.get("/api/model/info")
        assert r.status_code == 200
        data = r.json()
        assert "feature_importance" in data
        if data["ml_available"]:
            assert len(data["feature_importance"]) > 0
            assert len(data["feature_importance"]) <= 12
            imps = [e["importance"] for e in data["feature_importance"]]
            assert imps == sorted(imps, reverse=True)
            for e in data["feature_importance"]:
                assert e["feature"] and e["label"]
                assert e["importance"] >= 0.0
        else:
            assert data["feature_importance"] == []
