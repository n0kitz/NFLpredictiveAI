"""NFL Team mappings including historical name changes and relocations."""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TeamInfo:
    """Team information."""
    name: str
    city: str
    abbreviation: str
    conference: str
    division: str
    franchise_id: str
    active_from: Optional[int] = None
    active_until: Optional[int] = None
    pfr_abbr: Optional[str] = None  # Pro Football Reference abbreviation


# Current NFL teams (as of 2024)
CURRENT_TEAMS: List[TeamInfo] = [
    # AFC East
    TeamInfo("Bills", "Buffalo", "BUF", "AFC", "East", "BUF", 1960, None, "buf"),
    TeamInfo("Dolphins", "Miami", "MIA", "AFC", "East", "MIA", 1966, None, "mia"),
    TeamInfo("Patriots", "New England", "NE", "AFC", "East", "NE", 1971, None, "nwe"),
    TeamInfo("Jets", "New York", "NYJ", "AFC", "East", "NYJ", 1963, None, "nyj"),

    # AFC North
    TeamInfo("Ravens", "Baltimore", "BAL", "AFC", "North", "BAL", 1996, None, "rav"),
    TeamInfo("Bengals", "Cincinnati", "CIN", "AFC", "North", "CIN", 1968, None, "cin"),
    TeamInfo("Browns", "Cleveland", "CLE", "AFC", "North", "CLE", 1999, None, "cle"),
    TeamInfo("Steelers", "Pittsburgh", "PIT", "AFC", "North", "PIT", 1933, None, "pit"),

    # AFC South
    TeamInfo("Texans", "Houston", "HOU", "AFC", "South", "HOU", 2002, None, "htx"),
    TeamInfo("Colts", "Indianapolis", "IND", "AFC", "South", "IND", 1984, None, "clt"),
    TeamInfo("Jaguars", "Jacksonville", "JAX", "AFC", "South", "JAX", 1995, None, "jax"),
    TeamInfo("Titans", "Tennessee", "TEN", "AFC", "South", "TEN", 1999, None, "oti"),

    # AFC West
    TeamInfo("Broncos", "Denver", "DEN", "AFC", "West", "DEN", 1960, None, "den"),
    TeamInfo("Chiefs", "Kansas City", "KC", "AFC", "West", "KC", 1963, None, "kan"),
    TeamInfo("Raiders", "Las Vegas", "LV", "AFC", "West", "OAK_LA_LV", 2020, None, "rai"),
    TeamInfo("Chargers", "Los Angeles", "LAC", "AFC", "West", "SD_LA", 2017, None, "sdg"),

    # NFC East
    TeamInfo("Cowboys", "Dallas", "DAL", "NFC", "East", "DAL", 1960, None, "dal"),
    TeamInfo("Giants", "New York", "NYG", "NFC", "East", "NYG", 1925, None, "nyg"),
    TeamInfo("Eagles", "Philadelphia", "PHI", "NFC", "East", "PHI", 1933, None, "phi"),
    TeamInfo("Commanders", "Washington", "WAS", "NFC", "East", "WAS", 2022, None, "was"),

    # NFC North
    TeamInfo("Bears", "Chicago", "CHI", "NFC", "North", "CHI", 1922, None, "chi"),
    TeamInfo("Lions", "Detroit", "DET", "NFC", "North", "DET", 1934, None, "det"),
    TeamInfo("Packers", "Green Bay", "GB", "NFC", "North", "GB", 1921, None, "gnb"),
    TeamInfo("Vikings", "Minnesota", "MIN", "NFC", "North", "MIN", 1961, None, "min"),

    # NFC South
    TeamInfo("Falcons", "Atlanta", "ATL", "NFC", "South", "ATL", 1966, None, "atl"),
    TeamInfo("Panthers", "Carolina", "CAR", "NFC", "South", "CAR", 1995, None, "car"),
    TeamInfo("Saints", "New Orleans", "NO", "NFC", "South", "NO", 1967, None, "nor"),
    TeamInfo("Buccaneers", "Tampa Bay", "TB", "NFC", "South", "TB", 1976, None, "tam"),

    # NFC West
    TeamInfo("Cardinals", "Arizona", "ARI", "NFC", "West", "ARI", 1994, None, "crd"),
    TeamInfo("Rams", "Los Angeles", "LAR", "NFC", "West", "STL_LA", 2016, None, "ram"),
    TeamInfo("49ers", "San Francisco", "SF", "NFC", "West", "SF", 1946, None, "sfo"),
    TeamInfo("Seahawks", "Seattle", "SEA", "NFC", "West", "SEA", 1976, None, "sea"),
]

