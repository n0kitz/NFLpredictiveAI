"""API contract for the roster-aware endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


class TestStartSitRank:
    def test_rejects_bad_scoring(self):
        r = client.post(
            "/api/fantasy/start-sit/rank",
            json={"player_ids": [1, 2], "week": 1, "scoring": "superflex"},
        )
        assert r.status_code == 422

    def test_rejects_oversized_roster(self):
        r = client.post(
            "/api/fantasy/start-sit/rank",
            json={"player_ids": list(range(30)), "week": 1},
        )
        assert r.status_code == 422

    def test_empty_list_returns_empty_ranking(self):
        r = client.post(
            "/api/fantasy/start-sit/rank", json={"player_ids": [], "week": 1}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ranked"] == []
        assert body["scoring"] == "standard"

    def test_defaults_to_standard_scoring(self):
        r = client.post(
            "/api/fantasy/start-sit/rank", json={"player_ids": [], "week": 1}
        )
        assert r.json()["scoring"] == "standard"


class TestMyTeamLineup:
    def test_rejects_bad_league_size(self):
        r = client.post(
            "/api/fantasy/my-team/lineup",
            json={"player_ids": [1], "week": 1, "league_size": 99},
        )
        assert r.status_code == 422

    def test_unknown_players_yield_404_not_500(self):
        r = client.post(
            "/api/fantasy/my-team/lineup",
            json={"player_ids": [999999], "week": 1, "season": 1999},
        )
        assert r.status_code == 404
