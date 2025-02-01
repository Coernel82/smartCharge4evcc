# utils.py

# This project is licensed under the MIT License.

# Disclaimer: This code has been created with the help of AI (ChatGPT) and may not be suitable for
# AI-Training. This code ist Alpha-Stage


import logging
import requests
import json
import os
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import numpy as np
from scipy.stats import linregress
import pandas as pd
from sklearn.linear_model import LinearRegression
import initialize_smartcharge
import datetime
import solarweather
import home
import math

                            
settings = initialize_smartcharge.load_settings()

####################################
# Calculations
####################################


# Logging configuration with color scheme for debug information
logger = logging.getLogger('smartCharge')
#logging.basicConfig(level=logging.DEBUG)
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
GREY = "\033[37m"


def ensure_datetime_with_timezone(time_value):
    """
    Converts a time value to a datetime object with timezone information.
    
    Parameters:
        time_value: The time value to be converted (can be datetime, int, float, or str).
    
    Returns:
        datetime object with timezone information or None on error.
    """
    if isinstance(time_value, datetime.datetime):
        if time_value.tzinfo is None:
            time_value = time_value.astimezone()
        return time_value
    elif isinstance(time_value, (int, float)):
        # Check if the timestamp is in milliseconds or seconds based on its length
        if len(str(int(time_value))) > 10:
            # Vermutlich in Millisekunden
            time_value = datetime.datetime.fromtimestamp(time_value / 1000).astimezone()
        else:
            time_value = datetime.datetime.fromtimestamp(time_value).astimezone()
        return time_value
    elif isinstance(time_value, str):
        try:
            time_value = datetime.datetime.fromisoformat(time_value)
            if time_value.tzinfo is None:
                time_value = time_value.astimezone()
            return time_value
        except ValueError:
            logging.error(f"Invalid time format: {time_value}")
            return None
    else:
        logging.error(f"Unexpected type for time value: {type(time_value)}")
        return None



def write_corrected_energy_consumption(hourly_climate_energy):
    """
    Writes the corrected hourly energy consumption data to InfluxDB.
    This function initializes an InfluxDB client and writes the corrected energy consumption
    data for a specified heat pump to the InfluxDB. Each entry in the provided data is tagged
    with a loadpoint name and timestamped before being written to the database.
    Args:
        hourly_climate_energy (list of dict): A list of dictionaries containing
            the corrected hourly energy consumption data. Each dictionary should have the keys:
            - 'energy_consumption' (float): The corrected energy consumption value.
            - 'time' (str): The timestamp of the energy consumption in ISO 8601 format.
        heatpump_name (str): The name of the heat pump for which the data is being corrected.
    Raises:
        InfluxDBError: If there is an error writing to the InfluxDB.
    """
    client = InfluxDBClient(
        # Initialize InfluxDB client
        url=settings['InfluxDB']['INFLUX_BASE_URL'],
        token=settings['InfluxDB']['INFLUX_ACCESS_TOKEN'],
        org=settings['InfluxDB']['INFLUX_ORGANIZATION']
    )
    write_api = client.write_api(write_options=SYNCHRONOUS)
  
    # Write the corrected energy consumption data to InfluxDB   
    for entry in hourly_climate_energy:
        timestamp = entry['time']
        point = Point("correctedEnergy") \
            .time(timestamp, WritePrecision.NS) \
            .tag("SmartCharge", "calculatedEnergy")
        
        for key, value in entry.items():
            if key == 'time':
                continue  # 'time' is used as timestamp
            elif key in ['climate_energy_nominal', 'climate_energy_corrected', 'baseload', 'maximum_pv']:
                point = point.field(key, float(value))
            elif key == 'pv_estimate':
                point = point.field(key, int(value))
            elif isinstance(value, (int, float)):
                point = point.field(key, float(value))
            else:
                point = point.tag(key, value)
        
        try:
            write_api.write(
                bucket='smartCharge4evcc',
                org=settings['InfluxDB']['INFLUX_ORGANIZATION'],
                record=point
            )
            logging.debug(f"{GREY}Corrected energy consumption data {entry} at {timestamp} written to InfluxDB.{RESET}")
        except Exception as e:
            logging.error(f"{RED}Failed to write data to InfluxDB: {e}{RESET}")

def query_influx_real_energy_readings():
    INFLUX_BASE_URL = settings['InfluxDB']['INFLUX_BASE_URL']
    INFLUX_ORGANIZATION = settings['InfluxDB']['INFLUX_ORGANIZATION']
    INFLUX_BUCKET = settings['InfluxDB']['INFLUX_BUCKET']
    INFLUX_ACCESS_TOKEN = settings['InfluxDB']['INFLUX_ACCESS_TOKEN']
    TIMESPAN_WEEKS = settings['InfluxDB']['TIMESPAN_WEEKS']

    # Initialize InfluxDB client
    client = InfluxDBClient(
        url=INFLUX_BASE_URL,
        token=INFLUX_ACCESS_TOKEN,
        org=INFLUX_ORGANIZATION
    )



    # Modify the Flux query to accumulate readings and get 7 * TIMESPAN_WEEKS readings at the end
    # / 3600000.0 to convert from Ws to Wh
    start_time = f"-{TIMESPAN_WEEKS * 7}d"
    # set stop time to past midnight
    stop_time = datetime.datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    flux_query_real_energy_readings = f"""
    from(bucket: "{INFLUX_BUCKET}")
        |> range(start: {start_time}, stop: time(v: "{stop_time}"))
        |> filter(fn: (r) => r["loadpoint"] == "Wärmepumpe")
        |> filter(fn: (r) => r["_measurement"] == "chargePower")
        |> aggregateWindow(every: 1d, fn: integral, createEmpty: false)
        |> map(fn: (r) => ({{_value: r._value / 3600.0, _time: r._time}}))
        |> yield(name: "mean")
    """
    query_api = client.query_api()
    result_real = query_api.query(org=INFLUX_ORGANIZATION, query=flux_query_real_energy_readings)
    logging.debug(f"{GREY}result_real from Influx: {result_real}{RESET}")
    # Check if results are empty
    if not result_real:
        logging.warning("No data returned from real query")
    return result_real

