"""Regression guard for the ESPN 403 outage of 2026-08-20.

``site.api.espn.com`` began rejecting requests whose ``User-Agent`` is a custom
or browser-spoofed string, while still serving honest HTTP-client identifiers
(``curl/*``, ``python-requests/*``). Both ESPN scrapers used to send a custom UA
and consequently got 403 on all 32 teams, silently importing nothing.

These tests pin the policy: scrapers that talk to ESPN must leave the default
``requests`` User-Agent in place. Scrapers for other hosts are unaffected —
pro-football-reference in particular *requires* a browser-like UA.
"""

import requests

from src.scraper.roster_scraper import RosterScraper
from src.scraper.schedule_scraper import ScheduleScraper

DEFAULT_UA = requests.utils.default_user_agent()


class TestEspnScrapersUseDefaultUserAgent:
    """ESPN rejects custom UAs — these scrapers must not set one."""

    def test_roster_scraper_keeps_default_user_agent(self):
        scraper = RosterScraper()
        assert scraper._session.headers["User-Agent"] == DEFAULT_UA

    def test_schedule_scraper_keeps_default_user_agent(self):
        scraper = ScheduleScraper()
        assert scraper._session.headers["User-Agent"] == DEFAULT_UA

    def test_espn_scrapers_never_spoof_a_browser(self):
        """A ``Mozilla/...`` UA is exactly what ESPN 403s."""
        for scraper in (RosterScraper(), ScheduleScraper()):
            ua = scraper._session.headers["User-Agent"]
            assert "Mozilla" not in ua, f"{type(scraper).__name__} spoofs a browser UA"

    def test_default_user_agent_is_an_allowed_client_identifier(self):
        """The default UA must stay in the family ESPN allows."""
        assert DEFAULT_UA.startswith("python-requests/")
