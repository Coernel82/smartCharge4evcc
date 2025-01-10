# smartCharge.py

# This project is licensed under the MIT License.

# Disclaimer: This code has been created with the help of AI (ChatGPT) and may not be suitable for
# AI-Training. This code is Alpha-Stage


    
# Important

# Good to have
# TODO: unify cache folder to /backend cache and not /cache
# TODO: Unimportant / Nice to have
# add MQTT temperature source (via external script and cache)
# add multiple sources for energy prices (Awattar, Fraunhofer)
# implement finer resolutions for the api data - finest resolution determined by the worst resolution of all data sources. solcast hobbyist minimum and maximum is 30 minutes
# add barchart into each trip with the energy compsotion (solar, grid)
# add savings information for each trip (in the index.html) compared to average price
# add pre-heating and pre-cooling using sg ready. evcc now has a virtual sg ready charger as well
# add additional (electric) heating (by timetable)






import requests
import logging
import datetime
import time
import os
import math
import utils
import solarweather
import vehicle
import home
import initialize_smartcharge
import evcc
import socGuard


current_version = "v0.0.4-alpha"
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
SOLCAST_API_URL1 = settings['EnergyAPIs']['SOLCAST_API_URL1']
SOLCAST_API_URL2 = settings['EnergyAPIs']['SOLCAST_API_URL2']
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
    logging.info(f"{GREEN}Starting the main program...{RESET}")
    current_hour_start = datetime.datetime.now().hour
    # we loop the main program till infinity
    while True:
        if settings['HolidayMode']['HOLIDAY_MODE']:
            logging.info(f"{GREEN}Holiday mode is active. Skipping all calculations.{RESET}")
            continue
        else:
            # wait till the next full hour to start the program as the electricity prices, weather, etc. change exactly to the hour
            logging.info(f"{GREEN}Waiting for the next full hour to start the program...{RESET}")

            # FIXME: change to True when testing is finished
            while False:
                logging.info(f"{GREEN}... still waiting!{RESET}")
                time.sleep(10)
                current_hour = datetime.datetime.now().hour
                if current_hour == (current_hour_start + 1) % 24:
                    current_hour_start = current_hour
                    break

            

            # Initialilzing: Getting all the data
            print(f"{GREEN}╔══════════════════════════════════════════════════╗{RESET}")
            print(f"{GREEN}║{CYAN} Starting the EV charging optimization program... {GREEN}{RESET}")
            print(f"{GREEN}╚══════════════════════════════════════════════════╝{RESET}")   

            
            cars = initialize_smartcharge.load_cars()

            # I will need this as I need more than /api/state
            evcc_base_url = initialize_smartcharge.load_settings()

            github_check_new_version = initialize_smartcharge.github_check_new_version(current_version)

            usage_plan = initialize_smartcharge.read_usage_plan()

            # API-Abrufe
            weather_forecast, sunrise, sunset = solarweather.get_weather_forecast()
            solar_forecast = solarweather.get_solar_forecast(SOLCAST_API_URL1, SOLCAST_API_URL2)
            # electricity_prices = utils.get_electricity_prices(TIBBER_API_URL, TIBBER_HEADERS)
            electricity_prices = evcc.get_electricity_prices()
            logging.debug(f"{GREY}Electricity prices: {electricity_prices}{RESET}")
            evcc_state = initialize_smartcharge.get_evcc_state()

            # Create our "smartCharge4evcc" bucket in InfluxDB if it does not exist
            initialize_smartcharge.create_influxdb_bucket()

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

            # TODO: delete this line after testing
            last_update_date = "2022-01-01" # for testing

            if last_update_date != today_date:
                utils.update_correction_factor()
                utils.update_correction_factor_nominal()
                with open(last_update_file, "w") as file:
                    file.write(today_date)
                            



            # Calculate hourly energy surplus
            hourly_energy_surplus = utils.calculate_hourly_energy_surplus(hourly_climate_energy, solar_forecast)
            
            ########################################################################################################################
            # now we can start the calculations for the cars
            ########################################################################################################################

            print(f"{GREEN}╔══════════════════════════════════════════════════╗{RESET}")
            print(f"{GREEN}║{CYAN} Apply the energy balance to each trip...         {GREEN}║{RESET}")
            print(f"{GREEN}╚══════════════════════════════════════════════════╝{RESET}")
            
            initialize_smartcharge.delete_deprecated_trips()
            usage_plan = initialize_smartcharge.get_usage_plan_from_json()
            sorted_trips = vehicle.sort_trips_by_earliest_departure_time(usage_plan)

            # which car is assigned to which loadpoint - we need to know that as the loadpoint determines the charging speed
            # here we just load the cars and loadpoints and assign later in the loop
            cars = initialize_smartcharge.load_cars()
            evcc_base_url = initialize_smartcharge.settings['EVCC']['EVCC_API_BASE_URL']

            # iterate over all trips
            for trip in sorted_trips:
                # get the car name and the loadpoint id from assignments
                car_name = trip['car_name']
                logging.info(f"\033[42m\033[93mEnergy calculation for {car_name}{RESET}")
                loadpoint_id = initialize_smartcharge.get_loadpoint_id_for_car(car_name, evcc_state)
                if loadpoint_id is None:
                    logging.error(f"{RED}No loadpoint assigned to car {car_name}. Skipping this trip.{RESET}")
                    continue
                # we have departure_datetime and return_datetime and distance in the trip
                departure_time = trip['departure_datetime']
                return_time = trip['return_datetime']
                total_distance = trip['distance']
                # match car_name to the car in cars and get the consumption and buffer_distance from cars
                car_info = next((car for car in cars.values() if car['CAR_NAME'] == car_name), None)
                consumption = car_info['CONSUMPTION']
                buffer_distance = car_info['BUFFER_DISTANCE']
                              
                # get departure_temperature and return_temperature from solarweather.get_temperatures
                temperatures = solarweather.get_temperature_for_times(weather_forecast, departure_time, return_time)
                if temperatures is None:
                    logging.error(f"{RED}Temperature data is missing for the trip of {car_name}. Skipping this trip.{RESET}")
                    continue
                departure_temperature, return_temperature, outside_temperatures_till_departure = temperatures

                # calculate the energy requirements for the car
                ev_energy_for_trip = vehicle.calculate_ev_energy_consumption(departure_temperature, return_temperature, total_distance, consumption, buffer_distance, car_name, evcc_state, loadpoint_id)
                current_soc = vehicle.get_evcc_soc(loadpoint_id, evcc_state) # yes, SoC is under loadpoint_id in evcc
            
                # here we calculate the final required SoC and the energy gap
                trip_name = trip['description']
                required_soc_final = current_soc + vehicle.calculate_required_soc_topup(ev_energy_for_trip, car_name, evcc_state, loadpoint_id, trip_name)
                ev_energy_gap_Wh = vehicle.calculate_energy_gap(required_soc_final, current_soc, car_name, evcc_state, loadpoint_id)
                
                # remaining hours till departure to find best charging window                
                remaining_hours = utils.calculate_remaining_hours(departure_time)

                # from here we take care of the loading process

                
                # how much regenerative energy can we use? (we do not need usable_energy for now)
                regenerative_energy_surplus, usable_energy = utils.get_usable_charging_energy_surplus(usable_energy, departure_time, ev_energy_gap_Wh, evcc_state, car_name, load_car=True)
                logging.debug(f"{GREY}Regenerativer Energieüberschuss der genutzt werden KANN: {regenerative_energy_surplus/1000:.2f} kWh{RESET}")
                
                # Update ev_energy_gap_Wh: till departure we can use regenerative_energy_surplus
                logging.debug(f"{GREY}regenerative_energy_surplus: {regenerative_energy_surplus}{RESET}")
                logging.debug(f"{GREY}ev_energy_gap_Wh: {ev_energy_gap_Wh}{RESET}")
                ev_energy_gap_Wh -= regenerative_energy_surplus
                if ev_energy_gap_Wh < 0:
                    ev_energy_gap_Wh = 0
                logging.debug(f"{GREY}ev_energy_gap_Wh nach Abzug des regenerativen Energieüberschusses: {ev_energy_gap_Wh/1000:.2f} kWh{RESET}")
                logging.debug(f"{GREY}Energiebedarf für {car_name} nach regenerativer Energie: {ev_energy_gap_Wh:.2f} kWh{RESET}")
                # this required energy to be topped up with grid energy in Wh
                # so using vehicle.calculate_required_soc again is correct
                required_soc_grid_topup = vehicle.calculate_required_soc_topup(ev_energy_gap_Wh, car_name, evcc_state, loadpoint_id, trip_name)
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
            # Calculations for the heat pump
            print(f"{GREEN}╔══════════════════════════════════════════════════╗{RESET}")
            print(f"{GREEN}║{CYAN} Now we optimize the heating...                   {GREEN}║{RESET}")
            print(f"{GREEN}╚══════════════════════════════════════════════════╝{RESET}")
            season = utils.get_season()
            if season == "summer" or season == "interim":
                logging.info(f"{GREEN}It is summer or interim season. Skipping the heating optimization.{RESET}")
                # it can happen that from one round of the program the season changes and SG Ready is still on. So we have to switch it to pv mode
                home.switch_heatpump_to_mode(heatpump_id, "pv")
            else:
                # Calculate different time parameters
                price_limit_blocking = utils.calculate_price_limit_blocktime(weather_forecast, electricity_prices, settings)
                price_limit_boostmode = utils.calculate_price_limit_boostmode(settings, hourly_climate_energy, electricity_prices)
                
                # get basic parameters for the heating and blocking logic
                heatpump_id = utils.get_heatpump_id(settings)
                
                # Decision: force heating / normal mode / blocking mode
                # price limit for boostig can be set via evcc api
                post_url = f"{evcc_base_url}/api/loadpoints/{heatpump_id}/smartcostlimit/{price_limit_boostmode}"
                response = requests.post(post_url)
                if response.status_code == 200:
                    logging.info(f"{GREEN}Successfully set smart cost limit for heat pump.{RESET}")
                else:
                    logging.error(f"{RED}Failed to set smart cost limit for heat pump. Status code: {response.status_code}{RESET}")

                # in between blocking and boost is the normal mode - nothing to do here
                # the heatpump will opearte in default mode

                # blocking is more tricky - when the current price is in the blocking range --> block
                # TODO:[medium prio] Think about logic. Is made sure that blocking is only for x hours in y hours?
                if utils.get_current_electricity_price(electricity_prices) >= price_limit_blocking:
                    home.switch_heatpump_to_mode(heatpump_id, "off")
                else:
                    # switch heat pump to pv mode to enable normal operation
                    home.switch_heatpump_to_mode(heatpump_id, "pv")
          
                


        ########################################################################################################################
            # Calculations for the house batteries
            print(f"{GREEN}╔══════════════════════════════════════════════════╗{RESET}")
            print(f"{GREEN}║{CYAN} Now we optimize the home battery...              {GREEN}║{RESET}")
            print(f"{GREEN}╚══════════════════════════════════════════════════╝{RESET}")
            logging.info(f"{GREEN}Calculations for home batteries{RESET}")
            home_battery_json_data = initialize_smartcharge.get_home_battery_data_from_json()
            
        
            home_battery_api_data = initialize_smartcharge.get_home_battery_data_from_api(evcc_state)
            if home_battery_json_data is None or home_battery_api_data == [{'battery_id': 0, 'battery_soc': 0, 'battery_capacity': 0}]:
                logging.error(f"{RED}Home battery data could not be loaded. Skipping the home battery optimization.{RESET}")
                potential_home_battery_energy_forecast, grid_feedin, required_charge, charging_plan, future_grid_feedin = None, None, None, None, None
            else:
                battery_data = home.process_battery_data(home_battery_json_data, home_battery_api_data)    
                home_batteries_capacity = home.get_home_batteries_capacities(evcc_state) # this is the total usable capacity of all batteries (info by evcc api)
                home_batteries_SoC = home.get_home_battery_soc() # we refresh it every 4 minutes, so evcc_state is not suitable as it is static
                remaining_home_battery_capacity = home.calculate_remaining_home_battery_capacity(home_batteries_capacity, home_batteries_SoC)
                
                

                # this is the additional cost due to wear of battery and inverter 
                home_battery_charging_cost_per_kWh = home.get_home_battery_charging_cost_per_Wh(battery_data) * 1000
                
                purchase_threshold = home_battery_charging_cost_per_kWh
                home_battery_efficiency = home.calculate_average_battery_efficiency(battery_data)
                
                # Here we forcast the energy of the home battery in hourly increments
                home_battery_energy_forecast, grid_feedin, required_charge = home.calculate_homebattery_soc_forcast_in_Wh(home_batteries_capacity, remaining_home_battery_capacity, usable_energy, hourly_climate_energy, home_battery_efficiency)

                
                # the real charging plan is done by evcc - we just set the price
                charging_plan = home.calculate_charging_plan(home_battery_energy_forecast, electricity_prices, purchase_threshold, battery_data, required_charge, evcc_state)
                maximum_acceptable_price = charging_plan
                evcc.set_upper_price_limit(maximum_acceptable_price)
                
                
                # first thought: we do not need to lock the battery when using grid energy is cheaper than battery energy as the battery
                # will be locked indirectly by the minimum price - yes but there is a price gap in between:
                # to expensive to charge but to cheap to use it - so we have to lock the battery
                # get fake loadpoint id from settings

                
                # here we handley the battery lock to minimize the grid feedin                                
                home.minimize_future_grid_feedin(settings, electricity_prices, usable_energy, home_battery_energy_forecast, evcc_state, maximum_acceptable_price, purchase_threshold)

            # we guard the soc of the home battery every 4 minutes. If the current minute is 0, we exit the loop to run the main program
            # error handling in case there is no battery
            if 'home_battery_energy_forecast' not in locals() or 'grid_feedin' not in locals() or 'required_charge' not in locals() or 'home_battery_charging_cost_per_kWh' not in locals():
                home_battery_energy_forecast, grid_feedin, required_charge, home_battery_charging_cost_per_kWh = [], [], [], 0
    
            # even without guard we "guard" to slow down the program
            socGuard.initiate_guarding(GREEN, RESET, settings, home_battery_energy_forecast, home_battery_charging_cost_per_kWh)
                
            # data for the WebUI
            utils.json_dump_all_time_series_data(weather_forecast, hourly_climate_energy, hourly_energy_surplus, electricity_prices, home_battery_energy_forecast, grid_feedin, required_charge, charging_plan, usable_energy, solar_forecast, future_grid_feedin)
            logging.info(f"{GREEN}EV charging optimization program completed.{RESET}")
