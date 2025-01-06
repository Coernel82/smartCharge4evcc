# vehicle.py

# This project is licensed under the MIT License.

# Disclaimer: This code has been created under the help of AI (ChatGPT) and may not be suitable for
# AI-Training. This code ist Alpha-Stage

import logging
import numpy as np
import datetime
import requests
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
LILAC = "\033[95m"

EVCC_API_BASE_URL = initialize_smartcharge.settings['EVCC']['EVCC_API_BASE_URL']


def sort_trips_by_earliest_departure_time(usage_plan):
    """
    Sort all trips in the usage plan by the earliest departure time, regardless of car.
    Args:
        usage_plan (dict): A dictionary containing the usage plan with car names as keys and lists of trips as values.
    Returns:
        list: A list of trips sorted by earliest departure time. Each trip includes 'departure_time', 'return_time', and 'car_name'.
    """
    
    all_trips = []
    now = datetime.datetime.now()

    for car_name, car_trips in usage_plan.items():
        # Process recurring trips
        for trip in car_trips.get('recurring', []):
            departure_day_name = trip['departure_date']
            departure_time_str = trip['departure_time']
            return_day_name = trip.get('return_date', departure_day_name)
            return_time_str = trip['return_time']

            # Convert day names to indexes
            weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            departure_weekday = weekdays.index(departure_day_name)
            return_weekday = weekdays.index(return_day_name)

            departure_time = datetime.datetime.strptime(departure_time_str, '%H:%M').time()
            return_time = datetime.datetime.strptime(return_time_str, '%H:%M').time()

            # Calculate next departure date
            days_ahead_departure = (departure_weekday - now.weekday()) % 7
            if days_ahead_departure == 0 and departure_time <= now.time():
                days_ahead_departure = 7
            departure_date = now.date() + datetime.timedelta(days=days_ahead_departure)
            departure_datetime = datetime.datetime.combine(departure_date, departure_time)

            # Calculate next return date
            days_ahead_return = (return_weekday - departure_weekday) % 7
            return_date = departure_date + datetime.timedelta(days=days_ahead_return)
            return_datetime = datetime.datetime.combine(return_date, return_time)

            trip['departure_datetime'] = departure_datetime
            trip['return_datetime'] = return_datetime
            trip['car_name'] = car_name

            all_trips.append(trip)

        # Process non-recurring trips
        for trip in car_trips.get('non_recurring', []):
            departure_date_str = trip['departure_date']  # Updated key
            departure_time_str = trip['departure_time']
            return_date_str = trip['return_date'] # old code: trip.get('return_date', departure_date_str)
            return_time_str = trip['return_time']

            departure_date = datetime.datetime.strptime(departure_date_str, '%Y-%m-%d').date()
            departure_time = datetime.datetime.strptime(departure_time_str, '%H:%M').time()
            departure_datetime = datetime.datetime.combine(departure_date, departure_time)

            return_date = datetime.datetime.strptime(return_date_str, '%Y-%m-%d').date()
            return_time = datetime.datetime.strptime(return_time_str, '%H:%M').time()
            return_datetime = datetime.datetime.combine(return_date, return_time)

            if departure_datetime >= now:
                trip['departure_datetime'] = departure_datetime
                trip['return_datetime'] = return_datetime
                trip['car_name'] = car_name
                all_trips.append(trip)

    # Sort all trips by departure_datetime
    sorted_trips = sorted(all_trips, key=lambda x: x['departure_datetime'])

    return sorted_trips