def query_influx_calculated_energy_readings():

    INFLUX_BASE_URL = settings['InfluxDB']['INFLUX_BASE_URL']
    INFLUX_ORGANIZATION = settings['InfluxDB']['INFLUX_ORGANIZATION']
    INFLUX_ACCESS_TOKEN = settings['InfluxDB']['INFLUX_ACCESS_TOKEN']
    TIMESPAN_WEEKS = settings['InfluxDB']['TIMESPAN_WEEKS']

    # Initialize InfluxDB client
    client = InfluxDBClient(
        url=INFLUX_BASE_URL,
        token=INFLUX_ACCESS_TOKEN,
        org=INFLUX_ORGANIZATION
    )

    # Define start and stop times explicitly
    start_time = f"-{TIMESPAN_WEEKS * 7}d"
    aggregate_time_window = f"{abs(int(start_time[:-1]))}d"

    # Log the time range
    logging.debug(f"Querying data from {start_time} till now")
    
    # TODO: [low prio] check if we need the season, if yes we need it for the real readings as well
    # season = get_season()
    # |> filter(fn: (r) => r["season"] == "{season}")

    flux_query_calculated = f"""
        from(bucket: "smartCharge4evcc")
            |> range(start: {start_time}, stop: today())
            |> filter(fn: (r) => r["SmartCharge"] == "calculatedEnergy")
            |> filter(fn: (r) => r["SmartCharge"] == "calculatedEnergy" and r["season"] != "interim")
            |> aggregateWindow(every: {aggregate_time_window}, fn: mean, createEmpty: false)
            |> yield(name: "mean")
    """

    # Query InfluxDB
    query_api = client.query_api()
    result_calculated = query_api.query(org=INFLUX_ORGANIZATION, query=flux_query_calculated)
    #logging.debug(f"Flux Query (Calculated): {flux_query_calculated}")
    logging.debug(f"{GREY}result_calculated from Influx: {result_calculated}{RESET}")
    # Check if results are empty
    if not result_calculated:
        logging.warning("No data returned from calculated query")
    return result_calculated

def update_correction_factor():
    correction_factor_summer = settings['House']['correction_factor_summer']
    correction_factor_winter = settings['House']['correction_factor_winter']

    
    result_calculated = query_influx_calculated_energy_readings()
    result_real = query_influx_real_energy_readings()
    
   
    real_energy = []
    for table in result_real:
        for record in table.records:
            real_energy.append(record['_value'])
    
    
     # if real_energy is empty abort
    if not real_energy:
        logging.error(f"{RED}[update correction factor] Real energy is empty - maybe because you are running the programm for just a short timespan. Aborting correction factor update.{RESET}")
        return
    else:
        logging.debug(f"{GREY}Real energy from InfluxDB: {real_energy}{RESET}")

    # Calculate the average real energy
    real_energy = np.mean(real_energy)
    logging.debug(f"{GREY}Average real energy from InfluxDB: {real_energy}{RESET}")
    
    # getting calculated values out of result_calculated
    total_climate_energy_nominal = 0
    total_climate_energy_corrected = 0
    total_baseload = 0
    total_MAXIMUM_PV = 0
    total_pv_estimate = 0
    count = 0
    
    for table in result_calculated:
        for record in table.records:
            field_name = record.values.get('_field', '')
            field_value = record.values.get('_value', 0)
            if field_name == 'climate_energy_nominal':
                total_climate_energy_nominal += field_value
            elif field_name =='climate_energy_corrected':
                total_climate_energy_corrected += field_value
            elif field_name == 'baseload':
                total_baseload += field_value
            elif field_name == 'maximum_pv':
                total_MAXIMUM_PV += field_value
            elif field_name == 'pv_estimate':
                total_pv_estimate += field_value
            count += 1


    average_climate_energy_nominal = total_climate_energy_nominal / count if count else 0
    average_baseload = total_baseload / count if count else 0
    average_MAXIMUM_PV = total_MAXIMUM_PV / count if count else 0
    average_pv_estimate = total_pv_estimate / count if count else 0
    average_climate_energy_corrected = total_climate_energy_corrected / count if count else 0

    # Calculate the new correction factor
    correction_factor = (average_climate_energy_corrected - average_climate_energy_nominal - average_baseload) * (average_MAXIMUM_PV / average_pv_estimate)
    
    season = get_season()
    # Apply the correction factor gradually by 0.03 = 3% per day
    if season == "summer":
        current_factor = settings['House']['correction_factor_summer']
        updated_factor = current_factor + 0.03 * (correction_factor - current_factor)
        settings['House']['correction_factor_summer'] = updated_factor
        correction_factor_summer = updated_factor
        logging.info(f"{GREEN}Gradually updated correction factor for summer to: {updated_factor}{RESET}")
    elif season == "winter":
        current_factor = settings['House']['correction_factor_winter']
        updated_factor = current_factor + 0.03 * (correction_factor - current_factor)
        settings['House']['correction_factor_winter'] = updated_factor
        logging.info(f"{GREEN}Gradually updated correction factor for winter to: {updated_factor}{RESET}")
        correction_factor_winter = updated_factor
    else:
        logging.info(f"{GREEN}Season not defined or in between seasons. No correction factor update applied.{RESET}")
        # Abort if no season is defined
        return

    # Bestimme den Pfad relativ zur utils.py-Datei
    settings_path = os.path.join(os.path.dirname(__file__), 'data', 'settings.json')

    # Update the correction factor in settings based on the season
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=4)

    # Write a log of the correction factor to correction_factor_log.txt
    # this is just to monitor the correction factor over time and monitor if the quality of the calculation is good
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        quality_of_calculation = (1 - abs(average_climate_energy_corrected - real_energy) / real_energy) * 100
        log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "correction_factor_summer": correction_factor_summer,
        "correction_factor_winter": correction_factor_winter,
        "quality_of_calculation": quality_of_calculation,
        }
        log_file_path = os.path.join(os.path.dirname(__file__), 'data', 'correction_factor_log.txt')
        with open(log_file_path, 'a') as log_file:
            log_file.write(json.dumps(log_entry) + '\n')

