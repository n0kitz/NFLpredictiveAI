"""Tests for the shared scraper HTTP retry helper."""

import pytest
import requests

from src.scraper.http import get_with_retry


class FakeResp:
    def __init__(self, status_code, headers=None):
        self.status_code = status_code
        self.headers = headers or {}


class FakeSession:
    """Returns/raises a scripted sequence of behaviours per .get() call."""

    def __init__(self, behaviours):
        self.behaviours = list(behaviours)
        self.calls = 0

    def get(self, url, timeout=None, **kwargs):
        b = self.behaviours[self.calls]
        self.calls += 1
        if isinstance(b, Exception):
            raise b
        return b


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    # Keep retries instant.
    monkeypatch.setattr("src.scraper.http.time.sleep", lambda *_: None)


def test_success_first_try():
    s = FakeSession([FakeResp(200)])
    resp = get_with_retry("http://x", session=s)
    assert resp.status_code == 200 and s.calls == 1


def test_retries_on_5xx_then_succeeds():
    s = FakeSession([FakeResp(503), FakeResp(500), FakeResp(200)])
    resp = get_with_retry("http://x", session=s, retries=3, backoff=0)
    assert resp.status_code == 200 and s.calls == 3


def test_retries_on_exception_then_succeeds():
    s = FakeSession([requests.exceptions.ConnectionError("boom"), FakeResp(200)])
    resp = get_with_retry("http://x", session=s, retries=3, backoff=0)
    assert resp.status_code == 200 and s.calls == 2


def test_raises_after_exhausting_retries():
    s = FakeSession([requests.exceptions.Timeout("t")] * 3)
    with pytest.raises(requests.RequestException):
        get_with_retry("http://x", session=s, retries=3, backoff=0)
    assert s.calls == 3


def test_no_retry_on_4xx():
    s = FakeSession([FakeResp(404)])
    resp = get_with_retry("http://x", session=s, retries=3, backoff=0)
    assert resp.status_code == 404 and s.calls == 1


def test_honours_retry_after_header(monkeypatch):
    waits = []
    monkeypatch.setattr("src.scraper.http.time.sleep", lambda s: waits.append(s))
    s = FakeSession([FakeResp(429, {"Retry-After": "2"}), FakeResp(200)])
    resp = get_with_retry("http://x", session=s, retries=3, backoff=0)
    assert resp.status_code == 200
    assert waits and waits[0] >= 2.0  # Retry-After honoured (plus jitter)