# Definierte Gaussian-ähnliche Funktion zur Berechnung des Energieverbrauchs
def calculate_ev_energy_consumption(departure_temperature, return_temperature, distance, CONSUMPTION, BUFFER_DISTANCE, car_name, evcc_state, loadpoint_id):
    """
    Calculate the energy consumption of an electric vehicle (EV) for a round trip based on temperatures and distance.
    Parameters:
    departure_temperature (float): The temperature at the start of the trip in degrees Celsius.
    return_temperature (float): The temperature at the end of the trip in degrees Celsius.
    distance (float): The total distance of the round trip in kilometers.
    CONSUMPTION (float): The base energy consumption of the EV in kWh per 100 km.
    BUFFER_DISTANCE (float): Additional buffer distance in kilometers to account for deviations.
    a (float, optional): Parameter for the correction factor calculation. Default is 80.145.
    b (float, optional): Parameter for the correction factor calculation. Default is 22.170.
    c (float, optional): Parameter for the correction factor calculation. Default is 17.776.
    d (float, optional): Parameter for the correction factor calculation. Default is 44.805.
    Source for graph:
    https://www.geotab.com/de/blog/elektrofahrzeuge-batterie-temperatur/
    Gauss-Formula for graph created with ChatGPT
    Returns:
    float: The total energy consumption for the round trip in kWh.
    """
    """"""
    logging.info(f"{GREEN}Calculating energy needed for {distance} km with departure temperature {departure_temperature}°C and return temperature {return_temperature}°C{RESET}")
    half_distance = distance / 2     # Berechne die Hälfte der Strecke für Hin- und Rückfahrt
    # unkorrigierter Energieverbrauch für die Fahrten
    uncorrected_energy_departure = (CONSUMPTION / 100) * (half_distance + BUFFER_DISTANCE / 2)
    uncorrected_energy_return = uncorrected_energy_departure

    a=80.145
    b=22.170
    c=17.776
    d=44.805

    # Berechnung des Korrekturfaktors für die Abfahrtstemperatur und Rückfahrtstemperatur
    correction_factor_departure = (a * np.exp(-((departure_temperature - b) ** 2) / (2 * c ** 2)) + d) / 100
    correction_factor_return = (a * np.exp(-((return_temperature - b) ** 2) / (2 * c ** 2)) + d) / 100
    
    
    # Energieverbrauch (Hinfahrt + Rückfahrt) unter Berücksichtigung der Korrekturfaktoren    
    energy_consumption_departure = uncorrected_energy_departure * correction_factor_departure
    energy_consumption_return = uncorrected_energy_return * correction_factor_return

    # Gesamtenergieverbrauch (Hinfahrt + Rückfahrt)
    total_energy_consumption = energy_consumption_departure + energy_consumption_return

    logging.debug(f"{GREY}Hinfahrt: {uncorrected_energy_departure / 1000:.1f} kWh x {correction_factor_departure:.2f} = "
                f"{energy_consumption_departure / 1000:.2f} kWh bei {departure_temperature:.1f}°C | "
                f"Rückfahrt: {uncorrected_energy_return / 1000:.1f} kWh x {correction_factor_return:.2f} = "
                f"{energy_consumption_return / 1000:.2f} kWh bei {return_temperature:.1f}°C{RESET}")

    logging.info(f"{GREEN}Gesamtenergieverbrauch zur Erreichung von {distance} km: {total_energy_consumption / 1000:.2f} kWh{RESET}")
    
    
    degradated_battery_capacity = calculate_car_battery_degradation(evcc_state, car_name, loadpoint_id)
    if total_energy_consumption > degradated_battery_capacity:
        logging.warning(f"{CYAN}However: Energy consumption exceeds battery capacity of the car!{RESET}")
        total_energy_consumption = degradated_battery_capacity
        
    return total_energy_consumption

def calculate_car_battery_degradation(evcc_state, car_name, loadpoint_id):
    """
    Calculate the battery degradation of an electric vehicle (EV) given its car name.
    Parameters:
    car_name (str): Name of the car as defined in cars_settings.
    Returns:
    float: The degraded battery capacity in kWh.
    """
    # get variables we need for the calculation
    cars_settings = initialize_smartcharge.settings['Cars']
    car_id = None
    for i, car in initialize_smartcharge.settings['Cars'].items():
        if car['CAR_NAME'] == car_name:
            car_id = i
            break
    if car_id is None:
        logging.error(f"{RED}Car with name {car_name} not found in settings{RESET}")
        return 0
    cars_settings = initialize_smartcharge.settings['Cars'][car_id]
    battery_capacity = cars_settings.get('BATTERY_CAPACITY')
    degradation = cars_settings.get('DEGRADATION')
    battery_year = cars_settings.get('BATTERY_YEAR')
    
    # get odometer from evcc_state
    odometer = evcc_state['result']['loadpoints'][loadpoint_id]['vehicleOdometer']
    
    
    # If odometer is 0, calculate degradation by age
    if odometer == 0:
        logging.warning(f"{YELLOW}Odometer is 0, calculating degradation by age{RESET}")
        # Use values from car_settings since we have a zero odometer
        degradated_battery_capacity = battery_capacity * (1 - degradation) ** (datetime.datetime.now().year - battery_year)
        return degradated_battery_capacity
    else:
        logging.info(f"{GREEN}Calculating degradation by odometer{RESET}")
        # Polynomial-based degradation by odometer
        a = 2.3027725883259073e-12
        b = -1.2056443455051694e-6
        c = 1.00
        degradation_car_battery_percentage = a * odometer**2 + b * odometer + c
        if degradation_car_battery_percentage <= 0:
            degradation_car_battery_percentage = 0
            logging.critical(f"{RED}Degradation by odometer is negative or zero{RESET}")
        degradated_battery_capacity = battery_capacity * degradation_car_battery_percentage
        return degradated_battery_capacity

