import os
import json
import requests
import logging
import home
import datetime

# Farbige Konsole
class ColorFormatter(logging.Formatter):
    GREEN = '\033[92m'
    RED = '\033[91m'
    RESET = '\033[0m'

    def format(self, record):
        if record.levelno == logging.INFO:
            record.msg = f"{self.GREEN}{record.msg}{self.RESET}"
        elif record.levelno == logging.ERROR:
            record.msg = f"{self.RED}{record.msg}{self.RESET}"
        return super().format(record)

# Logger konfigurieren
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = ColorFormatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# BUG: [from 2025-01-10 high prio] home_battery_energy_forecast has always the same value
def guard_home_battery_soc(settings, home_battery_energy_forecast, chargingCosts):
    EVCC_API_BASE_URL = settings['EVCC']['EVCC_API_BASE_URL']
    
    # get maximum_soc_allowed from list home_battery_energy_forecast
    # it always is index 0 as we need it for the current hour
    maximum_soc_allowed = home_battery_energy_forecast[0]['energy']
    
    # get current SoC from home battery - as we need it every 4 minutes it really comes from the api and not from evcc_state
    currentSoC = home.get_home_battery_soc()

    # feedin abrufen
    try:
        response = requests.get(f"{EVCC_API_BASE_URL}/api/tariff/feedin")
        response.raise_for_status()
        feedin_data = response.json()
        now = datetime.datetime.now()
        feedin = 0.0
        for rate in feedin_data['result']['rates']:
            start = datetime.datetime.fromisoformat(rate['start']).replace(tzinfo=None)
            end = datetime.datetime.fromisoformat(rate['end']).replace(tzinfo=None)
            if start <= now < end:
                feedin = rate['price']
                break
    except Exception as e:
        logger.error(f"Fehler beim Abrufen von feedin: {e}")
        return

    # Vergleichen und Aktion durchführen
    if currentSoC >= maximum_soc_allowed:
        cost = feedin - chargingCosts

        
        # TODO: negative value. also -40.058.... results in -4.005.8 cents
        # could be correct as there can be negative energy costs
        # Guarding home battery charge
        # Still guarding!
        # Retrieving home battery SoC from http://192.168.178.28:7070/api/state
        # Current home battery SoC: 51%
        # POST zu /api/batterygridchargelimit/-40.05805630386612 erfolgreich.
        # Serverantwort: {"result":-40.05805630386612}



        # POST Request ausführen
        try:
            response = requests.post(f"{EVCC_API_BASE_URL}/api/batterygridchargelimit/{cost}")
            response.raise_for_status()
            logger.info(f"POST zu /api/batterygridchargelimit/{cost} erfolgreich.")
            logger.info(f"Serverantwort: {response.text}")
        except Exception as e:
            logger.error(f"Fehler beim POST Request: {e}")
            return
    else:
        logger.info("currentSoC ist kleiner als maximum_soc_allowed. Keine Aktion erforderlich.")

def initiate_guarding(GREEN, RESET, settings, home_battery_energy_forecast, home_battery_charging_cost_per_kWh):
    # Guarde the home battery every 4 minutes and break the loop just before the full hour
    import time
    end_time = datetime.datetime.now() + datetime.timedelta(minutes=4)
    while datetime.datetime.now() < end_time:
        logging.info(f"{GREEN}Guarding home battery charge / slowing down the program (when there is no home battery){RESET}")
        current_time = datetime.datetime.now()
        # Calculate the remaining time until the next full hour
        seconds_until_full_hour = (60 - current_time.minute) * 60 - current_time.second
        if seconds_until_full_hour <= 0:
            # If it's already past the full hour, break the loop
            break

        while seconds_until_full_hour > 0:
            sleep_duration = min(60, seconds_until_full_hour)
            time.sleep(sleep_duration)
            logging.info(f"{GREEN}Still guarding!{RESET}")
            seconds_until_full_hour -= sleep_duration
            if seconds_until_full_hour <= 4 * 60:
                break
        guard_home_battery_soc(settings, home_battery_energy_forecast, home_battery_charging_cost_per_kWh)