# Historical team names/locations (for teams that have moved or changed names)
HISTORICAL_TEAMS: List[TeamInfo] = [
    # Raiders history
    TeamInfo("Raiders", "Oakland", "OAK", "AFC", "West", "OAK_LA_LV", 1995, 2019, "rai"),
    TeamInfo("Raiders", "Los Angeles", "RAI", "AFC", "West", "OAK_LA_LV", 1982, 1994, "rai"),
    TeamInfo("Raiders", "Oakland", "OAK", "AFC", "West", "OAK_LA_LV", 1960, 1981, "rai"),

    # Chargers history
    TeamInfo("Chargers", "San Diego", "SD", "AFC", "West", "SD_LA", 1961, 2016, "sdg"),

    # Rams history
    TeamInfo("Rams", "St. Louis", "STL", "NFC", "West", "STL_LA", 1995, 2015, "ram"),
    TeamInfo("Rams", "Los Angeles", "RAM", "NFC", "West", "STL_LA", 1946, 1994, "ram"),

    # Colts history
    TeamInfo("Colts", "Baltimore", "BAL_OLD", "AFC", "East", "IND", 1953, 1983, "clt"),

    # Cardinals history
    TeamInfo("Cardinals", "Phoenix", "PHX", "NFC", "East", "ARI", 1988, 1993, "crd"),
    TeamInfo("Cardinals", "St. Louis", "SLC", "NFC", "East", "ARI", 1960, 1987, "crd"),

    # Titans/Oilers history
    TeamInfo("Oilers", "Tennessee", "TEN_OIL", "AFC", "Central", "TEN", 1997, 1998, "oti"),
    TeamInfo("Oilers", "Houston", "HOU_OIL", "AFC", "Central", "TEN", 1960, 1996, "oti"),

    # Washington name changes
    TeamInfo("Football Team", "Washington", "WFT", "NFC", "East", "WAS", 2020, 2021, "was"),
    TeamInfo("Redskins", "Washington", "WSH", "NFC", "East", "WAS", 1937, 2019, "was"),

    # Patriots history
    TeamInfo("Patriots", "Boston", "BOS", "AFC", "East", "NE", 1960, 1970, "nwe"),

    # Original Browns (now Ravens)
    TeamInfo("Browns", "Cleveland", "CLE_OLD", "AFC", "Central", "BAL", 1946, 1995, "cle"),
]