def update_correction_factor_nominal():
    "When there is no sun (less then 0.1% we can apply a correction factor to the energy certificate)"
    logging.info(f"{GREEN}Updating correction factor for nominal energy consumption{RESET}")
    # TODO: monitor the 0.001 value if it is too low or too high
    energy_cutoff = settings['House']['MAXIMUM_PV'] * 0.001

    INFLUX_BASE_URL = settings['InfluxDB']['INFLUX_BASE_URL']
    INFLUX_ORGANIZATION = settings['InfluxDB']['INFLUX_ORGANIZATION']
    INFLUX_ACCESS_TOKEN = settings['InfluxDB']['INFLUX_ACCESS_TOKEN']
    TIMESPAN_WEEKS = settings['InfluxDB']['TIMESPAN_WEEKS']
    BUCKET = settings['InfluxDB']['INFLUX_BUCKET']
    
    # get readings from the last 30 days with cloudy weather
    start_time = f"-{TIMESPAN_WEEKS * 7}d"

    flux_query_cloudy = f"""
        from(bucket: "{BUCKET}")
            |> range(start: {start_time}, stop: today())
            |> filter(fn: (r) => r["_measurement"] == "pvPower")
            |> filter(fn: (r) => r["_value"] <= {energy_cutoff})  // just get readings for very cloudy days
            |> aggregateWindow(every: 1d, fn: integral, createEmpty: false)
            |> yield(name: "integral")
    """
    # Initialize InfluxDB client
    client = InfluxDBClient(
        url=INFLUX_BASE_URL,
        token=INFLUX_ACCESS_TOKEN,
        org=INFLUX_ORGANIZATION
    )

    # Query InfluxDB
    query_api = client.query_api()
    cloudy_days = query_api.query(org=INFLUX_ORGANIZATION, query=flux_query_cloudy)

    # Create a list of timestamps for cloudy days
    cloudy_timestamps = []
    for table in cloudy_days:
        for record in table.records:
            cloudy_timestamps.append(record.get_time())
    logging.debug(f"{GREY}Cloudy days timestamps: {cloudy_timestamps}{RESET}")

    # get real energy readings from the last 30 days and filter out the ones which mach cloudy_timestamps
    result_real = query_influx_real_energy_readings()
    
    # working:
    """  real_energy = []
    for table in result_real:
        for record in table.records:
            real_energy.append(record['_value']) """
    
    # expression: result_real[0].records[0].row value: ['mean', 0, datetime.datetime(2024, 12, 7, 0, 0, tzinfo=datetime.timezone.utc), 5312.248716249997]

    real_energy = []
    for table in result_real:
        for record in table.records:
            if record.get_time() in cloudy_timestamps:
                real_energy.append(record['_value'])
    
     # if real_energy is empty abort
    if not real_energy:
        logging.error(f"{RED}Real energy for cloudy days is empty - maybe because you are running the programm for just a short timespan. Aborting correction factor update.{RESET}")
        return
    else:
        logging.debug(f"{GREY}Real energy for cloudy days from InfluxDB: {real_energy}{RESET}")

    # Calculate the average real energy
    real_energy = np.mean(real_energy)
    logging.debug(f"{GREY}Average real energy for cloudy daysfrom InfluxDB: {real_energy}{RESET}")

    
    # get climate_energy_nominal from the last 30 days and filter out the ones which match cloudy_timestamps
    result_calculated = query_influx_calculated_energy_readings()
    
    total_climate_energy_nominal = 0
    count = 0
    
    for table in result_calculated:
        for record in table.records:
            if record.get_time() in cloudy_timestamps:
                field_name = record.values.get('_field', '')
                field_value = record.values.get('_value', 0)
                if field_name == 'climate_energy_nominal':
                    total_climate_energy_nominal += field_value
                count += 1

    result_calculated = total_climate_energy_nominal / count if count else 0
    climate_energy_nominal = result_calculated

    logging.debug(f"{GREY}Total climate energy nominal for cloudy days: {total_climate_energy_nominal}{RESET}")
    logging.debug(f"{GREY}Count of records for cloudy days: {count}{RESET}")
    logging.debug(f"{GREY}Average climate energy nominal for cloudy days: {climate_energy_nominal}{RESET}")

    # now we know result_real (for cloudy days) and result_calculated (for cloudy days) and can calculate the correction factor
    # climate_energy_nominal = (abs(temp_difference) * HEATED_AREA * ENERGY_CERTIFICATE * correction_factor_summer_nominal / COP) / (365 * 24)
    # resolve for correction_factor_<season>_nominal

    correction_factor_summer_nominal = 0
    correction_factor_winter_nominal = 0
    season = get_season()
    if season == "summer":
        correction_factor_summer_nominal = real_energy / climate_energy_nominal
        logging.debug(f"{GREY}Correction factor for summer nominal: {correction_factor_summer_nominal}{RESET}")
    elif season == "winter":
        correction_factor_winter_nominal = real_energy / climate_energy_nominal
        logging.debug(f"{GREY}Correction factor for winter nominal: {correction_factor_winter_nominal}{RESET}")
    else:
        logging.info(f"{GREEN}Season not defined or in between seasons. No correction factor update applied.{RESET}")
        # Abort if no season is defined
        return
    
    # Apply the correction factor gradually by 0.03 = 3% per day
    if season == "summer":
        current_factor = settings['House']['correction_factor_summer_nominal']
        updated_factor = current_factor + 0.03 * (correction_factor_summer_nominal - current_factor)
        settings['House']['correction_factor_summer_nominal'] = updated_factor
        correction_factor_summer_nominal = updated_factor
        logging.info(f"{GREEN}Gradually updated correction factor nominal (for cloudy days) for summer to: {updated_factor}{RESET}")
    elif season == "winter":
        current_factor = settings['House']['correction_factor_winter_nominal']
        updated_factor = current_factor + 0.03 * (correction_factor_winter_nominal - current_factor)
        settings['House']['correction_factor_winter_nominal'] = updated_factor
        logging.info(f"{GREEN}Gradually updated correction factor nominal (for cloudy days) for winter to: {updated_factor}{RESET}")
        correction_factor_winter_nominal = updated_factor
    else:
        logging.info(f"{GREEN}Season not defined or in between seasons. No correction factor update applied.{RESET}")
        # Abort if no season is defined
        return

    # Bestimme den Pfad relativ zur utils.py-Datei
    settings_path = os.path.join(os.path.dirname(__file__), 'data', 'settings.json')

    # Update the correction factor in settings based on the season
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=4)
        logging.debug(f"{GREY}Updated settings with new correction factors and saved to {settings_path}{RESET}")

    # Write a log of the correction factor to correction_factor_log.txt
    # this is just to monitor the correction factor over time and monitor if the quality of the calculation is good
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        quality_of_calculation_nominal = (1 - abs(climate_energy_nominal - real_energy) / real_energy) * 100
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "correction_factor_summer_nominal": correction_factor_summer_nominal,
            "correction_factor_winter_nominal": correction_factor_winter_nominal,
            "quality_of_calculation_nominal": quality_of_calculation_nominal,
        }
        log_file_path = os.path.join(os.path.dirname(__file__), 'data', 'correction_factor_nominal_log.txt')
        with open(log_file_path, 'a') as log_file:
            log_file.write(json.dumps(log_entry) + '\n')
            logging.debug(f"{GREY}Logged correction factor update to {log_file_path}{RESET}")


    
    





