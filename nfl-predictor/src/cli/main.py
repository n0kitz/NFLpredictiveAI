"""CLI interface for NFL Prediction System."""

import argparse
import logging
import re
import sys
from typing import Optional, List, Tuple

from ..database.db import Database, get_database
from ..prediction.engine import PredictionEngine
from ..prediction.factors import FactorAdjuster, get_factor_type_descriptions
from ..scraper.pfr_scraper import PFRScraper

logger = logging.getLogger(__name__)


class NFLPredictor:
    """
    NFL Prediction CLI Interface.

    Supports natural language queries for predictions and historical data.
    """

    def __init__(self, db: Optional[Database] = None):
        """
        Initialize the NFL Predictor CLI.

        Args:
            db: Database instance (uses singleton if not provided)
        """
        self.db = db or get_database()
        self.engine = PredictionEngine(self.db)
        self.factor_adjuster = FactorAdjuster(self.db)

    def parse_query(self, query: str) -> Tuple[str, dict]:
        """
        Parse a natural language query into command and parameters.

        Args:
            query: Natural language query string

        Returns:
            Tuple of (command_type, parameters_dict)
        """
        query_lower = query.lower().strip()

        # Head-to-head queries (check first - these are more specific)
        # "Head to head Patriots vs Dolphins"
        h2h_patterns = [
            r'head\s*(?:to|2)\s*head\s+(.+?)\s+(?:vs\.?|versus|and|&)\s+(.+)',
            r'h2h\s+(.+?)\s+(?:vs\.?|versus|and|&)\s+(.+)',
        ]

        for pattern in h2h_patterns:
            match = re.search(pattern, query_lower)
            if match:
                team1 = re.sub(r'^the\s+', '', match.group(1).strip())
                team2 = re.sub(r'^the\s+', '', match.group(2).strip())
                return 'head_to_head', {'team1': team1, 'team2': team2}

        # Prediction queries
        # "Predict Chiefs vs Eagles"
        # "Who wins: Cowboys at Giants?"
        # "Predict week 15 matchup 49ers vs Seahawks"
        predict_patterns = [
            r'predict\s+(.+?)\s+(?:vs\.?|versus|at|@)\s+(.+)',
            r'who wins[:\s]+(.+?)\s+(?:vs\.?|versus|at|@)\s+(.+)',
            r'(.+?)\s+(?:vs\.?|versus|at|@)\s+(.+?)(?:\s+prediction)?$',
        ]

        for pattern in predict_patterns:
            match = re.search(pattern, query_lower)
            if match:
                team1, team2 = match.group(1).strip(), match.group(2).strip()
                # Clean up team names
                team1 = re.sub(r'^the\s+', '', team1)
                team2 = re.sub(r'^the\s+', '', team2)

                # Determine home/away based on "at" or "@"
                if ' at ' in query_lower or ' @ ' in query_lower:
                    # Team2 is home (team1 at team2)
                    return 'predict', {'home': team2, 'away': team1}
                else:
                    # Default: first team is away, second is home
                    return 'predict', {'home': team2, 'away': team1}

        # Recent games queries
        # "Last 10 games for the Bills"
        recent_patterns = [
            r'last\s+(\d+)\s+games?\s+(?:for\s+)?(?:the\s+)?(.+)',
            r'recent\s+games?\s+(?:for\s+)?(?:the\s+)?(.+)',
            r'(.+?)\s+last\s+(\d+)\s+games?',
        ]

        for pattern in recent_patterns:
            match = re.search(pattern, query_lower)
            if match:
                groups = match.groups()
                if groups[0].isdigit():
                    count = int(groups[0])
                    team = re.sub(r'^the\s+', '', groups[1].strip())
                elif len(groups) > 1 and groups[1].isdigit():
                    count = int(groups[1])
                    team = re.sub(r'^the\s+', '', groups[0].strip())
                else:
                    count = 10
                    team = re.sub(r'^the\s+', '', groups[0].strip())
                return 'recent_games', {'team': team, 'count': count}

        # Team record queries
        # "Bills record in 2023"
        record_patterns = [
            r'(.+?)\s+record\s+(?:in\s+)?(\d{4})',
            r'(\d{4})\s+(.+?)\s+record',
            r'(.+?)\s+stats?\s+(?:in\s+)?(\d{4})',
        ]

        for pattern in record_patterns:
            match = re.search(pattern, query_lower)
            if match:
                groups = match.groups()
                if groups[0].isdigit():
                    season = int(groups[0])
                    team = re.sub(r'^the\s+', '', groups[1].strip())
                else:
                    team = re.sub(r'^the\s+', '', groups[0].strip())
                    season = int(groups[1])
                return 'team_record', {'team': team, 'season': season}

        # Playoff history queries
        # "Show playoff history for the Lions"
        playoff_patterns = [
            r'playoff\s+history\s+(?:for\s+)?(?:the\s+)?(.+)',
            r'(.+?)\s+playoff\s+history',
            r'playoffs?\s+(.+)',
        ]

        for pattern in playoff_patterns:
            match = re.search(pattern, query_lower)
            if match:
                team = re.sub(r'^the\s+', '', match.group(1).strip())
                return 'playoff_history', {'team': team}

        # Team info/summary
        # "Tell me about the Chiefs"
        # "Chiefs"
        info_patterns = [
            r'(?:tell\s+me\s+)?about\s+(?:the\s+)?(.+)',
            r'info\s+(?:on\s+)?(?:the\s+)?(.+)',
            r'^(?:the\s+)?([a-z\s]+)$',
        ]

        for pattern in info_patterns:
            match = re.search(pattern, query_lower)
            if match:
                team = re.sub(r'^the\s+', '', match.group(1).strip())
                # Make sure it's not a command
                if team not in ['help', 'exit', 'quit', 'scrape', 'teams']:
                    return 'team_info', {'team': team}

        return 'unknown', {'query': query}

    def execute_query(self, query: str) -> str:
        """
        Execute a natural language query and return the result.

        Args:
            query: Query string

        Returns:
            Result string
        """
        command, params = self.parse_query(query)

        try:
            if command == 'predict':
                prediction = self.engine.predict(
                    home_team=params['home'],
                    away_team=params['away']
                )
                return prediction.format_output()

            elif command == 'head_to_head':
                return self.engine.get_head_to_head_summary(
                    params['team1'],
                    params['team2']
                )

            elif command == 'recent_games':
                return self.engine.get_recent_games(
                    params['team'],
                    params.get('count', 10)
                )

            elif command == 'team_record':
                return self.engine.get_team_summary(
                    params['team'],
                    params.get('season')
                )

            elif command == 'playoff_history':
                return self.engine.get_playoff_history(params['team'])

            elif command == 'team_info':
                return self.engine.get_team_summary(params['team'])

            else:
                return (
                    f"Could not understand query: {query}\n\n"
                    "Try one of these formats:\n"
                    "  Predictions:\n"
                    "    - Predict Chiefs vs Eagles\n"
                    "    - Who wins: Cowboys at Giants?\n"
                    "    - 49ers vs Seahawks\n\n"
                    "  Historical:\n"
                    "    - Head to head Patriots vs Dolphins\n"
                    "    - Last 10 games for the Bills\n"
                    "    - Bills record in 2023\n"
                    "    - Show playoff history for the Lions\n"
                    "    - Tell me about the Chiefs"
                )

        except ValueError as e:
            return f"Error: {e}"
        except Exception as e:
            logger.exception(f"Error executing query: {query}")
            return f"Error: {e}"

    def interactive_mode(self) -> None:
        """Run the CLI in interactive mode."""
        print("\nNFL Game Prediction System")
        print("=" * 40)
        print("Type 'help' for commands, 'exit' to quit\n")

        while True:
            try:
                query = input("NFL> ").strip()

                if not query:
                    continue

                if query.lower() in ('exit', 'quit', 'q'):
                    print("Goodbye!")
                    break

                if query.lower() == 'help':
                    self.print_help()
                    continue

                if query.lower() == 'teams':
                    self.list_teams()
                    continue

                if query.lower() == 'factors':
                    self.show_factor_types()
                    continue

                result = self.execute_query(query)
                print(result)

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except EOFError:
                break

    def print_help(self) -> None:
        """Print help information."""
        print("""
NFL Prediction System - Commands

PREDICTIONS:
  Predict Chiefs vs Eagles
  Who wins: Cowboys at Giants?
  49ers vs Seahawks
  Predict week 15 matchup Rams vs Cardinals

HISTORICAL DATA:
  Head to head Patriots vs Dolphins
  h2h Bills and Jets
  Last 10 games for the Bills
  Bills recent games
  Bills record in 2023
  Chiefs stats 2023
  Show playoff history for the Lions

TEAM INFO:
  Tell me about the Chiefs
  Info on the Eagles
  Cowboys

OTHER COMMANDS:
  teams     - List all teams
  factors   - Show available game factor types
  help      - Show this help
  exit/quit - Exit the program

NOTES:
  - Team names can be full name, city, or abbreviation
  - "vs" assumes first team is away, second is home
  - "at" or "@" means first team plays at second team's venue
""")

    def list_teams(self) -> None:
        """List all NFL teams."""
        teams = self.db.get_all_teams()
        print("\nNFL Teams:")
        print("-" * 50)

        current_conf = None
        current_div = None

        for team in teams:
            if team['conference'] != current_conf:
                current_conf = team['conference']
                print(f"\n{current_conf}")

            if team['division'] != current_div:
                current_div = team['division']
                print(f"  {current_div}:")

            print(f"    {team['abbreviation']:4} - {team['city']} {team['name']}")

    def show_factor_types(self) -> None:
        """Show available game factor types."""
        print("\nAvailable Game Factor Types:")
        print("-" * 50)

        descriptions = get_factor_type_descriptions()
        for factor_type, description in descriptions.items():
            print(f"  {factor_type:20} - {description}")

        print("\nImpact rating scale: -5 (very negative) to +5 (very positive)")


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description='NFL Game Prediction System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "Predict Chiefs vs Eagles"
  %(prog)s "Who wins: Cowboys at Giants?"
  %(prog)s "Head to head Patriots vs Dolphins"
  %(prog)s "Last 10 games for the Bills"
  %(prog)s "Bills record in 2023"
  %(prog)s --interactive
  %(prog)s --scrape --start 2020 --end 2024
        """
    )

    parser.add_argument(
        'query',
        nargs='?',
        help='Query to execute (omit for interactive mode)'
    )

    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        help='Run in interactive mode'
    )

    parser.add_argument(
        '--scrape',
        action='store_true',
        help='Run the data scraper'
    )

    parser.add_argument(
        '--start',
        type=int,
        default=1990,
        help='Start year for scraping (default: 1990)'
    )

    parser.add_argument(
        '--end',
        type=int,
        default=2025,
        help='End year for scraping (default: 2025)'
    )

    parser.add_argument(
        '--from-file',
        metavar='HTML_PATH',
        help='Parse a locally saved PFR schedule HTML file instead of scraping. '
             'Use --start to specify the season year.'
    )

    parser.add_argument(
        '--init-db',
        action='store_true',
        help='Initialize the database schema'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    # Factor management commands
    parser.add_argument(
        '--add-factor',
        nargs=4,
        metavar=('GAME_ID', 'TEAM_ID', 'FACTOR_TYPE', 'IMPACT'),
        help='Add a game factor: game_id team_id factor_type impact_rating'
    )

    parser.add_argument(
        '--factor-desc',
        help='Description for the factor (use with --add-factor)'
    )

    parser.add_argument(
        '--list-factors',
        type=int,
        metavar='GAME_ID',
        help='List factors for a game'
    )

    parser.add_argument(
        '--remove-factor',
        type=int,
        metavar='FACTOR_ID',
        help='Remove a factor by ID'
    )

    parser.add_argument(
        '--import-factors',
        metavar='CSV_PATH',
        help='Import factors from CSV file'
    )

    parser.add_argument(
        '--train-model',
        action='store_true',
        help='Train the ML prediction model on 2013-2022 data (takes 5-10 minutes)'
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    db = get_database()

    # Initialize database if requested
    if args.init_db:
        print("Initializing database...")
        db.init_schema()
        print("Database initialized.")
        return

    # Parse from local HTML file
    if args.from_file:
        from pathlib import Path
        html_path = Path(args.from_file)
        if not html_path.exists():
            print(f"Error: File not found: {html_path}")
            return
        season = args.start
        print(f"Parsing local HTML file for season {season}: {html_path}")
        html = html_path.read_text(encoding='utf-8')
        scraper = PFRScraper(db)
        scraper.initialize_teams()
        games = scraper.parse_season_from_html(html, season)
        if games:
            inserted, skipped = scraper.store_games(games)
            scraper.db.calculate_team_season_stats(season)
            print(f"Completed: {inserted} inserted, {skipped} skipped")
        else:
            print(f"No games found in {html_path}")
        return

    # Train ML model if requested
    if args.train_model:
        from ..prediction.ml_model import train_model
        print("=" * 60)
        print("  NFL ML Model Training")
        print("  Training window: seasons 2013-2022")
        print("  This may take 5-10 minutes depending on hardware.")
        print("=" * 60)
        result = train_model(db)
        print("\n  ── Training Complete ──")
        print(f"  Seasons:          {result['training_seasons']}")
        print(f"  Samples:          {result['n_training_samples']:,}")
        print(f"  CV accuracy:      {result['cv_accuracy']:.4f} ± {result['cv_std']:.4f}")
        print(f"  Fold accuracies:  {result['fold_accuracies']}")
        print("\n  Restart the API server to load the new model.")
        return

    # Run scraper if requested
    if args.scrape:
        print(f"Scraping NFL data from {args.start} to {args.end}...")
        scraper = PFRScraper(db)
        stats = scraper.scrape_seasons(args.start, args.end)
        print(f"\nScraping complete!")
        print(f"  Seasons: {stats['seasons_completed']}/{stats['seasons_attempted']}")
        print(f"  Games inserted: {stats['games_inserted']}")
        if stats['errors']:
            print(f"  Errors: {len(stats['errors'])}")
        return

    # Factor management commands
    predictor = NFLPredictor(db)

    if args.add_factor:
        game_id, team_id, factor_type, impact = args.add_factor
        try:
            factor_id = predictor.factor_adjuster.add_factor(
                game_id=int(game_id),
                team_id=int(team_id),
                factor_type=factor_type,
                description=args.factor_desc,
                impact_rating=int(impact)
            )
            print(f"Factor added with ID: {factor_id}")
        except Exception as e:
            print(f"Error adding factor: {e}")
        return

    if args.list_factors:
        factors = predictor.factor_adjuster.list_factors(args.list_factors)
        if factors:
            print(f"\nFactors for game {args.list_factors}:")
            for f in factors:
                print(f"  [{f['factor_id']}] {f['team']}: {f['type']} "
                      f"(impact: {f['impact']}) - {f['description']}")
        else:
            print(f"No factors found for game {args.list_factors}")
        return

    if args.remove_factor:
        if predictor.factor_adjuster.remove_factor(args.remove_factor):
            print(f"Factor {args.remove_factor} removed")
        else:
            print(f"Factor {args.remove_factor} not found")
        return

    if args.import_factors:
        try:
            imported, errors = predictor.factor_adjuster.bulk_import_factors(
                args.import_factors
            )
            print(f"Imported {imported} factors, {errors} errors")
        except Exception as e:
            print(f"Error importing factors: {e}")
        return

    # Interactive mode or single query
    if args.interactive or not args.query:
        predictor.interactive_mode()
    else:
        result = predictor.execute_query(args.query)
        print(result)


if __name__ == '__main__':
    main()
