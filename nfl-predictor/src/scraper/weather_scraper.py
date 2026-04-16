"""Fetch game-day weather forecasts from Open-Meteo (free, no auth)."""

import logging
from typing import Optional

import requests

from .injury_scraper import STADIUM_COORDS

logger = logging.getLogger(__name__)

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation code → human-readable condition
_WMO_CONDITIONS: dict[tuple, str] = {
    (0, 0):   "Clear",
    (1, 3):   "Partly Cloudy",
    (45, 48): "Fog",
    (51, 67): "Rain",
    (71, 77): "Snow",
    (80, 82): "Showers",
    (85, 86): "Snow Showers",
    (95, 99): "Thunderstorm",
}

# WMO codes that indicate snow (used for adverse-weather check)
_SNOW_CODES: frozenset[int] = frozenset(range(71, 78)) | {85, 86}


def _wmo_condition(code: int) -> str:
    """Map a WMO weather code to a readable condition string."""
    for (lo, hi), label in _WMO_CONDITIONS.items():
        if lo <= code <= hi:
            return label
    return "Unknown"


class WeatherScraper:
    """Fetch forecast weather for an NFL game location from Open-Meteo."""

    def fetch_game_weather(
        self, home_team_abbr: str, game_date: str
    ) -> Optional[dict]:
        """
        Return weather conditions for a game at the home team's stadium.

        Args:
            home_team_abbr: Internal team abbreviation (e.g. "KC").
            game_date: ISO date string "YYYY-MM-DD".

        Returns:
            Dict with keys: is_dome, temperature_c, wind_speed_kmh,
            precipitation_mm, weather_code, condition, is_adverse.
            Returns {"is_dome": True, "condition": "Dome"} immediately for
            covered venues (no HTTP call made).
            Returns None on any error.
        """
        coords = STADIUM_COORDS.get(home_team_abbr)
        if coords is None:
            logger.warning("No stadium coords for team %s", home_team_abbr)
            return None

        lat, lon, is_dome = coords

        if is_dome:
            return {
                "is_dome":           True,
                "condition":         "Dome",
                "temperature_c":     None,
                "wind_speed_kmh":    None,
                "precipitation_mm":  None,
                "weather_code":      None,
                "is_adverse":        False,
            }

        try:
            resp = requests.get(
                _OPEN_METEO_URL,
                params={
                    "latitude":    lat,
                    "longitude":   lon,
                    "daily":       ",".join([
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "precipitation_sum",
                        "windspeed_10m_max",
                        "weathercode",
                    ]),
                    "start_date":  game_date,
                    "end_date":    game_date,
                    "timezone":    "auto",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.warning("Weather fetch failed for %s on %s: %s", home_team_abbr, game_date, exc)
            return None
        except Exception as exc:
            logger.warning("Unexpected weather error: %s", exc)
            return None

        daily = data.get("daily", {})
        try:
            t_max  = (daily.get("temperature_2m_max") or [None])[0]
            t_min  = (daily.get("temperature_2m_min") or [None])[0]
            wind   = (daily.get("windspeed_10m_max")  or [None])[0]
            precip = (daily.get("precipitation_sum")   or [None])[0]
            wcode  = (daily.get("weathercode")         or [None])[0]
        except (IndexError, TypeError):
            return None

        temp_c = None
        if t_max is not None and t_min is not None:
            temp_c = round((t_max + t_min) / 2.0, 1)

        wind_kmh  = float(wind)   if wind   is not None else None
        prec_mm   = float(precip) if precip is not None else None
        wcode_int = int(wcode)    if wcode  is not None else None

        condition  = _wmo_condition(wcode_int) if wcode_int is not None else "Unknown"
        is_adverse = (
            (wind_kmh  is not None and wind_kmh  > 30)
            or (prec_mm  is not None and prec_mm   > 5)
            or (wcode_int is not None and wcode_int in _SNOW_CODES)
        )

        return {
            "is_dome":          False,
            "temperature_c":    temp_c,
            "wind_speed_kmh":   wind_kmh,
            "precipitation_mm": prec_mm,
            "weather_code":     wcode_int,
            "condition":        condition,
            "is_adverse":       is_adverse,
        }