####################################
# EVCC and other APIs
####################################

# EVCC

def reset_evcc_settings(evcc_api_base_url, car_name, loadpoint_id, cheapest_time_windows):
    # why loadpoint_id+1? --> https://github.com/evcc-io/evcc/issues/16826
    loadpoint_id += 1
    current_time = datetime.datetime.now(datetime.timezone.utc).astimezone()
    in_time_window = False
    for window in cheapest_time_windows:
        window_start = ensure_datetime_with_timezone(window['startsAt'])
        price_end = window_start + datetime.timedelta(hours=1)
        window_start = window_start.astimezone()
        price_end = price_end.astimezone()
        if window_start <= current_time < price_end:
            in_time_window = True
            break
    if not in_time_window:
        logging.debug(f"{RED}Not within cheapest time window. Resetting EVCC charging mode and minSoC.{RESET}")
        # Get cached charge mode
        cache_file_mode = "evcc_charge_mode_cache.json"
        if os.path.exists(cache_file_mode):
            with open(cache_file_mode, "r") as f:
                cached_data = json.load(f)
                cached_charge_mode = cached_data.get("charge_mode", "pv")
        else:
            cached_charge_mode = "pv"  # Default mode

        # Get cached minSoC
        cache_file_minsoc = "evcc_minsoc_cache.json"
        if os.path.exists(cache_file_minsoc):
            with open(cache_file_minsoc, "r") as f:
                cached_data = json.load(f)
                cached_min_soc = cached_data.get("min_soc", 0)
        else:
            cached_min_soc = 0  # Default minSoC

        # Reset the charging mode
        url_mode = f"{evcc_api_base_url}/api/loadpoints/{loadpoint_id}/mode/{cached_charge_mode}"
        try:
            response = requests.post(url_mode)
            if response.status_code == 200:
                logging.debug(f"{GREEN}Successfully reset EVCC charging mode to {cached_charge_mode}{RESET}")
            else:
                logging.error(f"{RED}Failed to reset charging mode. Response code: {response.status_code}{RESET}")
        except Exception as e:
            logging.error(f"{RED}Error resetting charging mode: {e}{RESET}")

        # Reset the minSoC
        url_minsoc = f"{evcc_api_base_url}/api/vehicles/{car_name}/minsoc/{int(cached_min_soc)}"
        try:
            response = requests.post(url_minsoc)
            if response.status_code == 200:
                logging.debug(f"{GREEN}Successfully reset EVCC minSoC to {cached_min_soc}%{RESET}")
            else:
                logging.error(f"{RED}Failed to reset minSoC. Response code: {response.status_code}{RESET}")
        except Exception as e:
            logging.error(f"{RED}Error resetting minSoC: {e}{RESET}")

        # Lockfile entfernen
        lock_file = "evcc_minsoc_cache.lock"
        if os.path.exists(lock_file):
            os.remove(lock_file)
        logging.debug(f"{GREEN}Removed lockfile {lock_file}{RESET}")

    else:
        logging.debug(f"{GREEN}Within cheapest time window. No need to reset charging mode or minSoC.{RESET}")




# other APIs

