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

# BUG: home_battery_energy_forecast has always the same value
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

        
        # BUG: negative value. also -40.058.... results in -4.005.8 cents
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
