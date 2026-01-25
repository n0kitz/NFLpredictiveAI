"""Scraper module for NFL Prediction System."""

from .team_mappings import TeamMappings, CURRENT_TEAMS, HISTORICAL_TEAMS
from .pfr_scraper import PFRScraper

__all__ = ['TeamMappings', 'CURRENT_TEAMS', 'HISTORICAL_TEAMS', 'PFRScraper']
