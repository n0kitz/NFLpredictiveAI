"""API contract for the FAAB waiver advisor endpoint."""

from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


class TestFaabRecommendations:
    def test_rejects_bad_scoring(self):
        r = client.post(
            "/api/fantasy/waiver/faab",
            json={"roster_player_ids": [1], "week": 1, "scoring": "superflex"},
        )
        assert r.status_code == 422

    def test_rejects_oversized_roster(self):
        r = client.post(
            "/api/fantasy/waiver/faab",
            json={"roster_player_ids": list(range(30)), "week": 1},
        )
        assert r.status_code == 422

    def test_rejects_budget_out_of_range(self):
        r = client.post(
            "/api/fantasy/waiver/faab",
            json={"roster_player_ids": [1], "week": 1, "budget_remaining": -5},
        )
        assert r.status_code == 422

    def test_empty_roster_returns_shape(self):
        r = client.post(
            "/api/fantasy/waiver/faab", json={"roster_player_ids": [], "week": 1}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["budget_remaining"] == 100
        assert isinstance(body["candidates"], list)

    def test_defaults_to_active_season(self):
        r = client.post(
            "/api/fantasy/waiver/faab", json={"roster_player_ids": [], "week": 1}
        )
        assert r.json()["season"] > 2000
