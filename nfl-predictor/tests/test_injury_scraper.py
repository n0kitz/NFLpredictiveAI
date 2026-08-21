"""Tests for InjuryScraper and related constants."""

import pytest

from src.scraper.injury_scraper import (
    InjuryScraper,
    ESPN_TEAM_MAP,
    STADIUM_COORDS,
    TEAM_NAME_TO_ABBR,
    evaluate_injury_import,
    parse_injuries,
)


class TestKeyPlayerFilter:
    """filter_key_players() keeps position + significant status only."""

    def _make_injury(self, position: str, status: str, team: str = "KC") -> dict:
        return {
            "team_abbr": team,
            "player_name": "Test Player",
            "position": position,
            "injury_status": status,
            "report_date": "2026-04-13",
        }

    def test_keeps_key_position_significant_status(self):
        scraper = InjuryScraper()
        injuries = [self._make_injury("QB", "Out")]
        result = scraper.filter_key_players(injuries)
        assert len(result) == 1

    def test_drops_non_fantasy_position(self):
        """Defensive/line positions score no fantasy points individually."""
        scraper = InjuryScraper()
        assert scraper.filter_key_players([self._make_injury("OT", "Out")]) == []
        assert scraper.filter_key_players([self._make_injury("CB", "IR")]) == []

    def test_keeps_kicker(self):
        """Kickers are a scoring roster slot — an injured K must be flagged."""
        scraper = InjuryScraper()
        result = scraper.filter_key_players([self._make_injury("K", "Out")])
        assert len(result) == 1

    def test_keeps_questionable_status(self):
        """FantasyScorer._INJURY_RULES discounts Questionable to 0.7x.

        Dropping the status here made that rule unreachable, so a questionable
        starter was projected as fully healthy.
        """
        scraper = InjuryScraper()
        result = scraper.filter_key_players([self._make_injury("WR", "Questionable")])
        assert len(result) == 1

    def test_keeps_ir_status(self):
        scraper = InjuryScraper()
        injuries = [self._make_injury("RB", "IR")]
        result = scraper.filter_key_players(injuries)
        assert len(result) == 1

    def test_keeps_doubtful_status(self):
        scraper = InjuryScraper()
        injuries = [self._make_injury("TE", "Doubtful")]
        result = scraper.filter_key_players(injuries)
        assert len(result) == 1

    def test_mixed_list(self):
        scraper = InjuryScraper()
        injuries = [
            self._make_injury("QB", "Out"),  # kept
            self._make_injury("K", "Out"),  # kept: kickers score
            self._make_injury("WR", "Questionable"),  # kept: 0.7x discount
            self._make_injury("CB", "IR"),  # dropped: no fantasy value
            self._make_injury("RB", "Active"),  # dropped: not an impact status
        ]
        result = scraper.filter_key_players(injuries)
        assert len(result) == 3


