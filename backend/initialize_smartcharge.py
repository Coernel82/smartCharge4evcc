# initialize.py

# This project is licensed under the MIT License.

# Disclaimer: This code has been created with the help of AI (ChatGPT) and may not be suitable for
# AI-Training. This code ist Alpha-Stage

import os
import logging
import json 
import requests
import datetime
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import pandas as pd

# Logging configuration with color scheme for debug information
logger = logging.getLogger('smartCharge')
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
GREY = "\033[37m"


# Lade die Einstellungen aus der settings.json-Datei
def load_settings():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    settings_file = os.path.join(script_dir, 'data', 'settings.json')
    with open(settings_file, 'r', encoding='utf-8') as f:
        settings = json.load(f)
    return settings

settings = load_settings()

def save_settings(settings):
    with open('settings.json', 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

# def load_influx():
#     return settings['Influx']

# Funktionen zum Einlesen der Ladepunkte und Autos
def load_loadpoints():
    # logging.info(f"{GREY}Settings loaded:\n{settings} {RESET}")
    return settings['Loadpoints']

def load_cars():
    """
    Load the list of cars from the settings.

    Returns:
        list: A list of cars as defined in the settings.
    """
    return settings['Cars']

# Funktion zum Einlesen des Fahrplans
def read_usage_plan():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, 'data', 'usage_plan.json')

    logging.debug(f"Lese den Fahrplan aus der JSON-Datei: {file_path}")
    usage_plan = {}

    # Überprüfen, ob die Datei existiert
    if not os.path.exists(file_path):
        logging.error(f"Fahrplan-Datei nicht gefunden: {file_path}")
        exit(1)

    # Öffnen und Lesen der JSON-Datei
    with open(file_path, 'r') as f:
        # create a list of dictionaries from the JSON file
        usage_plan = json.load(f)
        return usage_plan

