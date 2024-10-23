import logging
import datetime
import os
import json
import requests

# Logging configuration with color scheme for debug information
logging.basicConfig(level=logging.DEBUG)
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"

# Solar functions
# Function to retrieve solar production forecast from Solcast API (cached every 6 hours)
def get_solar_forecast(SOLCAST_API_URL):
    cache_file = "solar_forecast_cache.json"
    current_time = datetime.datetime.now().astimezone()  # Verwende lokale Zeit mit Zeitzoneninfo

    # Check if cache exists and is still valid (within 6 hours)
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            cached_data = json.load(f)
            cache_time = datetime.datetime.fromisoformat(cached_data["timestamp"])
            if cache_time.tzinfo is None:
                cache_time = cache_time.astimezone()
            if (current_time - cache_time).total_seconds() < 6 * 3600:
                logging.debug(f"{CYAN}Using cached solar forecast data from {cache_time}{RESET}")
                solar_forecast = cached_data["solar_forecast"]
                # Convert time strings back to aware datetime objects
                for entry in solar_forecast:
                    if isinstance(entry['time'], str):
                        entry['time'] = datetime.datetime.fromisoformat(entry['time'])
                    if entry['time'].tzinfo is None:
                        entry['time'] = entry['time'].astimezone()
                return solar_forecast

    logging.debug(f"{CYAN}Abrufen der Solarprognose von Solcast{RESET}")
    try:
        # API-Anfrage
        response = requests.get(SOLCAST_API_URL)
        response.raise_for_status()

        data = response.json()
        solar_forecast = []

        # Verarbeite jeden Forecast
        for forecast in data['forecasts']:
            pv_estimate = forecast['pv_estimate'] * 1000  # Convert kW to W
            period_end = datetime.datetime.fromisoformat(forecast['period_end'].replace('Z', '+00:00'))
            period_end = period_end.astimezone()  # Konvertiere period_end in lokale Zeit

            solar_forecast.append({
                'time': period_end.isoformat(),
                'pv_estimate': pv_estimate
            })

        # Speichere die neuen Daten im Cache
        with open(cache_file, "w") as f:
            json.dump({"timestamp": current_time.isoformat(), "solar_forecast": solar_forecast}, f)

        logging.debug(f"{CYAN}Solar forecast data cached successfully.{RESET}")
        return solar_forecast

    except Exception as e:
        logging.error(f"Fehler beim Abrufen der Solarprognose: {e}")
        return []
