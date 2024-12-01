# smartCharge.py

# This project is licensed under the MIT License.

# Disclaimer: This code has been created with the help of AI (ChatGPT) and may not be suitable for
# AI-Training. This code ist Alpha-Stage




# TODO: for days without (<=2% of maximum possible yield) sunshine is it possible to compare calculated and real heating energy and apply another correction factor
# TODO: optional: add MQTT temperature source (via external script and cache)
# TODO. add multiple sources for energy prices (Awattar, Fraunhofer)
# TODO: remove function and assignment json
# TODO: calculate degradation from mileage and not from age: Result --> loadpoint -> id --> vehicleOdometer
# FIXME: settings.json has Home and House
# TODO: find {EVCC_API_BASE_URL}/api/state and replace it with evcc_state
# TODO: error catching: no heatpump
# TODO: error catching: no solar panels
# TODO: error catching: no battery
# TODO: add pre-heating and pre-cooling
# TODO: add additional (electric) heating (by timetable)
# TODO: implement finer resolutions for the api data - finest resolution determined by the worst resolution of all data sources

import requests
import logging
import datetime
import os
import math
import utils
import solarweather
import vehicle
import home
import initialize_smartcharge
import evcc


current_version = "v0.0.1-alpha"
# Logging configuration with color scheme for debug information
# DEBUG, INFO, WARNING, ERROR, CRITICAL
logging.basicConfig(level=logging.DEBUG)
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
GREY = "\033[37m"

settings = initialize_smartcharge.load_settings()

# Zugriff auf die Einstellungen
# User-Config
# OneCall API 3.0 von OpenWeather
API_KEY = settings['OneCallAPI']['API_KEY']
LATITUDE = settings['OneCallAPI']['LATITUDE']
LONGITUDE = settings['OneCallAPI']['LONGITUDE']

# Energy: SOLCAST und TIBBER API-URLs und Header
SOLCAST_API_URL = settings['EnergyAPIs']['SOLCAST_API_URL']
TIBBER_API_URL = settings['EnergyAPIs']['TIBBER_API_URL']
TIBBER_HEADERS = settings['EnergyAPIs']['TIBBER_HEADERS']

# InfluxDB
INFLUX_BASE_URL = settings['InfluxDB']['INFLUX_BASE_URL']
INFLUX_ORGANIZATION = settings['InfluxDB']['INFLUX_ORGANIZATION']
INFLUX_BUCKET = settings['InfluxDB']['INFLUX_BUCKET']
INFLUX_ACCESS_TOKEN = settings['InfluxDB']['INFLUX_ACCESS_TOKEN']
TIMESPAN_WEEKS = settings['InfluxDB']['TIMESPAN_WEEKS']


