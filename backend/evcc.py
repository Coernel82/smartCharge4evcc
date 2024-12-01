# evcc.py

# This project is licensed under the MIT License.

# Disclaimer: This code has been created with the help of AI (ChatGPT) and may not be suitable for
# AI-Training. This code ist Alpha-Stage

import datetime
import logging
import requests
import json
import os
import initialize_smartcharge

# Logging configuration with color scheme for debug information
logger = logging.getLogger('smartCharge')
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
GREY = "\033[37m"

EVCC_API_BASE_URL = initialize_smartcharge.settings['EVCC']['EVCC_API_BASE_URL']

def get_evcc_state():
    logging.debug(f"{GREEN}Retrieving EVCC state from {EVCC_API_BASE_URL}/api/state{RESET}")
    try:
        response = requests.get(f"{EVCC_API_BASE_URL}/api/state")
        response.raise_for_status()  # Check for HTTP errors
        evcc_state = response.json()
        # logging.debug(f"{GREY}Response from EVCC API: {evcc_state}{RESET}")
        return evcc_state
    except requests.RequestException as e:
        logging.critical(f"{RED}Error retrieving the EVCC state: {e}{RESET}")
        # stop the whole program if the EVCC state cannot be retrieved as this is vital
        raise SystemExit

# Function to send the calculated state of charge to EVCC
def set_evcc_soc(car_name, target_soc, time_windows):
    current_time = datetime.datetime.now().astimezone()
    in_time_window = False
    for window in time_windows:
        window_start = window['startsAt']
        # Ensure window_start is datetime object
        if isinstance(window_start, str):
            window_start = datetime.datetime.fromisoformat(window_start)
        price_end = window_start + datetime.timedelta(hours=1)
        window_start = window_start.astimezone()
        price_end = price_end.astimezone()
        if window_start <= current_time < price_end:
            in_time_window = True
            break
    if in_time_window:
        logging.debug(f"{CYAN}Within cheapest time window. Setting target SoC to {target_soc:.2f}%{RESET}")
        # Bevor wir den minSoC setzen, lesen wir den aktuellen Wert und cachen ihn
        get_evcc_minsoc(car_name)
        # Send target SoC to EVCC
        EVCC_API_BASE_URL = initialize_smartcharge.settings['EVCC']['EVCC_API_BASE_URL']
        url = f"{EVCC_API_BASE_URL}/api/vehicles/{car_name}/minsoc/{int(target_soc)}"
        try:
            response = requests.post(url)
            if response.status_code == 200:
                logging.debug(f"{GREEN}Successfully set target SoC to {target_soc:.2f}%{RESET}")
            else:
                logging.error(f"{RED}Failed to set target SoC. Response code: {response.status_code}{RESET}")
        except Exception as e:
            logging.error(f"{RED}Error setting target SoC: {e}{RESET}")
    else:
        logging.debug(f"{CYAN}Not within cheapest time window. Not setting target SoC.{RESET}")


def get_evcc_minsoc(car_name):
    logging.debug(f"{GREEN}Retrieving EVCC minSoC for {car_name} from {EVCC_API_BASE_URL}/api/state{RESET}")
    cache_file = "evcc_minsoc_cache.json"
    lock_file = "evcc_minsoc_cache.lock"
    
    # Wenn Lockfile existiert, nicht überschreiben
    if os.path.exists(lock_file):
        logging.debug(f"{YELLOW}Lockfile {lock_file} exists. Not overwriting minSoC cache.{RESET}")
        return None

    try:
        # API-Request an EVCC
        response = requests.get(f"{EVCC_API_BASE_URL}/api/state")
        response.raise_for_status()  # Prüfe auf HTTP-Fehler
        evcc_state = response.json()
        # logging.debug(f"{GREY}Response from EVCC API: {evcc_state}{RESET}")

        # Suche nach dem Fahrzeug mit dem Namen car_name in der API-Antwort
        vehicles = evcc_state.get('result', {}).get('vehicles', {})
        logging.debug(f"{GREEN}Vehicles retrieved: {vehicles}{RESET}")

        # Überprüfe, ob car_name in vehicles vorhanden ist
        if car_name in vehicles:
            vehicle = vehicles[car_name]
            min_soc = vehicle.get('minSoc')
            logging.debug(f"{GREEN}Retrieved minSoC value for {car_name}: {min_soc}{RESET}")

            if min_soc is not None:
                logging.debug(f"{GREEN}Caching vehicle minSoC: {min_soc}{RESET}")
                try:
                    with open(cache_file, "w") as f:
                        json.dump({"min_soc": min_soc}, f)
                    logging.debug(f"{GREEN}minSoC successfully cached in {cache_file}{RESET}")
                    # Lockfile erstellen
                    with open(lock_file, 'w') as f:
                        f.write('locked')
                    logging.debug(f"{GREEN}Created lockfile {lock_file}{RESET}")
                except Exception as file_error:
                    logging.error(f"{RED}Error writing to cache file: {file_error}{RESET}")
                return min_soc
            else:
                logging.error(f"{RED}The minSoC could not be found for vehicle {car_name}{RESET}")
                return None
        else:
            logging.error(f"{RED}No vehicle with the name {car_name} found in the API response{RESET}")
            return None

    except requests.RequestException as e:
        logging.error(f"{RED}Error retrieving the EVCC minSoC: {e}{RESET}")
        return None

def set_upper_price_limit(upper_limit_price_battery):
    """
    Sets the upper price limit for battery charging via API.
    """
    if upper_limit_price_battery is not None:
        post_url = f"{EVCC_API_BASE_URL}/api/batterygridchargelimit/{upper_limit_price_battery}"
        logging.debug(f"{GREY}Setting upper price limit via URL: {post_url}{RESET}")
        try:
            response = requests.post(post_url)
            response.raise_for_status()
            logging.info(f"{GREEN}Successfully set upper price limit: {upper_limit_price_battery:.4f} Euro{RESET}")
        except Exception as e:
            logging.error(f"{RED}Failed to set upper price limit: {e}{RESET}")
    else:
        logging.warning("Upper limit price is None. Cannot set the price limit.")