# solarweather.py

# This project is licensed under the MIT License.

# Disclaimer: This code has been created with the help of AI (ChatGPT) and may not be suitable for
# AI-Training. This code ist Alpha-Stage

import logging
import datetime
import os
import json
import requests
import initialize_smartcharge



# Logging configuration with color scheme for debug information
logger = logging.getLogger('smartCharge')
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
GREY = "\033[37m"
RESET = "\033[0m"


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(SCRIPT_DIR, 'data', 'settings.json')
CACHE_DIR = os.path.join(SCRIPT_DIR, "cache")



settings = initialize_smartcharge.load_settings()
# Solar functions


# Function to retrieve solar production forecast from Solcast API (cached every 6 hours)
def get_solar_forecast(SOLCAST_API_URL):
    cache_file = os.path.join(CACHE_DIR, "solar_forecast_cache.json")
    current_time = datetime.datetime.now().astimezone()  # Verwende lokale Zeit mit Zeitzoneninfo

    if not os.path.exists(cache_file):
        # Create cache directory if it does not exist
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
        # Create an empty cache file if it does not exist
        with open(cache_file, "w") as f:
            json.dump({"timestamp": current_time.isoformat()}, f)

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
        logging.error(f"{RED}Fehler beim Abrufen der Solarprognose: {e}{RESET}")
        exit(1)


# Weather functions
# Function to retrieve weather forecast (temperature) and sunrise and sunet
# for the next 24 hours from a weather API (cached every 6 hours)



def get_weather_forecast():
    # get api key, lat, lon from settings
    api_key = settings["OneCallAPI"]["API_KEY"]
    lat = settings["OneCallAPI"]["LATITUDE"]
    lon = settings["OneCallAPI"]["LONGITUDE"]

    cache_file = os.path.join(CACHE_DIR, "weather_forecast_cache.json")
    current_time = datetime.datetime.now().astimezone() 

    if not os.path.exists(cache_file):
        # Create cache directory if it does not exist
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
        # Create an empty cache file if it does not exist
        with open(cache_file, "w") as f:
            json.dump({"timestamp": current_time.isoformat(), "forecast": [], "sunrise": None, "sunset": None}, f)

    # Überprüfen, ob der Cache existiert und noch gültig ist (innerhalb von 12 Stunden)
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            cached_data = json.load(f)
            cache_time = datetime.datetime.fromisoformat(cached_data["timestamp"]).astimezone()
            if (current_time - cache_time).total_seconds() < 12 * 3600:
                logging.debug(f"{CYAN}Verwende zwischengespeicherte Wetterdaten vom {cache_time}{RESET}")
                forecast = cached_data["forecast"]
                sunrise = cached_data.get("sunrise")
                sunset = cached_data.get("sunset")
                # Konvertiere Zeitstempel zurück zu datetime-Objekten
                for entry in forecast:
                    if isinstance(entry['dt'], str):
                        entry['dt'] = datetime.datetime.fromisoformat(entry['dt'])
                if isinstance(sunrise, str):
                    sunrise = datetime.datetime.fromisoformat(sunrise)
                if isinstance(sunset, str):
                    sunset = datetime.datetime.fromisoformat(sunset)
                return forecast, sunrise, sunset
    else:
        # Create cache directory if it does not exist
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
        # Create an empty cache file if it does not exist
        with open(cache_file, "w") as f:
            json.dump({"timestamp": current_time.isoformat(), "forecast": [], "sunrise": None, "sunset": None}, f)

    logging.debug(f"{CYAN}Abrufen der Wettervorhersage von OpenWeatherMap{RESET}")
    # Abrufen der Wettervorhersage
    exclude = 'minutely,daily,alerts'
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude={exclude}&appid={api_key}&units=metric"
    try:
        response = requests.get(url)
        response.raise_for_status()
        weather_data = response.json()
        # Extrahiere Zeitzonen-Offset
        timezone_offset = weather_data.get('timezone_offset', 0)
        # Extrahiere Sonnenaufgang und Sonnenuntergang aus 'current' Daten
        current_weather = weather_data.get('current', {})
        sunrise_unix = current_weather.get('sunrise')
        sunset_unix = current_weather.get('sunset')
        if sunrise_unix is not None:
            sunrise_utc = datetime.datetime.fromtimestamp(sunrise_unix, tz=datetime.timezone.utc)
            sunrise = sunrise_utc + datetime.timedelta(seconds=timezone_offset)
            sunrise = sunrise.astimezone()  # Sicherstellen, dass Zeitzoneninformationen vorhanden sind
        else:
            sunrise = None
        if sunset_unix is not None:
            sunset_utc = datetime.datetime.fromtimestamp(sunset_unix, tz=datetime.timezone.utc)
            sunset = sunset_utc + datetime.timedelta(seconds=timezone_offset)
            sunset = sunset.astimezone()
        else:
            sunset = None

        # Extrahieren der stündlichen Temperaturen
        hourly_forecast = weather_data.get('hourly', [])
        forecast = []
        for hour_data in hourly_forecast:
            # Konvertieren des Unix-Zeitstempels in datetime mit Zeitzoneninformation
            utc_dt = datetime.datetime.fromtimestamp(hour_data['dt'], tz=datetime.timezone.utc)
            # Anwenden des Zeitzonen-Offsets
            local_dt = utc_dt + datetime.timedelta(seconds=timezone_offset)
            local_dt = local_dt.astimezone()  # Stelle sicher, dass local_dt Zeitzoneninformation hat
            temp = hour_data['temp']
            forecast.append({'dt': local_dt, 'temp': temp})
        # Speichern der neuen Daten im Cache
        with open(cache_file, "w") as f:
            # Zeitstempel in Strings konvertieren
            for entry in forecast:
                entry['dt'] = entry['dt'].isoformat()
            cache_data = {
                "timestamp": current_time.isoformat(),
                "forecast": forecast,
                "sunrise": sunrise.isoformat() if sunrise else None,
                "sunset": sunset.isoformat() if sunset else None
            }
            json.dump(cache_data, f)
        return forecast, sunrise, sunset
    except requests.RequestException as e:
        logging.error(f"{RED}Fehler beim Abrufen der Wetterdaten: {e}{RESET}")
        # Wenn zwischengespeicherte Daten vorhanden sind, verwenden wir diese
        if os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                cached_data = json.load(f)
                logging.debug(f"{CYAN}Verwende zwischengespeicherte Wetterdaten{RESET}")
                forecast = cached_data["forecast"]
                sunrise = cached_data.get("sunrise")
                sunset = cached_data.get("sunset")
                # Konvertiere Zeitstempel zurück zu datetime-Objekten
                for entry in forecast:
                    if isinstance(entry['dt'], str):
                        entry['dt'] = datetime.datetime.fromisoformat(entry['dt'])
                if isinstance(sunrise, str):
                    sunrise = datetime.datetime.fromisoformat(sunrise)
                if isinstance(sunset, str):
                    sunset = datetime.datetime.fromisoformat(sunset)
                return forecast, sunrise, sunset
        else:
            logging.error(f"{RED}No weather data available{RESET}")
            exit(1)
       