def calculate_required_soc_topup(energy_consumption, car, evcc_state, loadpoint_id, trip_name):
    logging.info(f"{GREEN}Calculating required state of charge (SoC) for energy consumption of {energy_consumption/1000:.2f} kWh for car {car} for trip {trip_name}{RESET}")
    # Calculate the required state of charge (SoC) in percentage
    # we need kWh not Wh --> /1000
    degradated_battery_capacity = calculate_car_battery_degradation(evcc_state, car, loadpoint_id) 
    required_soc_topup = (energy_consumption / degradated_battery_capacity) * 100
    if required_soc_topup > 100:
        required_soc_topup = 100
    if required_soc_topup < 0:
        required_soc_topup = 0
    logging.debug(f"{BLUE}Required energy: {energy_consumption/1000:.2f} kWh, Required SoC: {required_soc_topup:.2f}%{RESET}")
    return required_soc_topup

# Function to get the current SoC of EVCC
def get_evcc_soc(loadpoint_id, evcc_state):
    if loadpoint_id is None:
        logging.error(f"{RED}loadpoint_id is None{RESET}")
        return 0
    logging.debug(f"{GREEN}Retrieving current SoC from EVCC for loadpoint_id {loadpoint_id}{RESET}")

    loadpoints = evcc_state.get('result', {}).get('loadpoints', [])
    if len(loadpoints) > loadpoint_id:
        current_soc = loadpoints[loadpoint_id].get('vehicleSoc')
        if current_soc is not None:
            logging.debug(f"{GREEN}Current SoC: {current_soc}%{RESET}")
            return float(current_soc)
        else:
            logging.error(f"{RED}Current SoC not found{RESET}")
            return 0  # Default to 0 if not found
    else:
        logging.error(f"{RED}No loadpoints found{RESET}")
        return 0

def get_loadpoint_and_car_info(assignment, loadpoints, cars):
    """
    Retrieve loadpoint and car information based on the given assignment.
    Args:
        assignment (dict): A dictionary containing the assignment details with keys 'CAR_NAME' and 'LOADPOINT_ID'.
        loadpoints (list): A list of dictionaries, each representing a loadpoint with at least the key 'LOADPOINT_ID'.
        cars (list): A list of dictionaries, each representing a car with at least the key 'CAR_NAME'.
    Returns:
        tuple: A tuple containing two elements:
            - loadpoint (dict): The loadpoint dictionary that matches the 'LOADPOINT_ID' from the assignment.
            - car (dict or None): The car dictionary that matches the 'CAR_NAME' from the assignment, or None if not found.
    Logs:
        - Critical: If the loadpoint with the specified 'LOADPOINT_ID' is not found.
        - Error: If the car with the specified 'CAR_NAME' is not found.
    """
    car_name = assignment.get('CAR_NAME')
    loadpoint_id = assignment.get('LOADPOINT_ID')

    loadpoint = next((lp for lp in loadpoints if lp['LOADPOINT_ID'] == loadpoint_id), {})
    car = next((c for c in cars if c['CAR_NAME'] == car_name), None)

    if not loadpoint:
        logging.critical(f"{LILAC}Ladepunkt mit ID {loadpoint_id} nicht gefunden für Zuweisung: {assignment}{RESET}")
    if not car:
        logging.error(f"{LILAC}Auto mit Name {car_name} nicht gefunden für Zuweisung: {assignment}{RESET}")
        return None, None

    return loadpoint, car

def get_next_trip(car_name, usage_plan):
    car_schedule = usage_plan.get(car_name)
    if not car_schedule:
        logging.debug(f"{YELLOW}Kein Fahrplan für Auto {car_name} gefunden. Überspringe.{RESET}")
        return None

    # Annahme: Der Fahrplan ist bereits sortiert
    next_trip = car_schedule[0]
    return next_trip


def calculate_energy_gap(required_soc_final, current_soc, car, evcc_state, loadpoint_id):
    logging.debug(f"{GREEN}Calculating energy gap for required SoC {required_soc_final}% and current SoC {current_soc}%{RESET}")
    degradated_battery_capacity = calculate_car_battery_degradation(evcc_state, car, loadpoint_id)
    soc_gap = required_soc_final - current_soc
    if soc_gap < 0:
        soc_gap = 0  # No gap, car is already charged
    energy_gap_Wh = (soc_gap / 100) * degradated_battery_capacity
    logging.info(f"{GREEN}the energy gap is {energy_gap_Wh/1000:.2f} kWh before PV!{RESET}")
    return energy_gap_Wh

