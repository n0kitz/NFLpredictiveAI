"""Guard against silent roster-import failures.

On 2026-08-20 every ESPN fetch returned 403, so ``import_rosters.py`` upserted
zero players — yet it printed "Roster import complete" and exited 0. Cron would
have reported a healthy run while the draft board quietly went stale.

``evaluate_roster_import`` makes that outcome explicit so the script can exit
non-zero on a total failure and warn on a partial one.
"""

from src.scraper.roster_scraper import evaluate_roster_import


class TestTotalFailure:
    def test_zero_entries_is_a_failure(self):
        ok, message = evaluate_roster_import(teams_fetched=0, entries_upserted=0)
        assert ok is False
        assert "0/32" in message

    def test_failure_message_mentions_the_cause(self):
        _, message = evaluate_roster_import(teams_fetched=0, entries_upserted=0)
        assert "no roster entries" in message.lower()


class TestPartialImport:
    def test_missing_teams_still_succeeds_but_warns(self):
        ok, message = evaluate_roster_import(teams_fetched=30, entries_upserted=2500)
        assert ok is True
        assert "30/32" in message

    def test_entries_without_full_team_coverage_is_not_silent(self):
        _, message = evaluate_roster_import(teams_fetched=31, entries_upserted=2800)
        assert message, "a partial import must produce a visible message"


class TestFullSuccess:
    def test_all_teams_reports_ok(self):
        ok, message = evaluate_roster_import(teams_fetched=32, entries_upserted=2961)
        assert ok is True
        assert "32/32" in message

    def test_expected_teams_is_parametric(self):
        ok, _ = evaluate_roster_import(
            teams_fetched=4, entries_upserted=100, expected_teams=4
        )
        assert ok is True
