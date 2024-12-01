# home.py

# This project is licensed under the MIT License.

# Disclaimer: This code has been created with the help of AI (ChatGPT) and may not be suitable for
# AI-Training. This code ist Alpha-Stage

import logging
import requests
import os
import json
import datetime
import utils
import initialize_smartcharge
import math
import time


# Logging configuration with color scheme for debug information
logger = logging.getLogger('smartCharge')
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
GREY = "\033[37m"

settings = initialize_smartcharge.load_settings()

EVCC_API_BASE_URL = settings['EVCC']['EVCC_API_BASE_URL']
home_batteries = settings['Home']['HomeBatteries']
heatpump_name = settings['House']['integrated_devices']['heatpump']


def get_home_battery_soc():
    """
    Ruft den aktuellen SoC der Hausbatterie ab.
    """
    logging.debug(f"Retrieving home battery SoC from {EVCC_API_BASE_URL}/api/state")
    try:
        response = requests.get(f"{EVCC_API_BASE_URL}/api/state")
        response.raise_for_status()
        data = response.json()
        battery_soc = data['result']['batterySoc']
        logging.debug(f"Current home battery SoC: {battery_soc}%")
        return battery_soc
    except Exception as e:
        logging.error(f"Failed to retrieve home battery SoC: {e}")
        return None

def calculate_remaining_home_battery_capacity(home_batteries_capacity, home_batteries_SoC):
    """
    Calculate the remaining capacity of home batteries.
    This function computes the remaining capacity of home batteries based on their total capacity and state of charge (SoC).
    Args:
        home_batteries_capacity (float): The total capacity of the home batteries in kWh.
        home_batteries_SoC (float): The state of charge of the home batteries as a percentage (0-100).
    Returns:
        float: The remaining capacity of the home batteries in kWh.
    
    """
    remaining_capacity = home_batteries_capacity * (1 - home_batteries_SoC / 100)
    logging.debug(f"Usable home battery capacity: {remaining_capacity:.2f} kWh")
    return remaining_capacity

