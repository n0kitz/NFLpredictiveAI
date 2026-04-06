"""Pro Football Reference scraper for NFL game data."""

import logging
import re
import time
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

try:
    import cloudscraper
    _HAS_CLOUDSCRAPER = True
except ImportError:
    _HAS_CLOUDSCRAPER = False

from ..database.db import Database, get_database
from .team_mappings import (
    TeamMappings, CURRENT_TEAMS, PFR_TEAM_ABBR_MAP,
    get_team_abbr_for_year
)

logger = logging.getLogger(__name__)

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

BASE_URL = "https://www.pro-football-reference.com"


@dataclass
class ScrapedGame:
    """Represents a scraped game before database insertion."""
    date: str
    season: int
    week: str
    game_type: str
    home_team_pfr: str
    away_team_pfr: str
    home_score: Optional[int]
    away_score: Optional[int]
    overtime: bool = False
    venue: Optional[str] = None
    attendance: Optional[int] = None


class PFRScraper:
    """
    Scraper for Pro Football Reference NFL game data.

    Implements rate limiting, progress tracking, and resumable scraping.
    """

    def __init__(self, db: Optional[Database] = None, rate_limit: float = 4.0):
        """
        Initialize the PFR scraper.

        Args:
            db: Database instance (uses singleton if not provided)
            rate_limit: Seconds to wait between requests (default 4.0)
        """
        self.db = db or get_database()
        self.rate_limit = rate_limit
        self.team_mappings = TeamMappings()
        self._use_cloudscraper = False

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0.0.0 Safari/537.36'
        })

        # Prepare cloudscraper session as fallback
        if _HAS_CLOUDSCRAPER:
            self._cs_session = cloudscraper.create_scraper()
        else:
            self._cs_session = None

        self._last_request_time = 0.0
        self._teams_initialized = False

    def _rate_limit_wait(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            sleep_time = self.rate_limit - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.1f}s")
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """
        Fetch and parse a page from PFR.

        Falls back to cloudscraper if requests gets a 403.

        Args:
            url: URL to fetch

        Returns:
            BeautifulSoup object or None if failed
        """
        self._rate_limit_wait()

        # Use cloudscraper directly if a previous request already switched
        session = self._cs_session if self._use_cloudscraper else self.session

        try:
            logger.debug(f"Fetching: {url}")
            response = session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 403 and not self._use_cloudscraper:
                if self._cs_session is not None:
                    logger.info("Got 403, retrying with cloudscraper...")
                    self._use_cloudscraper = True
                    self._rate_limit_wait()
                    try:
                        response = self._cs_session.get(url, timeout=30)
                        response.raise_for_status()
                        return BeautifulSoup(response.text, 'html.parser')
                    except requests.RequestException as e2:
                        logger.error(f"cloudscraper also failed for {url}: {e2}")
                        return None
                else:
                    logger.error(f"Got 403 for {url} and cloudscraper is not installed. "
                                 f"Install it with: pip install cloudscraper")
                    return None
            logger.error(f"Failed to fetch {url}: {e}")
            return None
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    def initialize_teams(self) -> None:
        """Initialize all NFL teams in the database."""
        if self._teams_initialized:
            return

        logger.info("Initializing teams in database...")

        # Initialize schema first
        self.db.init_schema()

        # Add all current teams
        for team in CURRENT_TEAMS:
            existing = self.db.get_team_by_abbreviation(team.abbreviation)
            if not existing:
                self.db.insert_team(
                    name=team.name,
                    city=team.city,
                    conference=team.conference,
                    division=team.division,
                    abbreviation=team.abbreviation,
                    franchise_id=team.franchise_id,
                    active_from=team.active_from,
                    active_until=team.active_until
                )
                logger.debug(f"Added team: {team.city} {team.name}")

        self._teams_initialized = True
        logger.info(f"Teams initialized: {len(CURRENT_TEAMS)} teams")

    def _get_team_id(self, pfr_abbr: str, year: int) -> Optional[int]:
        """
        Get database team_id from PFR abbreviation.

        Maps historical teams to their current franchise.
        """
        # Get the current abbreviation for this franchise
        current_abbr = PFR_TEAM_ABBR_MAP.get(pfr_abbr.lower())
        if not current_abbr:
            logger.warning(f"Unknown PFR abbreviation: {pfr_abbr}")
            return None

        team = self.db.get_team_by_abbreviation(current_abbr)
        if team:
            return team['team_id']

        logger.warning(f"Team not found in database: {current_abbr}")
        return None

    def scrape_season_schedule(self, season: int) -> List[ScrapedGame]:
        """
        Scrape all games for a season from PFR.

        Args:
            season: NFL season year (e.g., 2023)

        Returns:
            List of ScrapedGame objects
        """
        url = f"{BASE_URL}/years/{season}/games.htm"
        soup = self._fetch_page(url)

        if not soup:
            logger.error(f"Failed to fetch season {season} schedule")
            return []

        games = []

        # Find the games table
        table = soup.find('table', {'id': 'games'})
        if not table:
            logger.error(f"Could not find games table for season {season}")
            return []

        tbody = table.find('tbody')
        if not tbody:
            logger.error(f"Could not find tbody in games table for season {season}")
            return []

        rows = tbody.find_all('tr')

        for row in rows:
            # Skip header rows
            if row.get('class') and 'thead' in row.get('class', []):
                continue

            game = self._parse_game_row(row, season)
            if game:
                games.append(game)

        logger.info(f"Scraped {len(games)} games for {season} season")
        return games

    def _parse_game_row(self, row, season: int) -> Optional[ScrapedGame]:
        """Parse a single game row from the schedule table."""
        try:
            # Get week
            week_cell = row.find('th', {'data-stat': 'week_num'})
            if not week_cell:
                return None

            week_text = week_cell.get_text(strip=True)
            if not week_text:
                return None

            # Determine game type and week
            game_type = 'regular'
            week = week_text

            if week_text in ['WildCard', 'Wild Card']:
                game_type = 'playoff'
                week = 'Wild Card'
            elif week_text in ['Division', 'Divisional']:
                game_type = 'playoff'
                week = 'Divisional'
            elif week_text in ['ConfChamp', 'Conf. Champ.', 'Conference']:
                game_type = 'playoff'
                week = 'Conference'
            elif week_text in ['SuperBowl', 'Super Bowl']:
                game_type = 'playoff'
                week = 'Super Bowl'

            # Get date
            date_cell = row.find('td', {'data-stat': 'game_date'})
            if not date_cell:
                return None

            date_text = date_cell.get_text(strip=True)
            if not date_text or date_text == 'Playoffs':
                return None

            # Parse date
            try:
                game_date = self._parse_date(date_text, season)
            except ValueError:
                logger.warning(f"Could not parse date: {date_text}")
                return None

            # Get teams
            winner_cell = row.find('td', {'data-stat': 'winner'})
            loser_cell = row.find('td', {'data-stat': 'loser'})

            if not winner_cell or not loser_cell:
                return None

            winner_link = winner_cell.find('a')
            loser_link = loser_cell.find('a')

            if not winner_link or not loser_link:
                return None

            winner_pfr = self._extract_team_abbr(winner_link.get('href', ''))
            loser_pfr = self._extract_team_abbr(loser_link.get('href', ''))

            if not winner_pfr or not loser_pfr:
                return None

            # Get home/away indicator
            home_indicator = row.find('td', {'data-stat': 'game_location'})
            home_indicator_text = home_indicator.get_text(strip=True) if home_indicator else ''

            # @ means winner was away, empty means winner was home
            # N means neutral site (like Super Bowl)
            if home_indicator_text == '@':
                home_team = loser_pfr
                away_team = winner_pfr
            else:
                home_team = winner_pfr
                away_team = loser_pfr

            # Get scores
            winner_score_cell = row.find('td', {'data-stat': 'pts_win'})
            loser_score_cell = row.find('td', {'data-stat': 'pts_lose'})

            winner_score = None
            loser_score = None

            if winner_score_cell:
                score_text = winner_score_cell.get_text(strip=True)
                if score_text:
                    winner_score = int(score_text)

            if loser_score_cell:
                score_text = loser_score_cell.get_text(strip=True)
                if score_text:
                    loser_score = int(score_text)

            # Assign scores to home/away
            if home_indicator_text == '@':
                home_score = loser_score
                away_score = winner_score
            else:
                home_score = winner_score
                away_score = loser_score

            # Check for overtime
            overtime = False
            ot_cell = row.find('td', {'data-stat': 'overtime'})
            if ot_cell and ot_cell.get_text(strip=True):
                overtime = True

            return ScrapedGame(
                date=game_date,
                season=season,
                week=week,
                game_type=game_type,
                home_team_pfr=home_team,
                away_team_pfr=away_team,
                home_score=home_score,
                away_score=away_score,
                overtime=overtime
            )

        except Exception as e:
            logger.error(f"Error parsing game row: {e}")
            return None

    def _parse_date(self, date_text: str, season: int) -> str:
        """
        Parse date text from PFR format.

        Args:
            date_text: Date string like "September 7" or "2023-09-07"
            season: Season year for context

        Returns:
            ISO format date string (YYYY-MM-DD)
        """
        # Try ISO format first
        if re.match(r'\d{4}-\d{2}-\d{2}', date_text):
            return date_text

        # Parse "Month Day" format
        try:
            parsed = datetime.strptime(date_text, "%B %d")
            # Determine year - games from Sept-Dec are season year,
            # games from Jan-Feb are season+1 year
            if parsed.month >= 9:
                year = season
            else:
                year = season + 1
            return f"{year}-{parsed.month:02d}-{parsed.day:02d}"
        except ValueError:
            pass

        # Try abbreviated month
        try:
            parsed = datetime.strptime(date_text, "%b %d")
            if parsed.month >= 9:
                year = season
            else:
                year = season + 1
            return f"{year}-{parsed.month:02d}-{parsed.day:02d}"
        except ValueError:
            pass

        raise ValueError(f"Cannot parse date: {date_text}")

    def _extract_team_abbr(self, href: str) -> Optional[str]:
        """Extract team abbreviation from PFR URL."""
        # URL format: /teams/xxx/yyyy.htm
        match = re.search(r'/teams/([a-z]{3})/', href)
        if match:
            return match.group(1)
        return None

    def store_games(self, games: List[ScrapedGame]) -> Tuple[int, int]:
        """
        Store scraped games in the database.

        Args:
            games: List of ScrapedGame objects

        Returns:
            Tuple of (inserted_count, skipped_count)
        """
        inserted = 0
        skipped = 0

        for game in games:
            home_team_id = self._get_team_id(game.home_team_pfr, game.season)
            away_team_id = self._get_team_id(game.away_team_pfr, game.season)

            if not home_team_id or not away_team_id:
                logger.warning(
                    f"Could not find teams for game: "
                    f"{game.away_team_pfr} @ {game.home_team_pfr}"
                )
                skipped += 1
                continue

            # Determine winner
            winner_id = None
            if game.home_score is not None and game.away_score is not None:
                if game.home_score > game.away_score:
                    winner_id = home_team_id
                elif game.away_score > game.home_score:
                    winner_id = away_team_id
                # Tie: winner_id remains None

            try:
                game_id = self.db.insert_game(
                    date=game.date,
                    season=game.season,
                    week=game.week,
                    game_type=game.game_type,
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                    home_score=game.home_score,
                    away_score=game.away_score,
                    winner_id=winner_id,
                    venue=game.venue,
                    attendance=game.attendance,
                    overtime=game.overtime
                )

                if game_id:
                    inserted += 1
                else:
                    skipped += 1  # Likely duplicate
            except Exception as e:
                logger.error(f"Error inserting game: {e}")
                skipped += 1

        return inserted, skipped

    def scrape_seasons(self, start_year: int = 1990, end_year: int = 2025,
                       resume: bool = True) -> Dict[str, Any]:
        """
        Scrape multiple seasons of NFL game data.

        Args:
            start_year: First season to scrape (inclusive)
            end_year: Last season to scrape (inclusive)
            resume: Whether to skip already-completed seasons

        Returns:
            Dictionary with scraping statistics
        """
        self.initialize_teams()

        stats = {
            'seasons_attempted': 0,
            'seasons_completed': 0,
            'games_inserted': 0,
            'games_skipped': 0,
            'errors': []
        }

        for season in range(start_year, end_year + 1):
            stats['seasons_attempted'] += 1

            # Check if already completed
            if resume:
                status = self.db.get_scrape_status(season, 'full')
                if status == 'completed':
                    logger.info(f"Season {season} already scraped, skipping")
                    stats['seasons_completed'] += 1
                    continue

            logger.info(f"Scraping season {season}...")
            self.db.update_scrape_status(season, 'full', 'in_progress')

            try:
                games = self.scrape_season_schedule(season)

                if games:
                    inserted, skipped = self.store_games(games)
                    stats['games_inserted'] += inserted
                    stats['games_skipped'] += skipped

                    # Calculate season stats
                    self.db.calculate_team_season_stats(season)

                    self.db.update_scrape_status(season, 'full', 'completed')
                    stats['seasons_completed'] += 1
                    logger.info(
                        f"Season {season} complete: "
                        f"{inserted} inserted, {skipped} skipped"
                    )
                else:
                    error_msg = f"No games found for season {season}"
                    logger.error(error_msg)
                    self.db.update_scrape_status(season, 'full', 'failed', error_msg)
                    stats['errors'].append(error_msg)

            except Exception as e:
                error_msg = f"Error scraping season {season}: {e}"
                logger.error(error_msg)
                self.db.update_scrape_status(season, 'full', 'failed', error_msg)
                stats['errors'].append(error_msg)

        return stats

    def parse_season_from_html(self, html: str, season: int) -> List[ScrapedGame]:
        """
        Parse games from a locally saved PFR schedule HTML page.

        Use this when PFR blocks automated requests (403). Download the page
        manually in your browser and pass the HTML content here.

        Args:
            html: Raw HTML string of the PFR season schedule page
            season: NFL season year (e.g., 2024)

        Returns:
            List of ScrapedGame objects
        """
        soup = BeautifulSoup(html, 'html.parser')

        games = []

        table = soup.find('table', {'id': 'games'})
        if not table:
            logger.error(f"Could not find games table in provided HTML for season {season}")
            return []

        tbody = table.find('tbody')
        if not tbody:
            logger.error(f"Could not find tbody in games table for season {season}")
            return []

        rows = tbody.find_all('tr')

        for row in rows:
            if row.get('class') and 'thead' in row.get('class', []):
                continue

            game = self._parse_game_row(row, season)
            if game:
                games.append(game)

        logger.info(f"Parsed {len(games)} games from HTML for {season} season")
        return games

    def get_scrape_progress(self) -> Dict[str, Any]:
        """Get current scraping progress."""
        incomplete = self.db.get_incomplete_scrapes()
        completed_count = self.db.fetchone(
            "SELECT COUNT(*) as count FROM scrape_progress WHERE status = 'completed'"
        )

        return {
            'completed': completed_count['count'] if completed_count else 0,
            'incomplete': [dict(row) for row in incomplete],
            'total_games': self.db.fetchone(
                "SELECT COUNT(*) as count FROM games"
            )['count']
        }