def get_temperature_for_times(weather_forecast, departure_time, return_time):
    logging.debug(f"{GREEN}Retrieving temperatures for departure time {departure_time} and return time {return_time}{RESET}")
    current_time = datetime.datetime.now().astimezone()

    # Ensure departure_time and return_time are offset-aware
    if departure_time.tzinfo is None:
        departure_time = departure_time.astimezone()
    if return_time.tzinfo is None:
        return_time = return_time.astimezone()

    # Initialize variables
    departure_temperature = None
    return_temperature = None
    outside_temperatures = []

    # Convert 'dt' from string to datetime if needed and ensure it's offset-aware
    for forecast in weather_forecast:
        if isinstance(forecast['dt'], str):
            forecast['dt'] = datetime.datetime.fromisoformat(forecast['dt'])
        if forecast['dt'].tzinfo is None:
            forecast['dt'] = forecast['dt'].astimezone()

    # Collect temperatures from now until departure time
    for forecast in weather_forecast:
        forecast_time = forecast['dt']
        
        # Ensure forecast_time is timezone-aware
        if forecast_time.tzinfo is None:
            forecast_time = forecast_time.astimezone()

        # Collect temperatures within the range from current time to departure time
        if current_time <= forecast_time <= departure_time:
            outside_temperatures.append(forecast['temp'])

        # Capture the departure temperature at or after the departure time
        if departure_temperature is None and forecast_time >= departure_time:
            departure_temperature = forecast['temp']

        # Capture the return temperature at or after the return time
        if return_temperature is None and forecast_time >= return_time:
            return_temperature = forecast['temp']

        # Break the loop if both temperatures have been found and further data is unnecessary
        if forecast_time > return_time and return_temperature is not None and departure_temperature is not None:
            break  # We have all we need, so we can break the loop

    # Handle cases where temperature data is missing after loop completion

    # Check if the departure temperature was not found
    if departure_temperature is None:
        logging.error(f"{RED}No weather data available for departure time{RESET}")
        return None  # Signal a missing data error

    # Check if the return temperature was not found
    if return_temperature is None:
        logging.error(f"{RED}and no weather data available for return time:{RESET}")
        return None  # Signal a missing data error

    # Check if there are no temperatures between now and departure time
    if not outside_temperatures:
        logging.error(f"{RED}No weather data available between now and departure time{RESET}")
        return None  # Signal a missing data error

    # If all required data is available, return the collected values
    logging.debug(f"{GREEN}Departure temperature: {departure_temperature}°C, Return temperature: {return_temperature}°C{RESET}")
    logging.debug(f"{GREEN}Collected {len(outside_temperatures)} outside temperatures from now until departure{RESET}")
    return departure_temperature, return_temperature, outside_temperatures