def calculate_homebattery_soc_forcast_in_Wh(home_batteries_capacity, remaining_home_battery_capacity, usable_energy, home_energy, home_battery_efficiency):
    """
    Calculate the SoC forecast for the home batteries in Wh.
    This function computes the SoC forecast for the home batteries based on their total capacity, state of charge (SoC),
    remaining capacity, and regenerative energy surplus.
    Args:
        home_batteries_capacity (float): The total capacity of the home batteries in kWh.
        home_batteries_SoC (float): The state of charge of the home batteries as a percentage (0-100).
        remaining_home_battery_capacity (float): The remaining capacity of the home batteries in kWh.
        regenerative_energy_surplus (float): The regenerative energy surplus in kWh.
    Returns:
        float: The SoC forecast for the home batteries in Wh.
    """
    # Ensure regenerative_energy_surplus is sorted by time
    usable_energy = sorted(usable_energy, key=lambda x: x['time'])

    

    # round the current time to the nearest hour
    current_time = datetime.datetime.now().astimezone()
    if current_time.minute < 30:
        current_time = current_time.replace(minute=0, second=0, microsecond=0)
    else:
        current_time = (current_time + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

    cumulative_capacity = remaining_home_battery_capacity

    home_battery_energy_forecast = []

    # Add initial capacity at current_time
    home_battery_energy_forecast.append({
        'time': current_time,
        'energy': cumulative_capacity
    })
    grid_feedin = []
    required_charge = []
    # Loop over regenerative_energy_surplus
    for surplus in usable_energy:
        surplus_time = surplus['time']
        surplus_energy = surplus['pv_estimate']
        # Only consider surplus times after or equal to current_time
        if surplus_time >= datetime.datetime.now().astimezone():
            # Get corresponding home energy consumption
            home_consumption = next(
                (he.get('energy_consumption', 0) for he in home_energy if he['time'] == surplus_time),
                0
            )
            # Subtract home consumption from surplus energy
            net_energy = surplus_energy - home_consumption
            # Add net energy to cumulative_capacity
            cumulative_capacity += net_energy
            if cumulative_capacity > home_batteries_capacity:
                grid_feedin.append({
                    'time': surplus_time,
                    'energy': cumulative_capacity - home_batteries_capacity
                })
                cumulative_capacity = home_batteries_capacity
            elif cumulative_capacity < 0:
                cumulative_capacity = 0
                required_charge.append({
                    'time': surplus_time,
                    'energy': (cumulative_capacity - home_batteries_capacity) * 1 / home_battery_efficiency # we need to charge more as we lose energy!
                })
            # Append to forecast
            home_battery_energy_forecast.append({
                'time': surplus_time,
                'energy': cumulative_capacity
            })

    return home_battery_energy_forecast, grid_feedin, required_charge

def get_tariffFeedIn():
    """
    Fetches the current feed-in tariff from the EVCC API.
    """
    logging.debug(f"Fetching feed-in tariff from {EVCC_API_BASE_URL}/api/state")
    try:
        response = requests.get(f"{EVCC_API_BASE_URL}/api/state")
        response.raise_for_status()
        data = response.json()
        tariffFeedIn = data['result']['tariffFeedIn']
        logging.debug(f"Current feed-in tariff: {tariffFeedIn:.4f} €/kWh")
        return tariffFeedIn
    except Exception as e:
        logging.error(f"Failed to retrieve feed-in tariff: {e}")
        return None

def calculate_charging_plan(home_battery_energy_forecast, electricity_prices, purchase_threshold, battery_data, required_charge):
    """
    Calculate the charging plan for a home battery system based on energy forecasts, electricity prices, and required charge.
    Parameters:
    home_battery_energy_forecast (list of dict): A list of dictionaries containing energy forecasts for the home battery, each with a 'time' and 'energy' key.
    electricity_prices (list of dict): A list of dictionaries containing electricity prices, each with a 'startsAt' and 'total' key.
    purchase_threshold (float): The threshold price above which electricity should not be purchased.
    battery_data (list of dict): A list of dictionaries containing battery data, each with a 'BATTERY_LOADING_ENERGY' key.
    required_charge (float or dict): The required charge amount. If a float is provided, it will be converted to a dictionary with an 'energy' key.
    Returns:
    float: The maximum acceptable price for charging the battery.
    """
    
    # if we do not need to charge we still charge if we earn money with it
    if required_charge == 0:
        maximum_acceptable_price = get_tariffFeedIn() - purchase_threshold
        return maximum_acceptable_price
    
    # Ensure required_charge is a dictionary
    if isinstance(required_charge, float):
        required_charge = {'energy': required_charge}

    # Ensure home_battery_energy_forecast is sorted by time
    home_battery_energy_forecast = sorted(home_battery_energy_forecast, key=lambda x: x['time'])

    # Ensure electricity_prices is sorted by time
    sorted_electricity_prices = sorted(electricity_prices, key=lambda x: x['startsAt'])
    sorted_electricity_prices_copy = sorted_electricity_prices.copy()

    # Calculate charging time
    average_battery_efficiency = calculate_average_battery_efficiency(battery_data)
    charging_speed = sum(battery['BATTERY_LOADING_ENERGY'] for battery in battery_data)    
    
   
 

    # iterate over each hour to fill the energy gaps (energy < 0)
    current_price = get_current_price(sorted_electricity_prices)
    iterations = 0
    charge_for_next_hour = 0
    maximum_acceptable_price = None

    # Ensure we only iterate up to the shortest list length
    min_length = min(len(home_battery_energy_forecast), len(sorted_electricity_prices))

    for i in range(min_length):
        hour = home_battery_energy_forecast[i]
        iterations += 1
        if hour['energy'] < 0 or charge_for_next_hour > 0:
            if current_price > purchase_threshold + sorted_electricity_prices[0]['total']:
                logging.info(f"{RED}Current price ({current_price * 100:.2f} Cent) is above purchase threshold ({purchase_threshold * 100:.2f} Cent).{RESET}")
                if required_charge['energy'] > charging_speed:
                    charge_for_next_hour = required_charge['energy'] * 1 / average_battery_efficiency - charging_speed
                    required_charge['energy'] = charging_speed
                    # delete first element in sorted_electricity_prices
                    del sorted_electricity_prices[0]
                else:
                    charge_for_next_hour = charging_speed - required_charge['energy'] * 1 / average_battery_efficiency


                    logging.info(f"{RED}We need to charge {charge_for_next_hour:.2f} kWh for the next hour.{RESET}")
    # Find the maximum price
    # the maximum price is the nth element in 'sorted_electricity_copy' where n is the number of iterations - 1
    maximum_acceptable_price = sorted_electricity_prices_copy[iterations - 1]['total']

    return maximum_acceptable_price


def get_current_price(electricity_prices):
    """
    Findet den aktuellen Strompreis in der Liste der Strompreise.

    Args:
        electricity_prices (list): Liste der Strompreise, wobei jeder Preis ein Dictionary ist,
                                   das unter anderem den Schlüssel 'total' enthält.

    Returns:
        float: Der aktuelle Strompreis oder None, wenn die Liste leer ist.
    """
    if not electricity_prices:
        logging.warning("Die Liste der Strompreise ist leer.")
        return None

    # Der aktuelle Strompreis ist der erste Preis in der Liste
    current_time = datetime.datetime.now(datetime.timezone.utc).replace(minute=0, second=0, microsecond=0)
    current_price = next(
        (price['total'] for price in electricity_prices
        if datetime.datetime.fromisoformat(price['startsAt']).replace(minute=0, second=0, microsecond=0) == current_time),
        None
    )
    
    # FIXME: we get this twice:
        #INFO:root:Der aktuelle Strompreis beträgt (26.24 Cent)
        #INFO:root:Average battery efficiency: 93.00%
        #INFO:root:Average battery efficiency: 93.00%
        #INFO:root:Der aktuelle Strompreis beträgt (26.24 Cent)

    logging.info(f"{GREEN}Der aktuelle Strompreis beträgt ({current_price * 100:.2f} Cent){RESET}")
    return current_price


def calculate_hourly_house_energy_consumption(solar_forecast, weather_forecast):  
    baseload_data = initialize_smartcharge.get_baseload()
    logging.debug(f"{GREEN}calculate_hourly_house_energy_consumption called with {len(solar_forecast)} solar entries and {len(weather_forecast)} weather entries{RESET}")
    
    # Einstellungen laden
    HEATED_AREA = settings['House']['HEATED_AREA']
    INDOOR_TEMPERATURE = settings['House']['INDOOR_TEMPERATURE']
    ENERGY_CERTIFICATE = settings['House']['ENERGY_CERTIFICATE']
    COP = settings['House']['integrated_devices']['heatpump']['COP']
    SUMMER_THRESHOLD = settings['House']['SUMMER_THRESHOLD']
    correction_factor_summer = settings['House']['correction_factor_summer']
    correction_factor_winter = settings['House']['correction_factor_winter']
    MAXIMUM_PV = settings['House']['MAXIMUM_PV']
    
    # Funktion zum Normalisieren der Zeit
    def normalize_time(dt):
        if dt.minute < 30:
            return dt.replace(minute=0, second=0, microsecond=0)
        else:
            return (dt + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    
    # Convert time strings to datetime objects and normalize in solar_forecast
    for entry in solar_forecast:
        if isinstance(entry['time'], str):
            entry['time'] = datetime.datetime.fromisoformat(entry['time'])
        entry['time'] = normalize_time(entry['time'])
    
    # Convert 'dt' strings to datetime objects and normalize in weather_forecast
    for entry in weather_forecast:
        if isinstance(entry['dt'], str):
            entry['dt'] = datetime.datetime.fromisoformat(entry['dt'])
        entry['dt'] = normalize_time(entry['dt'])
    
    # Dictionaries für schnellen Zugriff erstellen
    solar_dict = {entry['time']: entry for entry in solar_forecast}
    weather_dict = {entry['dt']: entry for entry in weather_forecast}
    
    # Gemeinsame Zeitstempel finden
    common_times = sorted(set(solar_dict.keys()) & set(weather_dict.keys()))
    logging.info(f"{GREEN}Found {len(common_times)} common timestamps between solar and weather forecasts:{RESET}")
    # logging.debug(f"{GREY}{common_times}{RESET}")
    hourly_climate_energy = []
    
    season = utils.get_season()
    for time in common_times:
        outdoor_temp = weather_dict[time]['temp']
        pv_estimate = solar_dict[time]['pv_estimate']
    
        # Initialize climate_energy_corrected
        climate_energy_corrected = 0
    
        # Temperaturdifferenz berechnen
        temp_difference = INDOOR_TEMPERATURE - outdoor_temp
    
        # Nominalen Klimaenergieverbrauch pro Stunde berechnen       
        climate_energy_nominal = (abs(temp_difference) * HEATED_AREA * ENERGY_CERTIFICATE / COP) / (365 * 24)
    
        # Berechnung der Heizenergie unter Einbezug der PV-Leistung
        global_radiation_summer = (pv_estimate / MAXIMUM_PV) * correction_factor_summer
        global_radiation_winter = (pv_estimate / MAXIMUM_PV) * correction_factor_winter
    
        
        
        
        if season == 'summer':
            climate_energy_corrected = climate_energy_nominal + global_radiation_summer + get_baseload_for_time(time, baseload_data) # PLUS as it is cooling
            logging.info(f"{GREEN}Kühlbedarf um {time} bei {climate_energy_corrected:.2f} kWh bei {outdoor_temp:.1f}°C Außentemperatur.{RESET}")
        elif season == 'winter':
            climate_energy_corrected = climate_energy_nominal - global_radiation_winter - get_baseload_for_time(time, baseload_data) # MINUS as it is heating
            logging.debug(f"{GREEN}Heizbedarf um {time} bei {climate_energy_corrected:.2f} kWh bei {outdoor_temp:.1f}°C Außentemperatur.{RESET}")
        else:
            if not hasattr(calculate_hourly_house_energy_consumption, "interim_season_logged"):
                calculate_hourly_house_energy_consumption.interim_season_logged = True
                logging.info(f"{GREEN}Interim season! No heating or cooling needed. No update of correction factor{RESET}")
            # set all values to 0
            climate_energy_nominal = 0
            climate_energy_corrected = 0
            

        
        hourly_climate_energy.append({
            'time': time,
            'season': season,
            'climate_energy_nominal': climate_energy_nominal,
            'baseload' : get_baseload_for_time(time, baseload_data),
            'climate_energy_corrected': climate_energy_corrected,
            'outdoor_temp': outdoor_temp,
            'maximum_pv': MAXIMUM_PV,
            'pv_estimate': pv_estimate
        })
    
    # if we resolve the formula above we can calculate the correction factor - which will be done in another function
    # correction_factor_summer = (climate_energy_corrected - climate_energy_nominal - baseload) * (MAXIMUM_PV / pv_estimate)
    return hourly_climate_energy

def get_baseload_for_time(time, baseload_data):
    # logging.debug(f"{GREY}Searching for BASE_LOAD entry matching time {time}{RESET}")
    #logging.debug(f"{GREY}Baseload data: {baseload_data}{RESET}")
    # Get the day of the week, hour, and minute from 'time'
    day_of_week = time.strftime('%A')  # 'Monday', 'Tuesday', etc.
    time_seconds = time.hour * 3600 + time.minute * 60 + time.second
    #logging.debug(f"{GREY}Searching for BASE_LOAD entry matching day {day_of_week} and time {time}{RESET}")

    # Collect all entries for the given dayOfWeek
    entries_for_day = [entry for entry in baseload_data if entry['dayOfWeek'] == day_of_week]
    # logging.debug(f"{GREY}Found {len(entries_for_day)} entries for day {day_of_week}{RESET}")
    # logging.debug(f"{GREY}Entries for day {day_of_week}: {entries_for_day}{RESET}")
    if entries_for_day:
        # Find the entry with the closest time
        min_time_diff = None
        closest_baseload_value = None
        for entry in entries_for_day:
            entry_seconds = entry['hour'] * 3600 + entry['minute'] * 60
            time_diff = abs(time_seconds - entry_seconds)
            if min_time_diff is None or time_diff < min_time_diff:
                min_time_diff = time_diff
                closest_baseload_value = entry['floating_average_baseload']
        return closest_baseload_value
    else:
        logging.warning(f"{CYAN}No BASE_LOAD entry matching day {day_of_week}{RESET}")
        return 0  # Default value if no match is found

def process_battery_data(home_battery_json_data, home_battery_api_data):
    logging.debug(f"{GREY}Processing battery data{RESET}")
    """
    Gets all the info about the home batteries.
    Returns: processed_data (list of dictionaries)
    """
    # Ensure that home_battery_json_data is a list
    if not isinstance(home_battery_json_data, list):
        home_battery_json_data = [home_battery_json_data]
    # Ensure that home_battery_api_data is a list
    if not isinstance(home_battery_api_data, list):
        home_battery_api_data = [home_battery_api_data]
    # logging.debug(f"{GREY}Home battery JSON data: {home_battery_json_data}{RESET}")
    # logging.debug(f"{GREY}Home battery API data: {home_battery_api_data}{RESET}")   

    processed_data = []
    for json_data, api_data in zip(home_battery_json_data, home_battery_api_data):
        # Convert json_data to dict if it's a float
        if isinstance(json_data, float):
            logging.warning("json_data is a float, converting to empty dictionary.")
            json_data = {}
        # Convert api_data to dict if it's a float
        if isinstance(api_data, float):
            logging.warning("api_data is a float, converting to empty dictionary.")
            api_data = {}
        
        # combine the two dictionaries
        combined_data = {**json_data, **api_data}
        
        processed_data.append(combined_data)
    logging.debug(f"{GREY}Processed battery data: {processed_data}{RESET}")
    return processed_data

def get_home_batteries_capacities():
    """
    Calculates the usable and total capacity for each battery.
    """
    cache_folder = 'cache'
    cache_file = os.path.join(cache_folder, 'usable_capacity_cache.json')

    def get_batteryEnergyFromAPI():
        logging.debug("Fetching battery energy from API")
        response = requests.get(f"{EVCC_API_BASE_URL}/api/state")
        response.raise_for_status()
        data = response.json()
        batteryEnergy = data['result']['batteryEnergy']
        # Save to cache
        logging.debug(f"Saving battery energy {batteryEnergy} to cache")
        with open(cache_file, 'w') as f:
            json.dump({
                'batteryEnergy': batteryEnergy,
                'timestamp': time.time()
            }, f)

    # Check if cache file exists
    if not os.path.exists(cache_file):
        logging.debug("No cache file exists, creating new one")
        # Create cache folder if it doesn't exist
        os.makedirs(cache_folder, exist_ok=True)
        # Call API and store result in cache
        try:
            get_batteryEnergyFromAPI()
        except Exception as e:
            logging.error(f"Error fetching battery energy from API: {e}")
            batteryEnergy = 0
    else:
        # Check if cache is older than one week
        cache_age = time.time() - os.path.getmtime(cache_file)
        one_week_seconds = 7 * 24 * 60 * 60
        if cache_age > one_week_seconds:
            logging.debug("Cache is older than one week, updating")
            # Cache is old, update it
            try:
                get_batteryEnergyFromAPI()
            except Exception as e:
                logging.error(f"Error fetching battery energy from API: {e}")
                batteryEnergy = 0
        else:
            logging.debug("Using existing cache file")
            # Load from cache
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
                batteryEnergy = cache_data.get('batteryEnergy', 0)
                logging.debug(f"Loaded battery energy {batteryEnergy} from cache")
                
    return batteryEnergy # which is the total_usable_capacity

def calculate_average_battery_efficiency(battery_data):
    """
    Calculates the weighted average efficiency of the home batteries.
    """
    capacities = [battery['battery_energy'] for battery in battery_data]
    efficiencies = [battery['BATTERYSYSTEM_EFFICIENCY'] for battery in battery_data]
    weighted_efficiency = sum(cap * eff for cap, eff in zip(capacities, efficiencies)) / sum(capacities)
    logging.info(f"Average battery efficiency: {weighted_efficiency:.2%}")
    return weighted_efficiency


def get_home_battery_charging_cost_per_Wh(battery_data):
    import home  # To avoid circular import error
    # Calculate marginal cost for battery inverter
    for battery_data in battery_data:
        battery_id = battery_data['battery_id']
        # Calculate marginal cost for inverter
        battery_inverter_price = battery_data['BATTERY_INVERTER_PRICE']
        battery_inverter_lifetime_years = battery_data['BATTERY_INVERTER_LIFETIME_YEARS']
        battery_loading_energy = battery_data['BATTERY_LOADING_ENERGY']
        battery_efficiency = battery_data['BATTERYSYSTEM_EFFICIENCY']

        # 0.5 is used to present that the inverter works half of the time
        total_inverter_work_per_hour = battery_inverter_lifetime_years * 365 * 24 * battery_loading_energy * 0.5 * (1 / battery_efficiency)
        marginal_cost_inverter_per_Wh = battery_inverter_price / total_inverter_work_per_hour

        logging.debug(f"Battery {battery_id} - Marginal Cost Inverter per Wh: {marginal_cost_inverter_per_Wh}")

        # Calculate marginal cost for battery
        degradation = battery_data['BATTERY_DEGRADATION']
        battery_year = battery_data['BATTERY_PURCHASE_YEAR']
        battery_purchase_price = battery_data['BATTERY_PURCHASE_PRICE']
        battery_max_cycles = battery_data['BATTERY_MAXIMUM_LOADING_CYCLES_LIFETIME']

        usable_capacity = battery_data['battery_energy']
        age = datetime.datetime.now().year - battery_year
        degradated_capacity = usable_capacity * (1 - degradation) ** age

        logging.debug(f"Battery {battery_id} - Degraded Capacity: {degradated_capacity}")

        marginal_cost_battery = battery_purchase_price / (battery_efficiency * battery_max_cycles * degradated_capacity)

        logging.debug(f"Battery {battery_id} - Marginal Cost Battery per Wh: {marginal_cost_battery}")

        # Total charging cost per Wh
        charging_cost_per_Wh = marginal_cost_inverter_per_Wh + marginal_cost_battery
        logging.debug(f"Battery {battery_id} - Charging Cost per Wh: {charging_cost_per_Wh}")

    # we just return one value as evcc just handles one virtual battery even if there are multiple physical batteries
    return charging_cost_per_Wh
