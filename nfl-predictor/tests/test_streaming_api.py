"""API contract for the streaming endpoint."""

from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


class TestStreamingCandidates:
    def test_rejects_non_streamable_position(self):
        r = client.post("/api/fantasy/streaming", json={"position": "WR", "week": 1})
        assert r.status_code == 422

    def test_rejects_oversized_exclude_list(self):
        r = client.post(
            "/api/fantasy/streaming",
            json={"position": "QB", "week": 1, "exclude_player_ids": list(range(30))},
        )
        assert r.status_code == 422

    def test_defaults_to_active_season(self):
        r = client.post("/api/fantasy/streaming", json={"position": "DST", "week": 1})
        assert r.status_code == 200
        body = r.json()
        assert body["season"] > 2000
        assert body["position"] == "DST"

    def test_response_shape(self):
        r = client.post("/api/fantasy/streaming", json={"position": "DST", "week": 1})
        assert r.status_code == 200
        body = r.json()
        assert "candidates" in body
        assert isinstance(body["candidates"], list)