class TeamMappings:
    """
    Handles team name mappings and lookups across different naming conventions.
    """

    def __init__(self):
        """Initialize team mappings."""
        self._build_mappings()

    def _build_mappings(self) -> None:
        """Build internal lookup dictionaries."""
        # Map PFR abbreviations to current team info
        self.pfr_to_team: Dict[str, TeamInfo] = {}

        # Map various names/abbreviations to team info
        self.name_to_team: Dict[str, TeamInfo] = {}

        # All teams by franchise ID
        self.franchise_teams: Dict[str, List[TeamInfo]] = {}

        # Process current teams
        for team in CURRENT_TEAMS:
            if team.pfr_abbr:
                self.pfr_to_team[team.pfr_abbr.lower()] = team

            # Add various lookup keys
            self.name_to_team[team.abbreviation.lower()] = team
            self.name_to_team[team.name.lower()] = team
            self.name_to_team[team.city.lower()] = team
            self.name_to_team[f"{team.city} {team.name}".lower()] = team

            # Group by franchise
            if team.franchise_id not in self.franchise_teams:
                self.franchise_teams[team.franchise_id] = []
            self.franchise_teams[team.franchise_id].append(team)

        # Process historical teams
        for team in HISTORICAL_TEAMS:
            if team.pfr_abbr:
                # Don't overwrite current team PFR mapping
                if team.pfr_abbr.lower() not in self.pfr_to_team:
                    self.pfr_to_team[team.pfr_abbr.lower()] = team

            # Add historical name lookups
            self.name_to_team[team.abbreviation.lower()] = team
            if team.name.lower() not in self.name_to_team:
                self.name_to_team[team.name.lower()] = team
            if team.city.lower() not in self.name_to_team:
                self.name_to_team[team.city.lower()] = team
            full_name = f"{team.city} {team.name}".lower()
            if full_name not in self.name_to_team:
                self.name_to_team[full_name] = team

            # Group by franchise
            if team.franchise_id not in self.franchise_teams:
                self.franchise_teams[team.franchise_id] = []
            self.franchise_teams[team.franchise_id].append(team)

        # Special mappings for common variations
        self._add_special_mappings()

    def _add_special_mappings(self) -> None:
        """Add special case mappings for common variations."""
        special_maps = {
            # Common abbreviation variations
            "kc": self.name_to_team.get("kc"),
            "jac": self.name_to_team.get("jax"),
            "jags": self.name_to_team.get("jax"),
            "gb": self.name_to_team.get("gb"),
            "ne": self.name_to_team.get("ne"),
            "pats": self.name_to_team.get("ne"),
            "no": self.name_to_team.get("no"),
            "sf": self.name_to_team.get("sf"),
            "niners": self.name_to_team.get("sf"),
            "tb": self.name_to_team.get("tb"),
            "bucs": self.name_to_team.get("tb"),
            "lv": self.name_to_team.get("lv"),
            "lar": self.name_to_team.get("lar") or self.name_to_team.get("los angeles rams"),
            "lac": self.name_to_team.get("lac") or self.name_to_team.get("los angeles chargers"),

            # City variations
            "new york jets": self.name_to_team.get("nyj"),
            "new york giants": self.name_to_team.get("nyg"),
            "la rams": self.name_to_team.get("lar") or self.name_to_team.get("los angeles rams"),
            "la chargers": self.name_to_team.get("lac") or self.name_to_team.get("los angeles chargers"),
            "indy": self.name_to_team.get("ind"),
            "wash": self.name_to_team.get("was"),
            "arizona": self.name_to_team.get("ari"),
            "vegas": self.name_to_team.get("lv"),
        }

        for key, team in special_maps.items():
            if team and key not in self.name_to_team:
                self.name_to_team[key] = team

    def get_team_by_pfr_abbr(self, pfr_abbr: str, year: Optional[int] = None) -> Optional[TeamInfo]:
        """
        Get team info by Pro Football Reference abbreviation.

        Args:
            pfr_abbr: PFR team abbreviation
            year: Optional year to get historical team name

        Returns:
            TeamInfo if found, None otherwise
        """
        team = self.pfr_to_team.get(pfr_abbr.lower())
        if team and year:
            # Get the correct historical name for this year
            return self.get_team_for_year(team.franchise_id, year)
        return team

    def get_team_for_year(self, franchise_id: str, year: int) -> Optional[TeamInfo]:
        """
        Get the team name/info that was active for a specific year.

        Args:
            franchise_id: Franchise identifier
            year: The year to look up

        Returns:
            TeamInfo for the team as it was named in that year
        """
        teams = self.franchise_teams.get(franchise_id, [])
        for team in teams:
            from_year = team.active_from or 0
            until_year = team.active_until or 9999
            if from_year <= year <= until_year:
                return team
        # Return current team if no historical match
        return teams[0] if teams else None

    def find_team(self, search_term: str) -> Optional[TeamInfo]:
        """
        Find a team by various search terms (name, city, abbreviation).

        Args:
            search_term: Search string

        Returns:
            TeamInfo if found, None otherwise
        """
        return self.name_to_team.get(search_term.lower().strip())

    def get_current_team_for_franchise(self, franchise_id: str) -> Optional[TeamInfo]:
        """Get the current (active) team for a franchise."""
        teams = self.franchise_teams.get(franchise_id, [])
        for team in teams:
            if team.active_until is None:
                return team
        return teams[0] if teams else None

    def get_all_current_teams(self) -> List[TeamInfo]:
        """Get all current NFL teams."""
        return CURRENT_TEAMS.copy()

    def normalize_team_name(self, name: str, year: Optional[int] = None) -> Optional[str]:
        """
        Normalize a team name to current abbreviation.

        Args:
            name: Team name, city, or abbreviation
            year: Optional year for context

        Returns:
            Current team abbreviation if found
        """
        team = self.find_team(name)
        if team:
            current = self.get_current_team_for_franchise(team.franchise_id)
            return current.abbreviation if current else team.abbreviation
        return None


