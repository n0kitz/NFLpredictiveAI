"""
Weekly scraper script.

Scrapes the current and previous season to catch any updates.
Designed to be run via cron every Wednesday.
"""

import atexit
import fcntl
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import timedelta

from src.config import current_nfl_season, settings
from src.database.db import create_database
from src.scraper.pfr_scraper import PFRScraper
from src.scraper.schedule_scraper import ScheduleScraper
from src.scraper.odds_scraper import OddsScraper
from src.scraper.injury_scraper import InjuryScraper
from src.scraper.weather_scraper import WeatherScraper
from src.scraper.roster_scraper import RosterScraper, should_purge_stale

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


_LOCK_PATH = Path(__file__).parent.parent / "data" / ".weekly_scrape.lock"


def _acquire_singleton_lock():
    """Take an exclusive non-blocking file lock so two scrapes can't overlap.

    Returns the open file descriptor on success, or None if another run already
    holds the lock. The OS releases the flock when this process exits; we also
    register an atexit close (which keeps a reference so the fd isn't GC'd).
    """
    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = open(_LOCK_PATH, "w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fd.close()
        return None
    atexit.register(fd.close)
    return fd


def core_scrape_failed(espn_games: int, pfr_seasons_ok: int) -> bool:
    """Whether the run failed at its core job of refreshing game results.

    Either source is enough. ESPN's scoreboard carries schedule and final
    scores; Pro-Football-Reference sits behind Cloudflare and 403s for weeks at
    a time, which used to mark every run as failed even though the results had
    already landed via ESPN.
    """
    return espn_games == 0 and pfr_seasons_ok == 0


def refresh_rosters(db, rosters: dict, season: int) -> dict:
    """Store an ESPN roster fetch as a snapshot of `season`.

    Mirrors scripts/import_rosters.py: every entry of the run shares one
    `fetched_at`, and entries the run did not refresh are purged so a traded
    player stops appearing on both teams -- but only after full 32-team
    coverage (see should_purge_stale).

    Returns counts: entries upserted, teams that returned players, rows purged.
    """
    fetched_at = datetime.now(timezone.utc).isoformat()
    entries = 0
    for team_abbr, players in rosters.items():
        team = db.get_team_by_abbreviation(team_abbr)
        if not team:
            continue
        for p in players:
            if not p.get("espn_id") or not p.get("full_name"):
                continue
            player_id = db.upsert_player(p)
            db.upsert_roster_entry(
                {
                    "player_id": player_id,
                    "team_id": team["team_id"],
                    "season": season,
                    "depth_position": p.get("depth_position"),
                    "is_starter": p.get("is_starter", False),
                    "roster_status": p.get("status", "Active"),
                    "fetched_at": fetched_at,
                }
            )
            entries += 1
    db.commit()

    teams = sum(1 for players in rosters.values() if players)
    purged = 0
    if entries and should_purge_stale(teams):
        purged = db.purge_stale_roster_entries(season, fetched_at)
    return {"entries": entries, "teams": teams, "purged": purged}


def main():
    if _acquire_singleton_lock() is None:
        logger.warning(
            "Another weekly scrape already holds %s — exiting to avoid overlap.",
            _LOCK_PATH,
        )
        return

    current_season = current_nfl_season()
    start = current_season - 1  # Also refresh prior season for corrections
    end = current_season

    logger.info(f"Weekly scrape: seasons {start}–{end}")

    db = create_database()
    # Fatal errors mark the run as failed in the scrape log. The core purpose of
    # this job is scraping games, so a total failure of the season-scrape loop is
    # fatal; downstream enrichment steps are best-effort (logged, non-fatal).
    fatal_errors: list = []

    # Step 0: Fetch upcoming schedule from ESPN (fast, no Cloudflare issues)
    espn_games = 0
    try:
        schedule_scraper = ScheduleScraper(db)
        esp_games = schedule_scraper.fetch_season(current_season)
        espn_games = len(esp_games)
        esp_ins, esp_skip = schedule_scraper.store_games(esp_games)
        if esp_ins > 0:
            db.calculate_team_season_stats(current_season)
        logger.info(f"ESPN schedule: {esp_ins} inserted/updated, {esp_skip} skipped")
    except Exception as e:
        logger.error(f"ESPN schedule fetch failed (non-fatal): {e}")

    scraper = PFRScraper(db, rate_limit=4.0)
    scraper.initialize_teams()

    # Force re-scrape current season (don't skip completed)
    seasons_scraped_ok = 0
    for season in range(start, end + 1):
        logger.info(f"Scraping season {season}...")
        try:
            games = scraper.scrape_season_schedule(season)
            if games:
                inserted, skipped = scraper.store_games(games)
                db.calculate_team_season_stats(season)
                db.update_scrape_status(season, "full", "completed")
                seasons_scraped_ok += 1
                logger.info(f"Season {season}: {inserted} inserted, {skipped} skipped")
            else:
                logger.warning(f"No games found for season {season}")
        except Exception as e:
            logger.error(f"Error scraping season {season}: {e}")
            fatal_errors.append(f"season {season}: {e}")

    # Game results come from ESPN or PFR; the run only missed its purpose if
    # neither delivered.
    if core_scrape_failed(espn_games, seasons_scraped_ok):
        fatal_errors.append("no game results from ESPN or PFR")
    elif seasons_scraped_ok == 0:
        logger.warning("PFR unavailable — game results came from ESPN only")

    # Enrich prediction history with completed game results
    try:
        enriched = db.enrich_prediction_history()
        if enriched:
            logger.info(f"Enriched {enriched} prediction(s) with game results")
    except Exception as e:
        logger.error(f"Error enriching prediction history: {e}")

    # Save a pick for every game of the upcoming week. Predictions are only
    # graded by games played afterwards, so this is what feeds /history.
    try:
        from src.prediction.engine import PredictionEngine
        from src.prediction.weekly_picks import save_upcoming_picks

        pick_week = db.get_upcoming_week(current_season)
        picks = save_upcoming_picks(db, PredictionEngine(db), current_season, pick_week)
        logger.info(
            "Weekly picks (week %s): %s saved, %s already present, %s failed",
            pick_week,
            picks["saved"],
            picks["skipped"],
            picks["failed"],
        )
    except Exception as e:
        logger.error(f"Saving weekly picks failed (non-fatal): {e}")

    # Fetch upcoming odds (silently skip if ODDS_API_KEY not set)
    odds_api_key = settings.odds_api_key
    if odds_api_key:
        try:
            odds_scraper = OddsScraper()
            games_odds = odds_scraper.fetch_upcoming_odds(odds_api_key)
            stored = 0
            for g in games_odds:
                home_team = db.get_team_by_abbreviation(g["home_team"])
                away_team = db.get_team_by_abbreviation(g["away_team"])
                if not home_team or not away_team:
                    continue
                home_team_id = home_team["team_id"]
                away_team_id = away_team["team_id"]
                game_date = g["game_date"]
                db_game = db.fetchone(
                    """SELECT game_id FROM games
                       WHERE home_team_id=? AND away_team_id=?
                         AND date BETWEEN date(?,' -1 day') AND date(?,' +1 day')
                       LIMIT 1""",
                    (home_team_id, away_team_id, game_date, game_date),
                )
                db.upsert_game_odds(
                    {
                        "game_id": db_game["game_id"] if db_game else None,
                        "external_game_id": g["external_game_id"],
                        "home_team_id": home_team_id,
                        "away_team_id": away_team_id,
                        "game_date": game_date,
                        "opening_spread": g["spread"],
                        "over_under": g["over_under"],
                        "home_implied_prob": g["home_implied_prob"],
                        "away_implied_prob": g["away_implied_prob"],
                        "fetched_at": g["fetched_at"],
                    }
                )
                stored += 1
            logger.info(f"Odds fetch complete: {stored} game(s) stored")
            if odds_scraper.last_requests_remaining is not None:
                logger.info(
                    "API quota — used: %s, remaining: %s",
                    odds_scraper.last_requests_used,
                    odds_scraper.last_requests_remaining,
                )
        except Exception as e:
            logger.error(f"Odds fetch failed (non-fatal): {e}")
    else:
        logger.info("ODDS_API_KEY not set — skipping odds fetch")

    # Fetch injury reports and weather conditions
    try:
        inj_scraper = InjuryScraper()
        wx_scraper = WeatherScraper()

        all_injuries = inj_scraper.fetch_injuries()
        key_injuries = inj_scraper.filter_key_players(all_injuries)

        by_team: dict = {}
        for inj in key_injuries:
            by_team.setdefault(inj["team_abbr"], []).append(inj)

        inj_stored = 0
        for abbr, injuries in by_team.items():
            team = db.get_team_by_abbreviation(abbr)
            if team:
                db.upsert_injuries(team["team_id"], injuries)
                inj_stored += len(injuries)
        logger.info(f"Conditions: stored {inj_stored} key injury record(s)")

        today = datetime.now().date()
        window_end = today + timedelta(days=14)
        upcoming = db.fetchall(
            """
            SELECT g.game_id, g.date, g.home_team_id, t.abbreviation AS home_abbr
            FROM games g JOIN teams t ON g.home_team_id = t.team_id
            WHERE g.date BETWEEN ? AND ? AND g.home_score IS NULL
            ORDER BY g.date ASC
            """,
            (str(today), str(window_end)),
        )
        wx_stored = 0
        for row in upcoming:
            wx = wx_scraper.fetch_game_weather(row["home_abbr"], str(row["date"]))
            if wx is None:
                continue
            db.upsert_game_weather(
                {
                    "game_id": row["game_id"],
                    "home_team_id": row["home_team_id"],
                    "game_date": str(row["date"]),
                    "is_dome": wx.get("is_dome", False),
                    "temperature_c": wx.get("temperature_c"),
                    "wind_speed_kmh": wx.get("wind_speed_kmh"),
                    "precipitation_mm": wx.get("precipitation_mm"),
                    "weather_code": wx.get("weather_code"),
                    "condition": wx.get("condition", "Unknown"),
                    "is_adverse": wx.get("is_adverse", False),
                    "fetched_at": str(today),
                }
            )
            wx_stored += 1
        logger.info(f"Conditions: stored weather for {wx_stored} upcoming game(s)")
    except Exception as e:
        logger.error(f"Conditions fetch failed (non-fatal): {e}")

    # Update rosters for all 32 teams
    try:
        roster_scraper = RosterScraper()
        rosters = roster_scraper.fetch_all_rosters()
        roster_result = refresh_rosters(db, rosters, current_season)
        logger.info(
            "Roster update: %(entries)s entries from %(teams)s/32 teams, "
            "%(purged)s stale purged" % roster_result
        )
    except Exception as e:
        logger.error(f"Roster fetch failed (non-fatal): {e}")

    # Import weekly player stats (nflverse) for ML features + K/DST fantasy
    try:
        from src.scraper.player_weekly_importer import (
            aggregate_kicker_dst_season_stats,
            aggregate_offense_season_stats,
            fetch_stats_player_week,
            import_kicker_weekly_stats,
            import_player_weekly_stats,
        )
        from src.scraper.dst_importer import import_dst_weekly_stats

        spw = fetch_stats_player_week([current_season])
        rows = import_player_weekly_stats(db, [current_season], df=spw)
        k_rows = import_kicker_weekly_stats(db, [current_season], df=spw)
        dst_rows = import_dst_weekly_stats(db, [current_season], df=spw)
        aggregate_kicker_dst_season_stats(db, [current_season])
        # Offensive season totals also come from weekly rows (nfl_data_py's
        # seasonal feed is dead for 2025+); draft rankings depend on them.
        aggregate_offense_season_stats(db, [current_season])
        logger.info(
            f"Weekly player stats: {rows} offense, {k_rows} kicker, "
            f"{dst_rows} DST rows upserted for {current_season}"
        )
    except Exception as e:
        logger.error(f"Weekly player stats import failed (non-fatal): {e}")

    # NOTE: Player-model retraining is intentionally MANUAL (decided 2026-06-29).
    # Training is heavy and the cron writes artifacts to disk without review, so
    # the weekly job only refreshes data + projections. To retrain, run from the
    # clean venv:  python scripts/train_player_models.py

    # Generate fantasy projections for the upcoming week (uses ML if loaded).
    # Stale rows are deleted first — the projections endpoint serves cached
    # rows, so leftovers from an older server (e.g. heuristic-only) would
    # otherwise mask the fresh run.
    try:
        from src.prediction.fantasy_scorer import FantasyScorer

        scorer = FantasyScorer(db)
        # The week still to be played -- the cron runs on Wednesday, when the
        # most recently completed week is already history.
        current_week = db.get_upcoming_week(current_season)
        db.execute(
            "DELETE FROM fantasy_projections WHERE season = ? AND week = ?",
            (current_season, current_week),
        )
        db.commit()
        projections = scorer.generate_weekly_projections(
            season=current_season, week=current_week
        )
        logger.info(
            f"Fantasy projections generated for week {current_week} ({len(projections)} players)"
        )
    except Exception as e:
        logger.error(f"Fantasy projection generation failed (non-fatal): {e}")

    # Write scrape log (success or failure)
    fatal_error = "; ".join(fatal_errors)
    try:
        db.write_scrape_log(
            success=not fatal_errors,
            error_message=fatal_error or None,
            seasons_scraped=f"{start}-{end}",
        )
    except Exception as e:
        logger.warning(f"Failed to write scrape log: {e}")

    db.close()
    if fatal_errors:
        logger.error(f"Weekly scrape finished WITH ERRORS: {fatal_error}")
        sys.exit(1)
    logger.info("Weekly scrape complete.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Weekly scrape aborted: {e}", exc_info=True)
        raise
