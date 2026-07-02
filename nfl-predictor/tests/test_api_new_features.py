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
