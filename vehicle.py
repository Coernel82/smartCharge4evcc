import logging
import numpy as np
import datetime
import requests


# Logging configuration with color scheme for debug information
logging.basicConfig(level=logging.DEBUG)
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"

# Definierte Gaussian-ähnliche Funktion zur Berechnung des Energieverbrauchs
def calculate_ev_energy_consumption(departure_temperature, return_temperature, distance, CONSUMPTION, BUFFER_DISTANCE, a=80.145, b=22.170, c=17.776, d=44.805):
    logging.debug(f"{BLUE}Calculating energy needed for {distance} km with departure temperature {departure_temperature}°C and return temperature {return_temperature}°C{RESET}")

    # Berechne die Hälfte der Strecke für Hin- und Rückfahrt
    half_distance = distance / 2

    # Berechnung des unbereinigten Energiebedarfs für die Hinfahrt
    uncorrected_energy_departure = (CONSUMPTION / 100) * (half_distance + BUFFER_DISTANCE / 2)
    logging.debug(f"Unbereinigter Energieverbrauch für die Hinfahrt: {uncorrected_energy_departure/1000:.1f} kWh")

    # Berechnung des Korrekturfaktors für die Abfahrtstemperatur
    correction_factor_departure = (a * np.exp(-((departure_temperature - b) ** 2) / (2 * c ** 2)) + d) / 100
    logging.debug(f"Korrekturfaktor für die Hinfahrt: {correction_factor_departure:.2f}")

    # Berechneter Energieverbrauch für die Hinfahrt
    energy_consumption_departure = uncorrected_energy_departure * correction_factor_departure
    logging.debug(f"Energieverbrauch für die Hinfahrt bei {departure_temperature:.1f}°C: {energy_consumption_departure/1000:.2f} kWh")

    # Berechnung des unbereinigten Energiebedarfs für die Rückfahrt
    uncorrected_energy_return = uncorrected_energy_departure
    logging.debug(f"Unbereinigter Energieverbrauch für die Rückfahrt: {uncorrected_energy_return/1000:.1f} kWh")

    # Berechnung des Korrekturfaktors für die Rückfahrtstemperatur
    correction_factor_return = (a * np.exp(-((return_temperature - b) ** 2) / (2 * c ** 2)) + d) / 100
    logging.debug(f"Korrekturfaktor für die Rückfahrt: {correction_factor_return:.2f}")

    # Berechneter Energieverbrauch für die Rückfahrt
    energy_consumption_return = uncorrected_energy_return * correction_factor_return
    logging.debug(f"Energieverbrauch für die Rückfahrt bei {return_temperature:.1f}°C: {energy_consumption_return/1000:.2f} kWh")

    # Gesamtenergieverbrauch (Hinfahrt + Rückfahrt)
    total_energy_consumption = energy_consumption_departure + energy_consumption_return
    logging.debug(f"Gesamtenergieverbrauch zur Erreichung von {distance} km: {total_energy_consumption/1000:.2f} kWh")

    return total_energy_consumption

def calculate_required_soc(energy_consumption, BATTERY_CAPACITY, DEGRADATION, BATTERY_YEAR):
    # Calculate the required state of charge (SoC) in percentage
    degradated_battery_capacity = BATTERY_CAPACITY * (1 - DEGRADATION) ** (datetime.datetime.now().year - BATTERY_YEAR)
    required_soc = (energy_consumption / degradated_battery_capacity) * 100
    if required_soc > 100:
        required_soc = 100
    logging.debug(f"{BLUE}Required energy: {energy_consumption/1000:.2f} kWh, Required SoC: {required_soc:.2f}%{RESET}")
    return required_soc

# Function to get the current SoC of EVCC
def get_evcc_soc(EVCC_API_BASE_URL, LOADPOINT_ID):
    logging.debug(f"{GREEN}Retrieving current SoC from EVCC{RESET}")
    try:
        response = requests.get(f"{EVCC_API_BASE_URL}/api/state")
        response.raise_for_status()
        data = response.json()
        loadpoints = data.get('result', {}).get('loadpoints', [])
        if len(loadpoints) > LOADPOINT_ID:
            current_soc = loadpoints[LOADPOINT_ID].get('vehicleSoc')
            if current_soc is not None:
                logging.debug(f"{GREEN}Current SoC: {current_soc}%{RESET}")
                return float(current_soc)
            else:
                logging.error(f"{RED}Current SoC not found{RESET}")
                return 0  # Default to 0 if not found
        else:
            logging.error(f"{RED}No loadpoints found{RESET}")
            return 0
    except Exception as e:
        logging.error(f"{RED}Error retrieving current SoC: {e}{RESET}")
        return 0