# Hauptprogramm
if __name__ == "__main__":

    # Initialilzing: Getting all the data
    print(f"{GREEN}╔══════════════════════════════════════════════════╗{RESET}")
    print(f"{GREEN}║{CYAN} Starting the EV charging optimization program... {GREEN}║{RESET}")
    print(f"{GREEN}╚══════════════════════════════════════════════════╝{RESET}")   

    loadpoints =initialize_smartcharge.load_loadpoints()
    cars = initialize_smartcharge.load_cars()
    assignments = initialize_smartcharge.load_assignments()

    # I will need this as I need more than /api/state
    evcc_base_url = initialize_smartcharge.load_settings()

    github_check_new_version = initialize_smartcharge.github_check_new_version(current_version)

    usage_plan = initialize_smartcharge.read_usage_plan()

    # API-Abrufe
    weather_forecast, sunrise, sunset = solarweather.get_weather_forecast()
    solar_forecast = solarweather.get_solar_forecast(SOLCAST_API_URL)
    electricity_prices = utils.get_electricity_prices(TIBBER_API_URL, TIBBER_HEADERS)
    
    evcc_state = initialize_smartcharge.get_evcc_state()


    logging.info("Alle Daten wurden erfolgreich geladen.")
    ########################################################################################################################

    #Before we start the calculations for the cars we need to know the available energy
    
    # Energy-Balance: Incoming Energy
    # --> we have solar_forecast
    print(f"{GREEN}╔══════════════════════════════════════════════════╗{RESET}")
    print(f"{GREEN}║{CYAN} Calculate the energy balance...                  {GREEN}║{RESET}")
    print(f"{GREEN}╚══════════════════════════════════════════════════╝{RESET}")


    usable_energy = solar_forecast

    # Energy-Balance: Outgoing Energy
    hourly_climate_energy = home.calculate_hourly_house_energy_consumption(solar_forecast, weather_forecast)
    # Write the corrected energy consumption to InfluxDB
    utils.write_corrected_energy_consumption(hourly_climate_energy)
    

    # the correction factor is used to correct the energy consumption of the house
    # however, it is an estimate at the beginning - so we update it bit by bit
    # within time the correction factor will be more accurate
    
    # Check if the correction factor was updated today
    cache_folder = "cache"
    os.makedirs(cache_folder, exist_ok=True)
    last_update_file = os.path.join(cache_folder, "last_correction_update.txt")
    today_date = datetime.date.today().isoformat()

    if os.path.exists(last_update_file):
        with open(last_update_file, "r") as file:
            last_update_date = file.read().strip()
    else:
        last_update_date = ""

    if last_update_date != today_date:
        # Update the correction factor and save the current date
        utils.update_correction_factor()
        with open(last_update_file, "w") as file:
            file.write(today_date)
                        



    # Calculate hourly energy surplus
    hourly_energy_surplus = utils.calculate_hourly_energy_surplus(hourly_climate_energy, solar_forecast)
    
    ########################################################################################################################
    # now we can start the calculations for the cars
    print(f"{GREEN}╔══════════════════════════════════════════════════╗{RESET}")
    print(f"{GREEN}║{CYAN} Apply the energy balance to each trip...         {GREEN}║{RESET}")
    print(f"{GREEN}╚══════════════════════════════════════════════════╝{RESET}")
    
    initialize_smartcharge.delete_deprecated_trips()
    usage_plan = initialize_smartcharge.get_usage_plan_from_json()
    sorted_trips = vehicle.sort_trips_by_earliest_departure_time(usage_plan)

    # which car is assigned to which loadpoint - we need to know that as the loadpoint determines the charging speed
    # here we just load the cars and loadpoints and assign later in the loop
    assignments = initialize_smartcharge.load_assignments()
    cars = initialize_smartcharge.load_cars()
    evcc_base_url = initialize_smartcharge.settings['EVCC']['EVCC_API_BASE_URL']

    # iterate over all trips
    for trip in sorted_trips:
        # get the car name and the loadpoint id from assignments
        car_name = trip['car_name']
        logging.info(f"\033[42m\033[93mEnergy calculation for {car_name}{RESET}")
        loadpoint_id = initialize_smartcharge.get_loadpoint_id_for_car(car_name)
        if loadpoint_id is None:
            logging.error(f"{RED}No loadpoint assigned to car {car_name}. Skipping this trip.{RESET}")
            continue
        # we have departure_datetime and return_datetime and distance in the trip
        departure_time = trip['departure_datetime']
        return_time = trip['return_datetime']
        total_distance = trip['distance']
        # match car_name to the car in cars and get the consumption and buffer_distance from cars
        car_info = next((car for car in cars if car['CAR_NAME'] == car_name), None)
        consumption = car_info['CONSUMPTION']
        buffer_distance = car_info['BUFFER_DISTANCE']
        
        # TODO: delete. redundant?
        """  # we need weather data till the return time of the earliest car - otherwise we can stop the whole loop
        if not solarweather.weather_data_available_for_next_trip(weather_forecast, return_time):
            logging.error(f"{RED}Für alle Fahrten: Keine Wetterdaten verfügbar.{RESET}")
            break # cancel the whole loop
        else: """

        
        # get departure_temperature and return_temperature from solarweather.get_temperatures
        temperatures = solarweather.get_temperature_for_times(weather_forecast, departure_time, return_time)
        if temperatures is None:
            logging.error(f"{RED}Temperature data is missing for the trip of {car_name}. Skipping this trip.{RESET}")
            continue
        departure_temperature, return_temperature, outside_temperatures_till_departure = temperatures

        # calculate the energy requirements for the car
        ev_energy_for_trip = vehicle.calculate_ev_energy_consumption(departure_temperature, return_temperature, total_distance, consumption, buffer_distance, car_name, evcc_state)
        current_soc = vehicle.get_evcc_soc(loadpoint_id) # yes, SoC is under loadpoint_id in evcc
    
        # here we calculate the final required SoC and the energy gap
        required_soc_final = vehicle.calculate_required_soc(ev_energy_for_trip, car_name, evcc_state)
        ev_energy_gap = vehicle.calculate_energy_gap(required_soc_final, current_soc, car_name)
        
        # remaining hours till departure to find best charging window                
        remaining_hours = utils.calculate_remaining_hours(departure_time)

        # from here we take care of the loading process

        # load the technical data of the loadpoints (charging speed!)
        loadpoints = initialize_smartcharge.load_loadpoints()
        # we know the loadpoint_id from the assignments - so we can get the loadpoint which the car is connected to
        loadpoint = next((loadpoint for loadpoint in loadpoints if loadpoint['LOADPOINT_ID'] == loadpoint_id), None)

        
        # howe much regenerative energy can we use? (we do not need usable_energy for now)
        regenerative_energy_surplus, usable_energy = utils.get_usable_charging_energy_surplus(usable_energy, departure_time, ev_energy_gap, load_car=True)
        logging.debug(f"{GREY}Regenerativer Energieüberschuss der genutzt werden KANN: {regenerative_energy_surplus/1000:.2f} kWh{RESET}")
        
        # Update ev_energy_gap: till departure we can use regenerative_energy_surplus
        logging.debug(f"{GREY}regenerative_energy_surplus: {regenerative_energy_surplus}{RESET}")
        logging.debug(f"{GREY}ev_energy_gap: {ev_energy_gap}{RESET}")
        ev_energy_gap -= regenerative_energy_surplus
        if ev_energy_gap < 0:
            ev_energy_gap = 0
        logging.debug(f"{GREY}ev_energy_gap nach Abzug des regenerativen Energieüberschusses: {ev_energy_gap:.2f} kWh{RESET}")
        logging.debug(f"{GREY}Energiebedarf für {car_name} nach regenerativer Energie: {ev_energy_gap:.2f} kWh{RESET}")
        # this required energy to be topped up with grid energy in Wh
        # so using vehicle.calculate_required_soc again is correct
        required_soc_grid_topup = vehicle.calculate_required_soc(ev_energy_gap, car_name, evcc_state)
        logging.info(f"{GREEN}Required SoC with addon from grid: {required_soc_grid_topup:.2f}%{RESET}")
        
        # required_soc_initial = required_soc_final -  required_soc_grid_topup
        logging.info(f"{GREEN}Required SoC to start charging: required trip soc excluding solar energy)): {required_soc_grid_topup:.2f}%{RESET}")

        # round it up as the api does not accept decimal places
        required_soc_grid_topup = math.ceil(required_soc_grid_topup)

        # using evcc's internal API to set the required SoC
        post_url = f"{evcc_base_url}/api/vehicles/{car_name}/plan/soc/{required_soc_grid_topup}/{departure_time.isoformat()}Z"
        logging.debug(f"{GREY}Post URL: {post_url}{RESET}")
        response = requests.post(post_url)
        if response.status_code == 200:
            logging.info(f"{GREEN}Successfully posted required SoC for {car_name} to the API.{RESET}")
        else:
            logging.error(f"{RED}Failed to post required SoC for {car_name} to the API. Status code: {response.status_code}{RESET}")
            logging.error(f"{RED}the url called was: {post_url}{RESET}")
            logging.error(f"{RED}This is most likely because you do not own this car or have assigned a different name for instance opel instead of Opel{RESET}")
            logging.error(f"{RED}The name here must be the same as in evcc!{RESET}")