# Funktion zum Einlesen der Zuordnung von Autos zu Ladepunkten
def load_assignments():
    """
    Loads loadpoint assignments from a JSON file.

    The function determines the directory of the current script, constructs the path to the 
    'loadpoint_assignments.json' file located in the 'data' subdirectory, and reads the 
    assignments data from the file.

    Returns:
        list: A list of assignments loaded from the JSON file.

    Raises:
        FileNotFoundError: If the 'loadpoint_assignments.json' file does not exist.
        json.JSONDecodeError: If the file is not a valid JSON.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    assignments_file = os.path.join(script_dir, 'data', 'loadpoint_assignments.json')
    with open(assignments_file, 'r') as f:
        assignments_data = json.load(f)
    return assignments_data['assignments']



def get_home_battery_data_from_json(): 
    """
    Reads home battery data from settings and returns relevant information.

    Returns:
        list: A list of dictionaries containing battery info and calculated marginal costs.
    """
    battery_data = []
    home_batteries = settings['Home']['HomeBatteries'].keys()
    for battery_id in home_batteries:
        battery_info = settings['Home']['HomeBatteries'][battery_id].copy()
        battery_info['battery_id'] = battery_id
        battery_data.append(battery_info)
    # logging.debug(f"{GREY}Home battery data: {battery_data}{RESET}")
    return battery_data

    
def get_home_battery_data_from_api():
    """
    Retrieves the state of charge (SoC) and current energy of home batteries from the API.

    Returns:
        list: A list of dictionaries containing battery SoC, energy, and calculated capacity.
    """
    evcc_api_base_url = settings['EVCC']['EVCC_API_BASE_URL']
    home_batteries = settings['Home']['HomeBatteries'].keys()
    try:
        response = requests.get(f"{evcc_api_base_url}/api/state")
        response.raise_for_status()
        data = response.json()
        
        battery_data = []
        batteries_info = data['result']['battery']
        
        for battery_index, battery_id in enumerate(home_batteries):
            battery_info = batteries_info[battery_index]
            battery_soc = battery_info['soc']
            battery_energy = battery_info['energy']
            battery_data.append({
                'battery_id': battery_id,
                'battery_soc': battery_soc,
                'battery_energy': battery_energy
            })
        logging.debug(f"{GREY}Home battery API data: {battery_data}{RESET}")
        return battery_data
    except Exception as e:
        logging.error(f"Failed to retrieve home battery data from API: {e}")
        return []

def get_loadpoint_id_for_car(car_name):
    evcc_api_base_url = settings['EVCC']['EVCC_API_BASE_URL']
    try:
        response = requests.get(f"{evcc_api_base_url}/api/state")
        response.raise_for_status()
        data = response.json()
        loadpoints = data['result']['loadpoints']
        for loadpoint in loadpoints:
            if loadpoint.get('vehicleName') == car_name:
                for loadpoint in loadpoints:
                    if loadpoint.get('vehicleName') == car_name:
                       return loadpoints.index(loadpoint)
    except Exception as e:
        logging.error(f"Failed to retrieve loadpoint ID for car {car_name}: {e}")
        return None
    
def get_baseload_from_influxdb():
    INFLUX_BASE_URL = settings['InfluxDB']['INFLUX_BASE_URL']
    INFLUX_ORGANIZATION = settings['InfluxDB']['INFLUX_ORGANIZATION']
    INFLUX_BUCKET = settings['InfluxDB']['INFLUX_BUCKET']
    INFLUX_ACCESS_TOKEN = settings['InfluxDB']['INFLUX_ACCESS_TOKEN']
    TIMESPAN_WEEKS_BASELOAD = settings['InfluxDB']['TIMESPAN_WEEKS_BASELOAD']
    
    # Initialize InfluxDB client
    client = InfluxDBClient(
        url=INFLUX_BASE_URL,
        token=INFLUX_ACCESS_TOKEN,
        org=INFLUX_ORGANIZATION
    )


    # Define start and stop times explicitly
    start_time = f"-{TIMESPAN_WEEKS_BASELOAD * 7}d"

    # Log the time range
    logging.debug(f"Querying data from {start_time} till now to get baseload")

    # divison by 3600000 to convert from Ws to kWh
    flux_query_baseload = f"""
    from(bucket: "{INFLUX_BUCKET}")
        |> range(start: {start_time}, stop: today())
        |> filter(fn: (r) => r["SmartCharge"] == "homePower")
        |> aggregateWindow(every: 1h, fn: integral, createEmpty: false)
        |> map(fn: (r) => ({{_value: r._value / 3600000.0, _time: r._time}}))
        |> yield(name: "integral")
    """
    # Query InfluxDB
    query_api = client.query_api()
    result_baseload = query_api.query(org=INFLUX_ORGANIZATION, query=flux_query_baseload)
    # logging.debug(f"Flux Query (Baseload): {flux_query_baseload}")
    logging.debug(f"Query Result (Baseload): {result_baseload}")
    # Check if results are empty
    if not result_baseload:
        logging.warning("No data returned from baseload query")

    
    records = []
    for table in result_baseload:
        for record in table.records:
            records.append(record.values)

    # In DataFrame umwandeln
    df = pd.DataFrame(records)
    df['_time'] = pd.to_datetime(df['_time'])

    # Wochentag, Stunde und Minute extrahieren
    df['dayOfWeek'] = df['_time'].dt.day_name()
    df['hour'] = df['_time'].dt.hour
    df['minute'] = df['_time'].dt.minute

    # Durchschnitt pro Zeitpunkt berechnen
    floating_average_baseload = df.groupby(['dayOfWeek', 'hour', 'minute'])['_value'].mean().reset_index()
    floating_average_baseload.rename(columns={'_value': 'floating_average_baseload'}, inplace=True)

    logging.debug(f"{GREY}Floating average baseload: {floating_average_baseload}{RESET}")
    return floating_average_baseload


def get_baseload():
    """
    Fetches the baseload energy consumption data, either from a cache file if it is less than a week old,
    or by fetching new data if the cache is older than a week or does not exist.
    The function checks for a cache file named 'baseload_cache.json' in the 'data' directory
    relative to the script's location. If the cache file exists and is less than a week old,
    it returns the cached baseload data. Otherwise, it fetches new baseload data, updates the
    cache file, and returns the new data.
    Returns:
        baseload (type): The baseload data, either from the cache or newly fetched.
    """
    baseload_serializable = []

    script_dir = os.path.dirname(os.path.abspath(__file__))
    cache_file = os.path.join(script_dir, 'cache', 'baseload_cache.json')

    # Check if cache file exists
    if not os.path.exists(cache_file):
        # Create cache directory if it doesn't exist
        cache_dir = os.path.dirname(cache_file)
        os.makedirs(cache_dir, exist_ok=True)

        # Create an empty cache file with the current timestamp
        baseload = get_baseload_from_influxdb()
        baseload_serializable = baseload.to_dict(orient='records')
        cache_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'baseload': []
        }
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=4)

    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
            cache_timestamp = datetime.datetime.fromisoformat(cache_data['timestamp']).astimezone()
            current_time = datetime.datetime.now().astimezone()

            # Check if the cache is older than a week
            if (current_time - cache_timestamp).days < 7:
                logging.debug(f"{GREY}Using cached baseload data{RESET}")
                # logging.debug(f"{GREY}Cached baseload data timestamp: {cache_data}{RESET}")
                return cache_data['baseload']
            else:
                # Fetch new baseload data (this is a placeholder, replace with actual fetching logic)
                baseload = get_baseload_from_influxdb() 

            # Convert DataFrame to a serializable format
            baseload_serializable = baseload.to_dict(orient='records')

            # Write new data to cache
            cache_data = {
                'timestamp': datetime.datetime.now().isoformat(),
                'baseload': baseload_serializable
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=4)


    logging.debug(f"{GREY}Fetched new baseload data and updated cache{RESET}")
    return baseload_serializable

def get_usage_plan_from_json():
    usage_plan_path = os.path.join(os.path.dirname(__file__), 'data', 'usage_plan.json')
    with open(usage_plan_path, 'r') as f:
        usage_plan = json.load(f)
    # logging.debug(f"{GREY}Usage plan loaded from JSON: {usage_plan}{RESET}")
    return usage_plan

def delete_deprecated_trips():
    """
    Deletes trips from the usage plan that are older than the current date.
    """
    usage_plan = read_usage_plan()
    current_date = datetime.datetime.now().date()
    usage_plan = [trip for trip in usage_plan if isinstance(trip, dict)]  # Ensure each trip is a dictionary
    for trip in usage_plan:
        trip_date = datetime.datetime.strptime(trip.get('date', ''), '%Y-%m-%d').date()
        if trip_date < current_date:
            usage_plan.remove(trip)
    return usage_plan

def github_check_new_version(current_version):
    """
    Checks for a new version of the script on GitHub.
    """
    # Get the latest release from the GitHub API
    github_api_url = "https://api.github.com/repos/Coernel82/smartCharge4evcc/releases/latest"
    try:
        response = requests.get(github_api_url)
        response.raise_for_status()
        latest_release = response.json()
        latest_version = latest_release['tag_name']
        if latest_version != current_version:
            logging.info(f"{YELLOW}A new version of the script is available: {latest_version}{RESET}")
        else:
            logging.info(f"{GREEN}The script is up to date{RESET}")
    except Exception as e:
        logging.error(f"Failed to check for a new version: {e}")

def get_evcc_state():
    """
    Retrieves the state of the EVCC from the API.

    Returns:
        dict: The state of the EVCC as a dictionary.
    """
    evcc_api_base_url = settings['EVCC']['EVCC_API_BASE_URL']
    try:
        response = requests.get(f"{evcc_api_base_url}/api/state")
        response.raise_for_status()
        evcc_state = response.json()
        # logging.debug(f"{GREY}EVCC state: {evcc_state}{RESET}")
        return evcc_state
    except Exception as e:
        logging.error(f"Failed to retrieve EVCC state: {e}")
        return {}