class TestTeamResolution:
    """Injuries must carry a resolvable team.

    ESPN's live payload (verified 2026-08-21) has NO ``team`` key: each of the
    32 entries is ``{'id', 'displayName', 'injuries'}`` with displayName like
    "Arizona Cardinals". The scraper read ``entry["team"]["abbreviation"]``, so
    every row came back with team_abbr="" and fetch_conditions.py grouped them
    all under the empty string — which is why injury_reports stayed at 0 rows.
    """

    def _payload(self, display_name: str = "Arizona Cardinals") -> dict:
        return {
            "injuries": [
                {
                    "id": "22",
                    "displayName": display_name,
                    "injuries": [
                        {
                            "status": "Questionable",
                            "athlete": {
                                "displayName": "Marvin Harrison Jr.",
                                "position": {"abbreviation": "WR"},
                            },
                        }
                    ],
                }
            ]
        }

    def test_resolves_team_from_display_name(self):
        rows = parse_injuries(self._payload())
        assert len(rows) == 1
        assert rows[0]["team_abbr"] == "ARI"
        assert rows[0]["player_name"] == "Marvin Harrison Jr."
        assert rows[0]["position"] == "WR"
        assert rows[0]["injury_status"] == "Questionable"

    @pytest.mark.parametrize(
        "display_name,expected",
        [
            ("Arizona Cardinals", "ARI"),
            ("Green Bay Packers", "GB"),
            ("Kansas City Chiefs", "KC"),
            ("Las Vegas Raiders", "LV"),
            ("Los Angeles Rams", "LAR"),
            ("Los Angeles Chargers", "LAC"),
            ("New York Giants", "NYG"),
            ("New York Jets", "NYJ"),
            ("Washington Commanders", "WAS"),
            ("Jacksonville Jaguars", "JAX"),
        ],
    )
    def test_ambiguous_city_names_resolve_correctly(self, display_name, expected):
        """Same-city pairs (LAR/LAC, NYG/NYJ) must not collapse into one team."""
        rows = parse_injuries(self._payload(display_name))
        assert rows[0]["team_abbr"] == expected

    def test_every_nfl_team_name_resolves(self):
        """All 32 display names map to a known abbreviation."""
        unresolved = [
            n for n in TEAM_NAME_TO_ABBR if TEAM_NAME_TO_ABBR[n] not in STADIUM_COORDS
        ]
        assert unresolved == []
        assert len(TEAM_NAME_TO_ABBR) == 32

    def test_unresolvable_team_is_dropped_not_blanked(self):
        """A row we cannot attribute is dropped — never stored with team_abbr=''."""
        rows = parse_injuries(self._payload("Springfield Isotopes"))
        assert rows == []

    def test_missing_athlete_name_is_dropped(self):
        payload = {
            "injuries": [
                {
                    "displayName": "Arizona Cardinals",
                    "injuries": [
                        {
                            "status": "Out",
                            "athlete": {"position": {"abbreviation": "WR"}},
                        }
                    ],
                }
            ]
        }
        assert parse_injuries(payload) == []

    def test_empty_payload(self):
        assert parse_injuries({}) == []
        assert parse_injuries({"injuries": []}) == []


class TestEvaluateInjuryImport:
    """An import that fetches rows but stores none must fail loudly.

    injury_reports sat at 0 for months while the fetch reported success; the
    same silent-no-op class already cost sessions on roster and ADP imports.
    """

    def test_fetched_but_none_stored_is_a_failure(self):
        ok, message = evaluate_injury_import(fetched=800, relevant=95, stored=0)
        assert ok is False
        assert "0" in message

    def test_nothing_fetched_is_a_failure(self):
        ok, _ = evaluate_injury_import(fetched=0, relevant=0, stored=0)
        assert ok is False

    def test_stored_rows_succeed(self):
        ok, message = evaluate_injury_import(fetched=800, relevant=95, stored=95)
        assert ok is True
        assert message.startswith("OK")

    def test_partial_store_warns_but_succeeds(self):
        ok, message = evaluate_injury_import(fetched=800, relevant=95, stored=40)
        assert ok is True
        assert "PARTIAL" in message


class TestEspnMappingComplete:
    """ESPN_TEAM_MAP covers all 32 current teams (internal abbreviations)."""

    def test_all_32_teams_covered(self):
        """Every internal abbreviation in STADIUM_COORDS appears as a value in ESPN_TEAM_MAP."""
        internal_abbrs = set(STADIUM_COORDS.keys())
        mapped_abbrs = set(ESPN_TEAM_MAP.values())
        missing = internal_abbrs - mapped_abbrs
        assert (
            missing == set()
        ), f"Internal abbreviations not in ESPN_TEAM_MAP values: {missing}"

    def test_known_remaps(self):
        """ESPN-specific remaps are present."""
        assert ESPN_TEAM_MAP.get("JAC") == "JAX"
        assert ESPN_TEAM_MAP.get("LA") == "LAR"
        assert ESPN_TEAM_MAP.get("WSH") == "WAS"

    def test_stadium_coords_all_32(self):
        assert len(STADIUM_COORDS) == 32

    def test_dome_teams_flagged(self):
        dome_teams = {
            "ARI",
            "ATL",
            "DAL",
            "DET",
            "HOU",
            "IND",
            "LAC",
            "LAR",
            "LV",
            "MIN",
            "NO",
        }
        for abbr in dome_teams:
            assert abbr in STADIUM_COORDS, f"{abbr} missing from STADIUM_COORDS"
            _, _, is_dome = STADIUM_COORDS[abbr]
            assert is_dome, f"{abbr} should be flagged as dome"
