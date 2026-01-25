"""Helper utility functions for NFL Prediction System."""

import re
from datetime import datetime
from typing import Optional, Tuple


def format_record(wins: int, losses: int, ties: int = 0) -> str:
    """
    Format a win-loss-tie record as a string.

    Args:
        wins: Number of wins
        losses: Number of losses
        ties: Number of ties (optional)

    Returns:
        Formatted record string (e.g., "10-4" or "10-4-1")
    """
    if ties > 0:
        return f"{wins}-{losses}-{ties}"
    return f"{wins}-{losses}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """
    Format a decimal as a percentage string.

    Args:
        value: Decimal value (0.0 to 1.0)
        decimals: Number of decimal places

    Returns:
        Formatted percentage string (e.g., "75.0%")
    """
    return f"{value * 100:.{decimals}f}%"


def parse_team_input(input_str: str) -> str:
    """
    Parse and clean team input string.

    Removes common prefixes like "the" and normalizes whitespace.

    Args:
        input_str: Raw team input string

    Returns:
        Cleaned team string
    """
    # Normalize whitespace
    cleaned = ' '.join(input_str.split())

    # Remove common prefixes
    cleaned = re.sub(r'^the\s+', '', cleaned, flags=re.IGNORECASE)

    return cleaned.strip()


def get_current_season() -> int:
    """
    Get the current NFL season year.

    NFL seasons span two calendar years. The season is named after
    the year it starts (e.g., 2023-2024 season is the "2023 season").

    Games from September-December are in the named year.
    Games from January-February are in the previous year's season.

    Returns:
        Current NFL season year
    """
    now = datetime.now()

    # If we're in January or February, we're in the previous year's season
    if now.month <= 2:
        return now.year - 1

    # If we're in March-August, the most recent completed season
    if now.month < 9:
        return now.year - 1

    # September onwards is the new season
    return now.year


def get_week_name(week: str) -> str:
    """
    Get a display-friendly week name.

    Args:
        week: Week identifier (number or playoff round name)

    Returns:
        Display-friendly week name
    """
    try:
        week_num = int(week)
        return f"Week {week_num}"
    except ValueError:
        # Already a named round
        return week


def calculate_win_percentage(wins: int, losses: int, ties: int = 0) -> float:
    """
    Calculate win percentage.

    Ties count as half a win.

    Args:
        wins: Number of wins
        losses: Number of losses
        ties: Number of ties

    Returns:
        Win percentage (0.0 to 1.0)
    """
    total = wins + losses + ties
    if total == 0:
        return 0.0
    return (wins + 0.5 * ties) / total


def parse_game_matchup(matchup_str: str) -> Optional[Tuple[str, str, bool]]:
    """
    Parse a game matchup string into team names and location indicator.

    Supports formats like:
    - "Team1 vs Team2" (Team2 is home)
    - "Team1 at Team2" (Team2 is home)
    - "Team1 @ Team2" (Team2 is home)

    Args:
        matchup_str: Matchup string

    Returns:
        Tuple of (away_team, home_team, is_at_format) or None if can't parse
    """
    matchup_str = matchup_str.strip()

    # Try "at" or "@" format first (more explicit about home/away)
    at_match = re.search(
        r'(.+?)\s+(?:at|@)\s+(.+)',
        matchup_str,
        re.IGNORECASE
    )
    if at_match:
        away = parse_team_input(at_match.group(1))
        home = parse_team_input(at_match.group(2))
        return (away, home, True)

    # Try "vs" format
    vs_match = re.search(
        r'(.+?)\s+(?:vs\.?|versus)\s+(.+)',
        matchup_str,
        re.IGNORECASE
    )
    if vs_match:
        # Convention: first team is away, second is home
        away = parse_team_input(vs_match.group(1))
        home = parse_team_input(vs_match.group(2))
        return (away, home, False)

    return None


def format_point_differential(diff: int) -> str:
    """
    Format point differential with +/- sign.

    Args:
        diff: Point differential value

    Returns:
        Formatted string with sign (e.g., "+45" or "-12")
    """
    return f"{diff:+d}"


def ordinal(n: int) -> str:
    """
    Convert number to ordinal string (1st, 2nd, 3rd, etc.).

    Args:
        n: Number to convert

    Returns:
        Ordinal string
    """
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
    return f"{n}{suffix}"