def main():
    """Run the scraper as a standalone script."""
    import argparse

    parser = argparse.ArgumentParser(description='Scrape NFL data from Pro Football Reference')
    parser.add_argument('--start', type=int, default=1990, help='Start year (default: 1990)')
    parser.add_argument('--end', type=int, default=2025, help='End year (default: 2025)')
    parser.add_argument('--rate-limit', type=float, default=4.0,
                        help='Seconds between requests (default: 4.0)')
    parser.add_argument('--no-resume', action='store_true',
                        help='Do not skip already-scraped seasons')
    parser.add_argument('--progress', action='store_true',
                        help='Show current progress and exit')
    parser.add_argument('--season', type=int, help='Scrape only a specific season')
    parser.add_argument(
        '--from-file',
        metavar='HTML_PATH',
        help='Parse a locally saved PFR schedule HTML file instead of scraping. '
             'Use --start to specify the season year.'
    )

    args = parser.parse_args()

    scraper = PFRScraper(rate_limit=args.rate_limit)

    if args.from_file:
        season = args.season or args.start
        html_path = Path(args.from_file)
        if not html_path.exists():
            logger.error(f"File not found: {html_path}")
            return
        logger.info(f"Parsing local HTML file for season {season}: {html_path}")
        html = html_path.read_text(encoding='utf-8')
        scraper.initialize_teams()
        games = scraper.parse_season_from_html(html, season)
        if games:
            inserted, skipped = scraper.store_games(games)
            scraper.db.calculate_team_season_stats(season)
            logger.info(f"Completed: {inserted} inserted, {skipped} skipped")
        else:
            logger.error(f"No games found in {html_path}")
        return

    if args.progress:
        progress = scraper.get_scrape_progress()
        print(f"Scraping Progress:")
        print(f"  Completed seasons: {progress['completed']}")
        print(f"  Total games in DB: {progress['total_games']}")
        if progress['incomplete']:
            print(f"  Incomplete:")
            for item in progress['incomplete']:
                print(f"    - {item['season']} week {item['week']}: {item['status']}")
        return

    if args.season:
        logger.info(f"Scraping single season: {args.season}")
        scraper.initialize_teams()
        games = scraper.scrape_season_schedule(args.season)
        if games:
            inserted, skipped = scraper.store_games(games)
            scraper.db.calculate_team_season_stats(args.season)
            logger.info(f"Completed: {inserted} inserted, {skipped} skipped")
    else:
        logger.info(f"Scraping seasons {args.start} to {args.end}")
        stats = scraper.scrape_seasons(
            start_year=args.start,
            end_year=args.end,
            resume=not args.no_resume
        )
        print("\nScraping Complete!")
        print(f"  Seasons attempted: {stats['seasons_attempted']}")
        print(f"  Seasons completed: {stats['seasons_completed']}")
        print(f"  Games inserted: {stats['games_inserted']}")
        print(f"  Games skipped: {stats['games_skipped']}")
        if stats['errors']:
            print(f"  Errors: {len(stats['errors'])}")
            for err in stats['errors'][:5]:
                print(f"    - {err}")


if __name__ == '__main__':
    main()