def calculate_hours_till_sunrise(sunrise):
    """
    Berechnet die verbleibenden Stunden bis zum Sonnenaufgang.
    sunrise ist ein datetime-Objekt.
    Gibt die Stunden bis zum Sonnenaufgang zurück.
    """
    current_time = datetime.datetime.now().astimezone()
    time_until_sunrise = (sunrise - current_time).total_seconds() / 3600
    if time_until_sunrise < 0:
        time_until_sunrise += 24  # Falls Sonnenaufgang erst am nächsten Tag ist
    return time_until_sunrise



def weather_data_available_for_next_trip(weather_forecast, return_time):
    if not weather_forecast:
        return False

    last_weather_time = max(
        [entry['dt'] if isinstance(entry['dt'], datetime.datetime) else datetime.datetime.fromisoformat(entry['dt']) for entry in weather_forecast]
    )

    # Sicherstellen, dass last_weather_time und return_time beide Zeitzoneninformationen haben
    if last_weather_time.tzinfo is None:
        last_weather_time = last_weather_time.astimezone()

    if return_time.tzinfo is None:
        return_time = return_time.astimezone()

    if last_weather_time >= return_time:
        logging.warning(f"{YELLOW}Keine Wetterdaten bis zum Rückkehrzeitpunkt verfügbar.{RESET}")
        return False

    return True

def get_current_temperature(weather_forecast):
    if not weather_forecast:
        logging.error("No weather forecast data available")
        return None
    # Flatten the forecast list in case of nested lists
    def flatten(lst):
        flattened_list = []
        for item in lst:
            if isinstance(item, list):
                flattened_list.extend(item)
            else:
                flattened_list.append(item)
        return flattened_list
    weather_forecast = flatten(weather_forecast)
    current_time = datetime.datetime.now().astimezone()
    for forecast in weather_forecast:
        forecast_time = forecast['dt']
        if forecast_time >= current_time:
            return forecast['temp']
    return weather_forecast[-1]['temp']

# FIXME: def write_temperature_to_influx() seems to be missing
# this version by chatgpt 4o and not o1
def write_temperature_to_influx(temperature_data):
    """
    Writes temperature data to InfluxDB.
    
    Args:
        temperature_data (list): List of dictionaries containing temperature data with keys 'time' and 'temp'.
    """
    from influxdb_client import InfluxDBClient, Point, WritePrecision

    INFLUX_BASE_URL = settings['InfluxDB']['INFLUX_BASE_URL']
    INFLUX_ORGANIZATION = settings['InfluxDB']['INFLUX_ORGANIZATION']
    INFLUX_BUCKET = settings['InfluxDB']['INFLUX_BUCKET']
    INFLUX_ACCESS_TOKEN = settings['InfluxDB']['INFLUX_ACCESS_TOKEN']

    client = InfluxDBClient(
        url=INFLUX_BASE_URL,
        token=INFLUX_ACCESS_TOKEN,
        org=INFLUX_ORGANIZATION
    )
    write_api = client.write_api(write_options=SYNCHRONOUS)

    for entry in temperature_data:
        point = Point("weatherData") \
            .time(entry['time'], WritePrecision.NS) \
            .field("temperature", entry['temp'])
        
        try:
            write_api.write(
                bucket=INFLUX_BUCKET,
                org=INFLUX_ORGANIZATION,
                record=point
            )
            logging.debug(f"{GREY}Temperature data {entry} written to InfluxDB.{RESET}")
        except Exception as e:
            logging.error(f"{RED}Failed to write temperature data to InfluxDB: {e}{RESET}")


