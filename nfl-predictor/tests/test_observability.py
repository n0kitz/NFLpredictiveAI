"""Tests for Phase 6 observability: request metrics + /api/metrics endpoint."""

from fastapi.testclient import TestClient

from src.api.app import app
from src.observability import Metrics

client = TestClient(app)


def test_metrics_unit_counts_and_buckets():
    m = Metrics()
    m.record_request(200, 10.0)
    m.record_request(200, 30.0)
    m.record_request(500, 5.0)
    snap = m.snapshot()
    assert snap["requests"] == 3
    assert snap["errors_5xx"] == 1
    assert snap["by_status"] == {"2xx": 2, "5xx": 1}
    assert snap["avg_latency_ms"] == 15.0
    assert snap["max_latency_ms"] == 30.0


def test_metrics_endpoint_shape_and_increments():
    # Make a couple of requests, then read metrics.
    client.get("/api/health")
    before = client.get("/api/metrics").json()
    assert "requests" in before and "by_status" in before
    assert "metrics_cache" in before
    assert {"hits", "misses", "hit_rate", "entries"} <= set(before["metrics_cache"])

    client.get("/api/health")
    after = client.get("/api/metrics").json()
    assert after["requests"] > before["requests"]


def test_request_id_header_present():
    r = client.get("/api/health")
    assert r.headers.get("X-Request-ID")
    # caller-supplied id is echoed back
    r2 = client.get("/api/health", headers={"X-Request-ID": "test-rid-123"})
    assert r2.headers.get("X-Request-ID") == "test-rid-123"