# PFR uses specific abbreviations that may differ from common ones
PFR_TEAM_ABBR_MAP = {
    'crd': 'ARI',  # Cardinals
    'atl': 'ATL',
    'rav': 'BAL',  # Ravens
    'buf': 'BUF',
    'car': 'CAR',
    'chi': 'CHI',
    'cin': 'CIN',
    'cle': 'CLE',
    'dal': 'DAL',
    'den': 'DEN',
    'det': 'DET',
    'gnb': 'GB',   # Packers
    'htx': 'HOU',  # Texans
    'clt': 'IND',  # Colts
    'jax': 'JAX',
    'kan': 'KC',   # Chiefs
    'rai': 'LV',   # Raiders (current)
    'sdg': 'LAC',  # Chargers (current)
    'ram': 'LAR',  # Rams (current)
    'mia': 'MIA',
    'min': 'MIN',
    'nwe': 'NE',   # Patriots
    'nor': 'NO',   # Saints
    'nyg': 'NYG',
    'nyj': 'NYJ',
    'phi': 'PHI',
    'pit': 'PIT',
    'sfo': 'SF',   # 49ers
    'sea': 'SEA',
    'tam': 'TB',   # Buccaneers
    'oti': 'TEN',  # Titans
    'was': 'WAS',
}

# Historical PFR abbreviation mappings based on year
PFR_HISTORICAL_ABBR = {
    # Raiders
    ('rai', 1995, 2019): 'OAK',
    ('rai', 1982, 1994): 'RAI',  # LA Raiders
    ('rai', 1960, 1981): 'OAK',

    # Chargers
    ('sdg', 1961, 2016): 'SD',

    # Rams
    ('ram', 1995, 2015): 'STL',
    ('ram', 1946, 1994): 'RAM',  # LA Rams

    # Cardinals
    ('crd', 1988, 1993): 'PHX',
    ('crd', 1960, 1987): 'SLC',

    # Titans/Oilers
    ('oti', 1997, 1998): 'TEN_OIL',
    ('oti', 1960, 1996): 'HOU_OIL',

    # Washington
    ('was', 2020, 2021): 'WFT',
    ('was', 1937, 2019): 'WSH',

    # Colts
    ('clt', 1953, 1983): 'BAL_OLD',
}


def get_team_abbr_for_year(pfr_abbr: str, year: int) -> str:
    """
    Get the appropriate team abbreviation for a given year.

    Args:
        pfr_abbr: Pro Football Reference abbreviation
        year: Season year

    Returns:
        Team abbreviation appropriate for that year
    """
    pfr_abbr = pfr_abbr.lower()

    # Check historical mappings
    for (abbr, start, end), result in PFR_HISTORICAL_ABBR.items():
        if abbr == pfr_abbr and start <= year <= end:
            return result

    # Return current mapping
    return PFR_TEAM_ABBR_MAP.get(pfr_abbr, pfr_abbr.upper())