def get_electricity_prices(TIBBER_API_URL, TIBBER_HEADERS):
    logging.debug(f"{GREEN}Retrieving electricity prices from Tibber{RESET}")
    current_time = datetime.datetime.now().astimezone()
    today = current_time.date()
    tomorrow = today + datetime.timedelta(days=1)
    cache_valid_today = False
    cache_valid_tomorrow = False
    electricity_prices = []

    # Check if cache directory exists, create if not
    cache_dir = os.path.join(os.path.dirname(__file__), 'cache')
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    # Define cache file path in cache directory
    cache_file = os.path.join(cache_dir, "electricity_prices_cache.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                cached_data = json.load(f)
                cache_time = ensure_datetime_with_timezone(cached_data["timestamp"])
                electricity_prices = cached_data["prices"]

                # Prüfen, ob Daten für heute im Cache sind
                for price in electricity_prices:
                    price_datetime = ensure_datetime_with_timezone(price['startsAt'])
                    price_date = price_datetime.date()
                    if price_date == today:
                        cache_valid_today = True
                    elif price_date == tomorrow:
                        cache_valid_tomorrow = True

                # Validierung basierend auf der aktuellen Uhrzeit
                if current_time.hour >= 13:
                    if cache_valid_today and cache_valid_tomorrow:
                        logging.debug(f"{GREY}Verwende zwischengespeicherte Strompreise für heute und morgen vom {cache_time}{RESET}")
                        return electricity_prices
                else:
                    if cache_valid_today:
                        logging.debug(f"{GREY}Verwende zwischengespeicherte Strompreise für heute vom {cache_time}{RESET}")
                        # Rückgabe nur der heutigen Preise
                        return [p for p in electricity_prices if datetime.datetime.fromisoformat(p['startsAt']).date() == today]

        except Exception as e:
            logging.error(f"{RED}Fehler beim Laden des Cache: {e}{RESET}")
            # Weiter zum Abruf neuer Daten

    # Entscheiden, ob neue Daten abgerufen werden müssen
    need_fetch = False
    if current_time.hour >= 13:
        if not (cache_valid_today and cache_valid_tomorrow):
            need_fetch = True
    else:
        if not cache_valid_today:
            need_fetch = True

    if need_fetch:
        logging.debug(f"{GREY}Abrufen neuer Strompreise von Tibber{RESET}")
        # Definiere die GraphQL-Anfrage
        query = """
        {
          viewer {
            homes {
              currentSubscription {
                priceInfo {
                  today {
                    total
                    startsAt
                  }
                  tomorrow {
                    total
                    startsAt
                  }
                }
              }
            }
          }
        }
        """
        logging.info("Sende Anfrage an die Tibber API...")

        try:
            # Sende Anfrage an Tibber API
            response = requests.post(TIBBER_API_URL, json={"query": query}, headers=TIBBER_HEADERS)

            # Logge den Response-Statuscode
            logging.info(f"API-Antwort Statuscode: {response.status_code}")

            # Prüfe, ob die Anfrage erfolgreich war
            if response.status_code == 200:
                data = response.json()

                # Extrahiere Preise aus der Antwort
                price_info = data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]
                today_prices = price_info["today"]
                tomorrow_prices = price_info["tomorrow"]

                # Kombiniere die Preise von heute und morgen
                fetched_prices = today_prices + tomorrow_prices

                # Konvertiere Zeiten in datetime-Objekte
                for price in fetched_prices:
                    price['startsAt'] = ensure_datetime_with_timezone(price['startsAt'].replace('Z', '+00:00'))

                # Filtern der relevanten Preise basierend auf der aktuellen Uhrzeit
                required_dates = {today}
                if current_time.hour >= 13:
                    required_dates.add(tomorrow)

                filtered_prices = [p for p in fetched_prices if p['startsAt'].date() in required_dates]

                # Speichere die neuen Daten im Cache
                with open(os.path.join(cache_dir, "electricity_prices_cache.json"), "w") as f:
                    # Konvertiere die datetime-Objekte zurück in ISO-Strings
                    for price in filtered_prices:
                        price['startsAt'] = price['startsAt'].isoformat()
                    json.dump({"timestamp": current_time.isoformat(), "prices": filtered_prices}, f)

                # Überprüfen, ob die notwendigen Daten verfügbar sind
                dates_response = set([ensure_datetime_with_timezone(p['startsAt']).date() for p in filtered_prices])
                cache_valid_today = today in dates_response
                cache_valid_tomorrow = tomorrow in dates_response

                # 13 as that is the time of new electricity prices
                if current_time.hour >= 13:
                    if cache_valid_today and cache_valid_tomorrow:
                        logging.debug(f"{GREEN}Strompreise für heute und morgen sind verfügbar und wurden zwischengespeichert.{RESET}")
                        return fetched_prices
                    else:
                        logging.warning(f"{YELLOW}Strompreise für heute und/oder morgen sind noch nicht verfügbar.{RESET}")
                        return []
                else:
                    if cache_valid_today:
                        logging.debug(f"{GREEN}Strompreise für heute sind verfügbar und wurden zwischengespeichert.{RESET}")
                        # Rückgabe Preise
                        return fetched_prices
                    else:
                        logging.warning(f"{YELLOW}Strompreise für heute sind noch nicht verfügbar.{RESET}")
                        return []

            else:
                logging.error(f"Fehler bei der Anfrage: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            logging.error(f"Ein Fehler ist aufgetreten: {e}")
            return []

    else:
        logging.debug(f"{GREEN}Cache ist gültig. Verwende zwischengespeicherte Strompreise.{RESET}")
        if current_time.hour < 13:
            # Rückgabe nur der heutigen Preise
            return [p for p in electricity_prices if ensure_datetime_with_timezone(p['startsAt']).date() == today]
        elif cache_valid_today and cache_valid_tomorrow:
            return electricity_prices
        else:
            return []


# other

def find_cheapest_time_windows(electricity_prices, ev_energy_additional_purchase, departure_time, charge_parameter, charger=False):
    logging.debug(f"{BLUE}Finde günstigste Zeitfenster für den Kauf von {ev_energy_additional_purchase/1000:.2f} kWh Strom{RESET}")
    
    # Berechne die benötigte Ladezeit in Stunden
    if charger == True:
        # here the charge_parameter is the energy of the loadpoint!
        total_charge_hours = ev_energy_additional_purchase / charge_parameter
    else:
        total_charge_hours = charge_parameter 
    logging.debug(f"Benötigte Ladezeit: {total_charge_hours:.2f} Stunden")
    
    current_time = datetime.datetime.now().astimezone()
    
    # Filtere die Strompreise zwischen jetzt und der Abfahrtszeit
    valid_prices = []
    for price in electricity_prices:
        # Stelle sicher, dass 'startsAt' ein datetime-Objekt mit Zeitzoneninfo ist
        price['start'] = ensure_datetime_with_timezone(price['start'])
        price_time = price['start'].astimezone()
        
        price_end = price_time + datetime.timedelta(hours=1)  # Annahme: Zeitfenster dauert 1 Stunde
        
        # Berechne die tatsächliche verfügbare Dauer in jedem Zeitfenster
        window_start = max(price_time, current_time)
        window_end = min(price_end, departure_time)
        available_duration = (window_end - window_start).total_seconds() / 3600  # Dauer in Stunden
        
        if available_duration <= 0:
            continue  # Keine verfügbare Zeit in diesem Zeitfenster
        
        # Speichere die verfügbare Dauer im Preisdatensatz
        price['available_duration'] = available_duration
        valid_prices.append(price)
    
    if not valid_prices:
        logging.warning(f"{YELLOW}Keine gültigen Strompreise zwischen jetzt und Abfahrtszeit verfügbar. Es wird versucht, so viel wie möglich zu laden.{RESET}")
        return []
    
    # Sortiere die gefilterten Preise nach Gesamtpreis aufsteigend
    sorted_prices = sorted(valid_prices, key=lambda x: x['total'])
    
    # Wähle die günstigsten Zeitfenster aus, bis die benötigte Ladezeit erreicht ist
    selected_time_windows = []
    accumulated_charge_hours = 0.0
    for price in sorted_prices:
        selected_time_windows.append(price)
        accumulated_charge_hours += price['available_duration']
        if accumulated_charge_hours >= total_charge_hours:
            break
    
    if accumulated_charge_hours < total_charge_hours:
        logging.warning(f"{YELLOW}Nicht genügend Zeit in den günstigsten Zeitfenstern verfügbar, um die benötigte Ladezeit zu erreichen. Es wird so viel wie möglich geladen.{RESET}")
        # Wir fahren trotzdem mit den verfügbaren Zeitfenstern fort
    
    logging.info(f"{GREEN}Günstigste Zeitfenster ausgewählt!{RESET}")
    
    return selected_time_windows



def parse_weekday(weekday_str):
    weekdays = {
        'Montag': 0, 'Monday': 0,
        'Dienstag': 1, 'Tuesday': 1,
        'Mittwoch': 2, 'Wednesday': 2,
        'Donnerstag': 3, 'Thursday': 3,
        'Freitag': 4, 'Friday': 4,
        'Samstag': 5, 'Saturday': 5,
        'Sonntag': 6, 'Sunday': 6,
    }
    return weekdays.get(weekday_str.capitalize())

def calculate_remaining_hours(departure_time):
    """
    Calculate the remaining hours until a specified departure time.

    Args:
        departure_time (datetime): The departure time as a timezone-aware datetime object.

    Returns:
        float: The number of hours remaining until the departure time.
    """
    current_time = datetime.datetime.now(datetime.timezone.utc).astimezone()
    departure_time = departure_time.replace(tzinfo=datetime.timezone.utc).astimezone()
    remaining_time = departure_time - current_time
    remaining_hours = remaining_time.total_seconds() / 3600
    return remaining_hours

def calculate_hourly_energy_surplus(hourly_climate_energy, solar_forecast):
    """
    Calculate the hourly energy surplus by subtracting the climate_energy_corrected from the solar forecast.

    Args:
        hourly_climate_energy (list): List of dictionaries with keys 'time' and 'energy_consumption'.
        solar_forecast (list): List of dictionaries with keys 'time' and 'pv_estimate'.

    Returns:
        list: List of dictionaries with keys 'time' and 'energy_surplus'.
    """
    # Create dictionaries for quick access
    consumption_dict = {entry['time']: entry['climate_energy_corrected'] for entry in hourly_climate_energy}
    solar_dict = {entry['time']: entry['pv_estimate'] for entry in solar_forecast}

    # Find common timestamps
    common_times = sorted(set(consumption_dict.keys()) & set(solar_dict.keys()))

    hourly_energy_surplus = []

    for time in common_times:
        energy_consumption = consumption_dict[time]
        pv_estimate = solar_dict[time]

        # Calculate energy surplus
        energy_surplus = pv_estimate - energy_consumption

        hourly_energy_surplus.append({
            'time': time,
            'energy_surplus': energy_surplus
        })

    return hourly_energy_surplus

def get_usable_charging_energy_surplus(usable_energy, departure_time, ev_energy_gap, evcc_state, car_name, load_car=True):
    """
    Extract and sum up all energy values from usable_energy higher than 700 Watt during the timespan 
    from now till departure_time until the sum is higher or equal to ev_energy_gap.
    Change each list entry used to calculate the usable_energy to 0.
    
    Args:
        usable_energy (list): List of dictionaries with keys 'time' and 'pv_estimate'.
        departure_time (datetime): The departure time as a timezone-aware datetime object.
        ev_energy_gap (float): The energy gap in Wh that needs to be filled.
        load_car (bool): If True, only consider energy values above 700 Watt. If False, consider all energy values.
    
    Returns:
        tuple: usable_charging_energy_surplus, usable_energy
        usable_charging_energy_surplus is limited to a minimum loading energy of the loadpoint
        usable_energy is unlimited and even contains small energy amounts which can be used for devices which can fully modulate
    """
    current_time = datetime.datetime.now().astimezone()
    usable_charging_energy_surplus = 0

    for entry in usable_energy:
        time = entry['time']
        pv_estimate = entry['pv_estimate']
        # logging.debug(f"{GREY}usable charging energy surplus: Time: {time}, PV Estimate: {pv_estimate}{RESET}")

        # Ensure time is a datetime object
        if isinstance(time, str):
            time = datetime.datetime.fromisoformat(time)
        if time.tzinfo is None:
            time = time.astimezone()

        # Only consider times between now and departure time
        current_time = current_time.astimezone()
        departure_time = departure_time.astimezone()
        if current_time <= time <= departure_time:
    
            if load_car:
                loadpoint_id = None
                for ids, loadpoint in enumerate(evcc_state['result']['loadpoints']):
                    if loadpoint.get('vehicleName') == car_name:
                            loadpoint_id = ids # we do not POST so no + 1
                            break
                    if loadpoint_id is None:
                        raise ValueError(f"Car name {car_name} not found in EVCC state loadpoints")
                
                # Get maximum loadpoint energy from evcc
                maximum_loadpoint_current = evcc_state['result']['loadpoints'][loadpoint_id]['maxCurrent']
                phases_Enabled = evcc_state['result']['loadpoints'][loadpoint_id]['phasesEnabled']

                # now this is physics: P = U * I * sqrt(3) for 3 phases and P = U * I for 1 phase
                if phases_Enabled == 1:
                    maximum_loadpoint_energy = 230 * maximum_loadpoint_current
                elif phases_Enabled == 3:
                    maximum_loadpoint_energy = math.sqrt(3) * 230 * maximum_loadpoint_current
                else:
                    raise ValueError("phasesEnabled must be 1 or 3")
                
                # Minimum charging power for EV is roughly 1.4 kW - so we assume that 700 Watt can mean that there was enough energy available for charging
                if pv_estimate > 700:
                    if pv_estimate > maximum_loadpoint_energy:
                        pv_estimate_usable = maximum_loadpoint_energy
                        pv_estimate -= pv_estimate_usable
                        # through iterations this value gets higher and higher and is used for charging the car
                        usable_charging_energy_surplus += pv_estimate_usable
                        # logging.debug(f"{GREY}usable charging energy surplus: Added {pv_estimate} Wh to the surplus{RESET}")
                        # setting the nwe pv_estimate to the remaining energy (which will be used for other devices which can fully modulate)
                        entry['pv_estimate'] = pv_estimate # Set the remaining energy to 0 as for sure we used everything up 
                
                else:
                    usable_charging_energy_surplus += pv_estimate
                    logging.debug(f"{GREY}usable charging energy surplus: Added {pv_estimate} Wh to the surplus{RESET}")
                    entry['pv_estimate'] = 0  # Set the remaining energy to 0 as for sure we used everything up

                if usable_charging_energy_surplus >= ev_energy_gap:
                    logging.info(f"{GREEN}Usable energy surplus of {usable_charging_energy_surplus/1000} kWh added to plan.{RESET}")
                    break
    # usable_charging_energy_surplus is limited to a minimum loading energy of the loadpoint
    # whereas usable_energy is unlimited and even contains small energy amounts which can be used for devices which can fully modulate
    return usable_charging_energy_surplus, usable_energy


def get_dates_for_recurrence(recurrence_type):
    current_date = datetime.datetime.now().date()
    dates = []
    for i in range(7):  # Look ahead one week
        date = current_date + datetime.timedelta(days=i)
        if recurrence_type == 'daily':
            dates.append(date)
        elif recurrence_type == 'workdays' and date.weekday() < 5:
            dates.append(date)
        elif recurrence_type == 'weekends' and date.weekday() >= 5:
            dates.append(date)
    return dates

def combine_date_time(date, time_str):
    time_obj = datetime.datetime.strptime(time_str, '%H:%M').time()
    return datetime.datetime.combine(date, time_obj)

def get_season():
    """
    Determines the expected temperature for today based on the trend of the last 30 days.
    Retrieves temperature data from InfluxDB and performs linear regression.
    """
    INFLUX_BASE_URL = settings['InfluxDB']['INFLUX_BASE_URL']
    INFLUX_ORGANIZATION = settings['InfluxDB']['INFLUX_ORGANIZATION']
    INFLUX_ACCESS_TOKEN = settings['InfluxDB']['INFLUX_ACCESS_TOKEN']
    
   
    # Initialize InfluxDB client
    client = InfluxDBClient(
        url=INFLUX_BASE_URL,
        token=INFLUX_ACCESS_TOKEN,
        org=INFLUX_ORGANIZATION
    )

    flux_query_temperatures = f'''
    from(bucket: "smartCharge4evcc")
        |> range(start: -30d)
        |> filter(fn: (r) => r["_field"] == "outdoor_temp")
    '''
    query_api = client.query_api()
    points = query_api.query(org=INFLUX_ORGANIZATION, query=flux_query_temperatures)
    
    logging.debug(f"{GREY}Temperature data from InfluxDB: {points}{RESET}")
    # Convert to pandas DataFrame
    records = []
    for table in points:
        for record in table.records:
            records.append({'time': record.get_time(), 'mean_temp': record.get_value()})
    temperature_data = pd.DataFrame(records)
    if temperature_data.empty or len(temperature_data) < 7:
      logging.error(f"{YELLOW}No temperature data at all or less than 7 days available. Setting season to interim{RESET}")
      season = 'interim'
      return season
    temperature_data['time'] = pd.to_datetime(temperature_data['time'])
    logging.debug(f"{GREY}Temperature data: {temperature_data}{RESET}")
    # Prepare data for linear regression

    # Convert dates to ordinal format
    X = temperature_data['time'].map(datetime.datetime.toordinal).values.reshape(-1, 1)
    y = temperature_data['mean_temp'].values

    # Perform linear regression
    model = LinearRegression()
    model.fit(X, y)

    # Calculate expected temperature for today
    today_ordinal = np.array([[datetime.datetime.now().toordinal()]])
    expected_temperature = model.predict(today_ordinal)[0]


    # Determine the season based on the expected temperature
    summer_threshold = settings['House']['SUMMER_THRESHOLD']
    summer_threshold_hysteresis = settings['House']['SUMMER_THRESHOLD_HYSTERESIS']

    if expected_temperature >= summer_threshold + summer_threshold_hysteresis:
        season = 'summer'
    elif expected_temperature < summer_threshold - summer_threshold_hysteresis:
        season = 'winter'
    else:
        season = 'interim'
    logging.info(f"{GREEN}Expected temperature for today based on past readings (and not weather report): {expected_temperature:.2f}°C. Season determined: {season}{RESET}")
    return season

def cache_upper_price_limit(price_limit):
    """
    Cache the upper price limit to a file.

    This function writes the given price limit to a file located at
    '/cache/batteryGridChargeLimit.txt'. If the file does not exist,
    it creates an empty file first before writing the price limit.

    Args:
        price_limit (float): The upper price limit to be cached.
    """
    file_path = '/cache/batteryGridChargeLimit.txt'
    if not os.path.exists(file_path):
        with open(file_path, 'w') as f:
            pass  # Create an empty file
    with open(file_path, 'w') as f:
        f.write(str(price_limit))


def cache_current_maximum_soc_allowed(home_battery_energy_forecast):
    """
    Caches the current maximum state of charge (SOC) allowed for the home battery.
    This function retrieves the maximum SOC for the current hour from the provided
    home battery energy forecast and writes it to a file. If no forecast is found
    for the current hour, an error is logged.
    Args:
        home_battery_energy_forecast (list): A list of dictionaries containing
            the energy forecast for the home battery. Each dictionary should have
            the keys 'time' and 'energy'.
    Raises:
        None
    Returns:
        None
    """
    maximum_soc_for_this_hour = home_battery_energy_forecast['maximum_soc']
    current_time = datetime.datetime.now().astimezone()
    current_hour = current_time.replace(minute=0, second=0, microsecond=0)
    
    maximum_soc_for_this_hour = None
    for forecast in home_battery_energy_forecast:
        forecast_time = ensure_datetime_with_timezone(forecast['time'])
        if forecast_time == current_hour:
            maximum_soc_for_this_hour = forecast['energy']
            break

    if maximum_soc_for_this_hour is None:
        logging.error(f"{RED}No maximum SOC found for the current hour.{RESET}")
        return
    
    file_path = '/data/maximum_soc_allowed.txt'
    if not os.path.exists(file_path):
        with open(file_path, 'w') as f:
            pass  # Create an empty file
    with open(file_path, 'w') as f:
        f.write(str(maximum_soc_for_this_hour))
     
def cache_home_battery_charging_cost_per_kWh(home_battery_charging_cost_per_kWh):
    """
    Cache the home battery charging cost per kWh to a file.

    This function writes the provided home battery charging cost per kWh to a file
    located at '/data/chargingCostsHomeBattery.txt'. If the file does not exist, 
    it creates an empty file before writing the cost.

    Args:
        home_battery_charging_cost_per_kWh (float): The cost of charging the home battery per kWh.
    """
    file_path = '/data/chargingCostsHomeBattery.txt'
    if not os.path.exists(file_path):
        with open(file_path, 'w') as f:
            pass  # Create an empty file    
    with open(file_path, 'w') as f: 
        f.write(str(home_battery_charging_cost_per_kWh))
    
def get_current_electricity_price(electricity_prices):
    """
    Get the current electricity price from a list of electricity prices.

    This function retrieves the electricity price for the current hour from the provided
    list of electricity prices. If no price is found for the current hour, an error is logged.

    Args:
        electricity_prices (list): A list of dictionaries containing the electricity prices.
            Each dictionary should have the keys 'startsAt' and 'total'.

    Raises:
        None

    Returns:
        float: The current electricity price.
    """
    current_time = datetime.datetime.now().astimezone()
    current_hour = current_time.replace(minute=0, second=0, microsecond=0)
    
    current_price = None
    for total in electricity_prices:
        if isinstance(total, str):
            total = json.loads(total)
        price_time = ensure_datetime_with_timezone(total['startsAt'])
        if price_time == current_hour:
            current_price = total['total']
            break

    if current_price is None:
        logging.error(f"{RED}No electricity price found for the current hour.{RESET}")
        return None

    return current_price

def json_dump_all_time_series_data(weather_forecast, hourly_climate_energy, hourly_energy_surplus, electricity_prices, home_battery_energy_forecast, grid_feedin, required_charge, charging_plan, usable_energy, solar_forecast):
    """
    Dumps all time series into www/templates/time_series_data.json
    """
    time_series_data = {
        "weather_forecast": weather_forecast,
        "hourly_climate_energy": hourly_climate_energy,
        "hourly_energy_surplus": hourly_energy_surplus,
        "electricity_prices": electricity_prices,
        "home_battery_energy_forecast": home_battery_energy_forecast,
        "grid_feedin": grid_feedin,
        "required_charge": required_charge,
        "charging_plan": charging_plan,
        "usable_energy_for_ev": usable_energy,
        "solar_forecast": solar_forecast,
        #"future_grid_feedin": future_grid_feedin
    }

    with open(os.path.join(os.path.dirname(__file__), '..', 'www', 'templates', 'time_series_data.json'), 'w') as f:
        logging.debug(f"{GREY}Dumping all time series data to {__file__}{RESET}")
        json.dump(time_series_data, f, default=str, indent=4)

def calculate_price_limit_boostmode(settings, hourly_climate_energy, electricity_prices):
    """
    Calculate various parameters related to heating, such as the heat pump ID,
    average heating power, total climate energy, maximum heating time, and the current electricity price.
    """
    maximum_boost_lower_percentile = settings['House']['MAXIMUM_BOOST_LOWER_PERCENTILE']

    # Iterate through settings till you find the heat pump
    for _, loadpoint_data in settings['House']['AdditionalLoads'].items():
        if loadpoint_data['INTEGRATED_DEVICE']:
            is_metered = loadpoint_data['IS_METERED']
            average_heating_power = loadpoint_data['AVERAGE_HEATING_POWER']
            break
    else:
        raise ValueError("Heat pump not found in settings")

    if is_metered:
        average_heating_power = home.get_average_heating_energy()
    else:
        logging.info(f"{GREEN}The heat pump is not metered. Using average heating power from settings.{RESET}")

    total_climate_energy = sum(value['climate_energy_corrected'] for value in hourly_climate_energy)
    maximum_heating_time = (total_climate_energy / average_heating_power) / 60 # in hours

    # get the price spread of the electricity prices from lowest to highest
    lowest_price = min(electricity_prices, key=lambda x: x['total'])['total']
    highest_price = max(electricity_prices, key=lambda x: x['total'])['total']
    price_spread = highest_price - lowest_price

    # calculate the price limit for the boost mode
    price_limit_boostmode = lowest_price + maximum_boost_lower_percentile * price_spread
    
    return price_limit_boostmode

def calculate_price_limit_blocktime(weather_forecast, electricity_prices, settings):
    from math import floor
    maximum_kelvinminutes = settings['House']['MAXIMUM_KELVINMINUTES']
    indoor_temperature = settings['House']['INDOOR_TEMPERATURE']
    # Calculate average temperature for the available weather data
    # this is a bit a shortcut and not precise as we could calculate for each hour and interate
    total_temp = sum(forecast['temp'] for forecast in weather_forecast)
    average_temp = total_temp / len(weather_forecast) if weather_forecast else 0
    delta_K = indoor_temperature - average_temp
    maximum_blocktime_minutes = maximum_kelvinminutes / delta_K

    
    maximum_blocktime_hours = floor(maximum_blocktime_minutes / 60)

    # Find most expensive prices to block
    # ####################################
 
    # Sort the prices by the 'total' key from high to low
    electricity_prices_sorted = sorted(electricity_prices, key=lambda x: x.get('total'), reverse=True)
    
    # go through the prices. the position which equals maximum_blocktime_hours is the price we need
    price_limit_blocking = electricity_prices_sorted[maximum_blocktime_hours]

    # get 'total' key from the dictionary
    price_limit_blocking = price_limit_blocking.get('total')

    logging.info(f"{GREEN}Block heating for prices from {price_limit_blocking} upwards.{RESET}")
    return price_limit_blocking

def get_heatpump_id(settings):
    # Currently supports one heatpump only
    heatpump_id = settings['House']['AdditionalLoads']['0']['LOADPOINT_ID'] + 1 # + 1 because of 0-based index in /api/state and 1 based in POST
    return heatpump_id