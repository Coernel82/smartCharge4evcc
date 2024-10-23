import logging
import datetime

# Logging configuration with color scheme for debug information
logging.basicConfig(level=logging.DEBUG)
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"

def calculate_energy_gap(required_soc, current_soc, BATTERY_CAPACITY, DEGRADATION, BATTERY_YEAR):
    # Calculate the energy gap in Wh between the required SoC and the current SoC
    degradated_battery_capacity = BATTERY_CAPACITY * (1 - DEGRADATION) ** (datetime.datetime.now().year - BATTERY_YEAR)
    soc_gap = required_soc - current_soc
    if soc_gap < 0:
        soc_gap = 0  # No gap, car is already charged
    energy_gap = (soc_gap / 100) * degradated_battery_capacity
    logging.debug(f"{BLUE}Energy gap: {energy_gap/1000:.2f} kWh{RESET}")
    return energy_gap

# Function to calculate energy required for climate control (heating or cooling) based on external temperature and building properties
def calculate_climate_control_energy_house(
        outside_temperatures,
        remaining_hours,
        solar_forecast,
        HEATED_AREA,
        INDOOR_TEMPERATURE,
        MAXIMUM_PV,
        ENERGY_CERTIFICATE,
        SUMMER_THRESHOLD,
        BASE_LOAD
    ):
    logging.debug(f"{CYAN}Calculating climate control energy requirement for {HEATED_AREA} m² over {remaining_hours:.2f} hours{RESET}")
    average_temperature_outdoors = sum(outside_temperatures) / len(outside_temperatures)
    temperature_difference = abs(INDOOR_TEMPERATURE - average_temperature_outdoors)
    # Berechnung der maximal möglichen PV-Leistung über den Zeitraum remaining_hours
    max_pv_power = MAXIMUM_PV * remaining_hours
    # Berechnung der prognostizierten PV-Leistung über den Zeitraum (Summation der Werte in solar_forecast)
    # Da solar_forecast in 30-Minuten-Schritten vorliegt, müssen wir die Werte erst summieren und dann umrechnen
    # Faktor 0.5 da die Werte halbstündlich aufgelöst sind
    total_solar_forecast = sum(entry['pv_estimate'] for entry in solar_forecast) * 0.5
    
    # Basisberechnung der Heizenergie (ohne solare Korrektur)
    climate_energy_nominal = temperature_difference * HEATED_AREA * ENERGY_CERTIFICATE * (remaining_hours / (365 * 24))

    # Solare Quote x (Verhältnis der prognostizierten zur maximal möglichen Leistung)
    x = total_solar_forecast / max_pv_power if max_pv_power > 0 else 0
    
    # above SUMMER_THRESHOLD there is no heating but cooling.
    # Überprüfung, ob die Außentemperatur den Schwellenwert überschreitet
    if average_temperature_outdoors > SUMMER_THRESHOLD:
        # Berechnung der Kühlenergie (umgekehrter Korrekturfaktor)
        climate_energy_corrected = climate_energy_nominal * (1 + x)
        logging.info(f"{YELLOW}Korrigierte Kühlenergie (mit solarem Einfluss): {climate_energy_corrected:.2f}{RESET} kWh")
    else:
        # Differenzierte Berechnung der korrigierten Heizenergie
        # Der lineare Zusammenhang zwischen PV-Leistung und Heizenergie wird über (1 - x) berücksichtigt
        climate_energy_corrected = climate_energy_nominal * (1 - x)
        logging.info(f"{YELLOW}Korrigierte Heizenergie (mit solarem Einfluss): {climate_energy_corrected:.2f}{RESET} kWh")
        # FIXME Hier kommt 24.651.67 kW raus - das ist wohl bisschen viel ;-)


    return climate_energy_corrected

# Function to calculate solar energy available before departure
def calculate_available_solar_energy(
        solar_forecast,
        departure_time,
        energy_consumption_house,
        BASE_LOAD
    ):
    logging.debug(f"{YELLOW}Calculating solar energy available until departure at {departure_time}{RESET}")
    total_solar_energy = 0  # in Wh

    num_intervals = len(solar_forecast)

    for entry in solar_forecast:
        time = entry['time']
        # Überprüfen, ob 'time' ein String ist und nur dann konvertieren
        if isinstance(time, str):
            time = datetime.datetime.fromisoformat(time)
        if time.tzinfo is None:
            time = time.astimezone()

        # Nur Daten bis zur Abfahrtszeit berücksichtigen
        if time > departure_time:
            continue

        pv_power = entry['pv_estimate']  # PV-Leistung in W

        # Subtrahiere den Hausenergieverbrauch (Leistung)
        # Angenommen, energy_consumption_house ist in Wh für den gesamten Zeitraum
        # Wir müssen es auf Leistung pro Zeiteinheit umrechnen
        if num_intervals > 0:
            house_power = energy_consumption_house / (num_intervals * 0.5)  # Leistung in W
        else:
            house_power = 0

        net_power = pv_power - BASE_LOAD - house_power
        if net_power < 0:
            net_power = 0

        # Berechne die Energie für den Zeitraum
        # Solcast Prognosen sind in 30-Minuten-Intervallen (PT30M)
        # Daher ist die Zeitdauer 0.5 Stunden
        energy = net_power * 0.5  # Energie in Wh (Leistung * Stunden)
        total_solar_energy += energy

    logging.debug(f"{GREEN}Total available solar energy for charging: {total_solar_energy/1000:.2f} kWh{RESET}")
    return total_solar_energy