########################################################################################################################

    # Calculations for the house batteries
    print(f"{GREEN}╔══════════════════════════════════════════════════╗{RESET}")
    print(f"{GREEN}║{CYAN} Now we optimize the home battery...              {GREEN}║{RESET}")
    print(f"{GREEN}╚══════════════════════════════════════════════════╝{RESET}")
    logging.info(f"{GREEN}Calculations for home batteries{RESET}")
    home_battery_json_data = initialize_smartcharge.get_home_battery_data_from_json()
    home_battery_api_data = initialize_smartcharge.get_home_battery_data_from_api()

    battery_data = home.process_battery_data(home_battery_json_data, home_battery_api_data)    
    home_batteries_capacity = home.get_home_batteries_capacities()
    home_batteries_SoC = home.get_home_battery_soc()
    remaining_home_battery_capacity = home.calculate_remaining_home_battery_capacity(home_batteries_capacity, home_batteries_SoC)
    

    # this is the additional cost due to wear of battery and inverter 
    home_battery_charging_cost_per_kWh = home.get_home_battery_charging_cost_per_Wh(battery_data) * 1000
    current_electricity_price_per_kWh = home.get_current_price(electricity_prices)
    purchase_threshold = home_battery_charging_cost_per_kWh
    home_battery_efficiency = home.calculate_average_battery_efficiency(battery_data)
    home_battery_energy_forecast, grid_feedin, required_charge = home.calculate_homebattery_soc_forcast_in_Wh(home_batteries_capacity, remaining_home_battery_capacity, usable_energy, hourly_climate_energy, home_battery_efficiency)
    # the real charging plan is done by evcc - we just set the price
    charging_plan = home.calculate_charging_plan(home_battery_energy_forecast, electricity_prices, purchase_threshold, battery_data, required_charge)
    maximum_acceptable_price = charging_plan
    evcc.set_upper_price_limit(maximum_acceptable_price)
    # we do not need to lock the battery when using grid energy is cheaper than battery energy as the battery
    # will be locked indirectly by the minimum price
    # Think about the case: summer, battery is full, grid is cheap: use battery anyways! No problem:
    # as the battery is full there is no charging plan anyways
    logging.info(f"{GREEN}EV charging optimization program completed.{RESET}")
