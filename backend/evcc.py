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
        # we must query the api in this case as we need fresh data every 4 minutes
        response = requests.get(f"{EVCC_API_BASE_URL}/api/state")
        response.raise_for_status()  # Check for HTTP errors
        evcc_state = response.json()
        # logging.debug(f"{GREY}Response from EVCC API: {evcc_state}{RESET}")
        return evcc_state
    except requests.RequestException as e:
        logging.critical(f"{RED}Error retrieving the EVCC state: {e}{RESET}")
        # stop the whole program if the EVCC state cannot be retrieved as this is vital
        raise SystemExit

def get_evcc_minsoc(car_name, evcc_state):
    logging.debug(f"{GREEN}Retrieving EVCC minSoC for {car_name} from evcc_state")
    cache_file = "evcc_minsoc_cache.json"
    lock_file = "evcc_minsoc_cache.lock"
    
    # Wenn Lockfile existiert, nicht überschreiben
    if os.path.exists(lock_file):
        logging.debug(f"{YELLOW}Lockfile {lock_file} exists. Not overwriting minSoC cache.{RESET}")
        return None



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

def lock_battery(fake_loadpoint_id, lock):
    """
    Locks the battery to prevent charging. This is done by a trick: There is no direct locking option in evcc, however
    setting a loadpoint to quick charge ("now") will lock the home battery. For this you just need to
    """
    if lock == True:
        post_url_dischargecontrol = f"{EVCC_API_BASE_URL}/api/batterydischargecontrol/true" 
        post_url_chargemode = f"{EVCC_API_BASE_URL}/api/loadpoints/{fake_loadpoint_id}/mode/now"
        logging.debug(f"{GREY}Locking battery via URL: {post_url_dischargecontrol}{RESET}")
    else:
        post_url_dischargecontrol = f"{EVCC_API_BASE_URL}/api/batterydischargecontrol/false" 
        post_url_chargemode = f"{EVCC_API_BASE_URL}/api/loadpoints/{fake_loadpoint_id}/mode/off"
        logging.debug(f"{GREY}Unlocking battery via URL: {post_url_chargemode}{RESET}")

    
    try:
        response = requests.post(post_url_chargemode)
        response.raise_for_status()
        logging.info(f"{GREEN}Successfully locked battery{RESET}")
    except Exception as e:
        logging.error(f"{RED}Failed to lock battery. Refer to the readme - this is likely due to not having set up a fake loadpoint: {e}{RESET}")
    
    try:
        response = requests.post(post_url_dischargecontrol)
        response.raise_for_status()
        logging.debug(f"Successfully activated battery discharge control")
    except Exception as e:
        logging.error(f"{RED}Failed to activate battery discharge control: {e}{RESET}")


def set_dischargecontrol(is_active):
    if is_active == True:
        is_active = "true"
    else:
        is_active = "false"
    post_url = f"{EVCC_API_BASE_URL}/api/batterydischargecontrol/{is_active}"
    logging.debug(f"{GREY}Setting discharge control via URL: {post_url}{RESET}")
    try:
        response = requests.post(post_url)
        response.raise_for_status()
        logging.info(f"{GREEN}Successfully set discharge control: {False}{RESET}")
    except Exception as e:
        logging.error(f"{RED}Failed to set discharge control: {e}{RESET}")