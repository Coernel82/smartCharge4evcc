import requests
import logging
import datetime
import json
import os
import math
import utils # alle von mir geschriebenen Hilfsfunktionen
import solarweather
import vehicle

# -------------------------------------#
# stop editing - developer zone only   #
# -------------------------------------#

# Logging configuration with color scheme for debug information
logging.basicConfig(level=logging.DEBUG)
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"

# Lade die Einstellungen aus der settings.json-Datei
def load_settings():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    settings_file = os.path.join(script_dir, 'settings.json')
    with open(settings_file, 'r') as f:
        settings = json.load(f)
    return settings

settings = load_settings()

# Zugriff auf die Einstellungen
# User-Config
# OneCall API 3.0 von OpenWeather
API_KEY = settings['OneCallAPI']['API_KEY']
LATITUDE = settings['OneCallAPI']['LATITUDE']
LONGITUDE = settings['OneCallAPI']['LONGITUDE']

# Loadmanagement
LOADMANAGEMENT = settings['Loadmanagement']['LOADMANAGEMENT']
EVCC_API_BASE_URL = settings['EVCC']['EVCC_API_BASE_URL']

# House
ENERGY_CERTIFICATE = settings['House']['ENERGY_CERTIFICATE']
HEATED_AREA = settings['House']['HEATED_AREA']
INDOOR_TEMPERATURE = settings['House']['INDOOR_TEMPERATURE']
BASE_LOAD = settings['House']['BASE_LOAD']
MAXIMUM_PV = settings['House']['MAXIMUM_PV']
SUMMER_THRESHOLD = settings['House']['SUMMER_THRESHOLD']

# Energy: SOLCAST und TIBBER API-URLs und Header
SOLCAST_API_URL = settings['EnergyAPIs']['SOLCAST_API_URL']
TIBBER_API_URL = settings['EnergyAPIs']['TIBBER_API_URL']
TIBBER_HEADERS = settings['EnergyAPIs']['TIBBER_HEADERS']

# Load EVCC base url
def load_evcc(settings):
    """
    Lädt die EVCC-spezifischen Einstellungen aus den Settings und gibt sie zurück.
    """
    try:
        evcc_settings = settings['EVCC']
        evcc_base_url = evcc_settings.get('EVCC_API_BASE_URL')
        if not evcc_base_url:
            raise KeyError("EVCC_API_BASE_URL nicht in den Settings gefunden.")
        return evcc_base_url
    except KeyError as e:
        logging.error(f"{RED}Fehler beim Laden der EVCC-Einstellungen: {e}{RESET}")
        exit(1)



# Funktionen zum Einlesen der Ladepunkte und Autos
def load_loadpoints():
    return settings['Loadpoints']

def load_cars():
    return settings['Cars']

# Funktion zum Einlesen der Zuordnung von Autos zu Ladepunkten
def load_assignments():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    assignments_file = os.path.join(script_dir, 'loadpoint_assignments.json')
    with open(assignments_file, 'r') as f:
        assignments_data = json.load(f)
    return assignments_data['assignments']

# Funktion zum Einlesen des Fahrplans
def read_usage_plan():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, 'usage_plan.json')

    logging.debug(f"Lese den Fahrplan aus der JSON-Datei: {file_path}")
    usage_plan = {}

    # Überprüfen, ob die Datei existiert
    if not os.path.exists(file_path):
        logging.error(f"Fahrplan-Datei nicht gefunden: {file_path}")
        return usage_plan

    # Öffnen und Lesen der JSON-Datei
    with open(file_path, 'r') as f:
        data = json.load(f)

    # Aktuelles Datum und Zeit für Berechnungen
    now = datetime.datetime.now()

    updated_data = {}

    # Verarbeitung für jedes Auto
    for car_name, car_schedule in data.items():
        updated_data[car_name] = {"recurring": [], "non_recurring": []}
        usage_plan[car_name] = []

        # Verarbeitung der wiederkehrenden Fahrten
        recurring_trips = car_schedule.get('recurring', [])
        for entry in recurring_trips:
            original_entry = entry.copy()
            departure_str = entry.get('departure')
            departure_time_str = entry.get('departure_time')
            total_distance = entry.get('distance')
            return_str = entry.get('return')
            return_time_str = entry.get('return_time')

            # Validierung der Daten (weniger streng)
            if not all([departure_str, departure_time_str, total_distance, return_str, return_time_str]):
                logging.error(f"{RED}Ungültiger Eintrag in wiederkehrenden Fahrten für {car_name}: {entry}{RESET}")
                continue

            try:
                departure_weekday_number = parse_weekday(departure_str)
                return_weekday_number = parse_weekday(return_str)

                if departure_weekday_number is None or return_weekday_number is None:
                    logging.error(f"{RED}Ungültiger Wochentag im Fahrplan für {car_name}: {departure_str} oder {return_str}{RESET}")
                    continue

                departure_time = datetime.datetime.strptime(departure_time_str, '%H:%M').time()
                return_time = datetime.datetime.strptime(return_time_str, '%H:%M').time()
                total_distance = float(total_distance)

                # Berechnung des nächsten Abfahrtsdatums
                days_until_departure = (departure_weekday_number - now.weekday() + 7) % 7
                if days_until_departure == 0 and departure_time < now.time():
                    days_until_departure = 7  # Verschieben auf nächste Woche

                departure_date = now.date() + datetime.timedelta(days=days_until_departure)
                departure_datetime = datetime.datetime.combine(departure_date, departure_time)

                # Berechnung des Rückkehrdatums
                days_until_return = (return_weekday_number - departure_weekday_number + 7) % 7
                return_date = departure_date + datetime.timedelta(days=days_until_return)
                return_datetime = datetime.datetime.combine(return_date, return_time)

                if return_datetime < departure_datetime:
                    return_datetime += datetime.timedelta(days=7)

                # Hinzufügen des Eintrags zum Fahrplan
                trip = {
                    'departure_datetime': departure_datetime,
                    'return_datetime': return_datetime,
                    'total_distance': total_distance,
                    'original_entry': original_entry
                }

                usage_plan[car_name].append(trip)
                updated_data[car_name]['recurring'].append(original_entry)

            except Exception as e:
                logging.error(f"{RED}Fehler beim Verarbeiten einer wiederkehrenden Fahrt für {car_name}: {e}{RESET}")
                continue

        # Verarbeitung der einmaligen Fahrten
        non_recurring_trips = car_schedule.get('non_recurring', [])
        for entry in non_recurring_trips:
            original_entry = entry.copy()
            departure_date_str = entry.get('departure_date')
            departure_time_str = entry.get('departure_time')
            total_distance = entry.get('distance')
            return_date_str = entry.get('return_date')
            return_time_str = entry.get('return_time')

            # Validierung der Daten (weniger streng)
            if not all([departure_date_str, departure_time_str, total_distance, return_date_str, return_time_str]):
                logging.error(f"{RED}Ungültiger Eintrag in einmaligen Fahrten für {car_name}: {entry}{RESET}")
                continue

            try:
                departure_date = datetime.datetime.strptime(departure_date_str, '%Y-%m-%d').date()
                departure_time = datetime.datetime.strptime(departure_time_str, '%H:%M').time()
                return_date = datetime.datetime.strptime(return_date_str, '%Y-%m-%d').date()
                return_time = datetime.datetime.strptime(return_time_str, '%H:%M').time()
                total_distance = float(total_distance)

                departure_datetime = datetime.datetime.combine(departure_date, departure_time)
                return_datetime = datetime.datetime.combine(return_date, return_time)

                # Überprüfen, ob die Fahrt bereits abgeschlossen ist
                if departure_datetime < now:
                    logging.info(f"{YELLOW}Einmalige Fahrt für {car_name} abgeschlossen und wird entfernt: {entry}{RESET}")
                    continue  # Überspringe diesen Eintrag

                # Hinzufügen des Eintrags zum Fahrplan
                trip = {
                    'departure_datetime': departure_datetime,
                    'return_datetime': return_datetime,
                    'total_distance': total_distance,
                    'original_entry': original_entry
                }

                usage_plan[car_name].append(trip)
                updated_data[car_name]['non_recurring'].append(original_entry)

            except Exception as e:
                logging.error(f"{RED}Fehler beim Verarbeiten einer einmaligen Fahrt für {car_name}: {e}{RESET}")
                continue

        # Sortieren des Fahrplans nach Abfahrtszeit für jedes Auto
        usage_plan[car_name].sort(key=lambda x: x['departure_datetime'])

    # Aktualisiere die usage_plan.json mit den verbleibenden Fahrten
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, 'usage_plan.json')
    with open(file_path, 'w') as f:
        json.dump(updated_data, f, indent=4)

    return usage_plan

# Function to retrieve weather forecast (temperature) for the next 24 hours from a weather API (cached every 6 hours)
def get_weather_forecast(api_key, lat, lon):
    cache_file = "weather_forecast_cache.json"
    current_time = datetime.datetime.now()

    # Überprüfen, ob der Cache existiert und noch gültig ist (innerhalb von 6 Stunden)
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            cached_data = json.load(f)
            cache_time = datetime.datetime.fromisoformat(cached_data["timestamp"])
            if (current_time - cache_time).total_seconds() < 6 * 3600:
                logging.debug(f"{CYAN}Verwende zwischengespeicherte Wetterdaten vom {cache_time}{RESET}")
                forecast = cached_data["forecast"]
                # Konvertiere Zeitstempel zurück zu datetime-Objekten
                for entry in forecast:
                    if isinstance(entry['dt'], str):
                        entry['dt'] = datetime.datetime.fromisoformat(entry['dt'])
                return forecast

    logging.debug(f"{CYAN}Abrufen der Wettervorhersage von OpenWeatherMap{RESET}")
    # Abrufen der Wettervorhersage
    exclude = 'current,minutely,daily,alerts'
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude={exclude}&appid={api_key}&units=metric"
    try:
        response = requests.get(url)
        response.raise_for_status()
        weather_data = response.json()
        # Extrahiere Zeitzonen-Offset
        timezone_offset = weather_data.get('timezone_offset', 0)
        # Extrahieren der stündlichen Temperaturen
        hourly_forecast = weather_data.get('hourly', [])
        forecast = []
        for hour_data in hourly_forecast:
            # Konvertieren des Unix-Zeitstempels in datetime mit Zeitzoneninformation
            utc_dt = datetime.datetime.fromtimestamp(hour_data['dt'], tz=datetime.timezone.utc)
            # Anwenden des Zeitzonen-Offsets
            local_dt = utc_dt + datetime.timedelta(seconds=timezone_offset)
            local_dt = local_dt.astimezone()  # Stelle sicher, dass local_dt Zeitzoneninformation hat
            temp = hour_data['temp']
            forecast.append({'dt': local_dt, 'temp': temp})
        # Speichern der neuen Daten im Cache
        with open(cache_file, "w") as f:
            # Zeitstempel in Strings konvertieren
            for entry in forecast:
                entry['dt'] = entry['dt'].isoformat()
            json.dump({"timestamp": current_time.isoformat(), "forecast": forecast}, f)
        return forecast
    except requests.RequestException as e:
        logging.error(f"{RED}Fehler beim Abrufen der Wetterdaten: {e}{RESET}")
        # Wenn zwischengespeicherte Daten vorhanden sind, verwenden wir diese
        if os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                cached_data = json.load(f)
                logging.debug(f"{CYAN}Verwende zwischengespeicherte Wetterdaten{RESET}")
                return cached_data["forecast"]
        else:
            # Keine Daten verfügbar
            return None


def get_temperature_for_times(weather_forecast, departure_time, return_time):
    logging.debug(f"{GREEN}Retrieving temperatures for departure time {departure_time} and return time {return_time}{RESET}")
    current_time = datetime.datetime.now().astimezone()

    # Ensure departure_time and return_time are offset-aware
    if departure_time.tzinfo is None:
        departure_time = departure_time.astimezone()
    if return_time.tzinfo is None:
        return_time = return_time.astimezone()

    # Initialize variables
    departure_temperature = None
    return_temperature = None
    outside_temperatures = []

    # Convert 'dt' from string to datetime if needed and ensure it's offset-aware
    for forecast in weather_forecast:
        if isinstance(forecast['dt'], str):
            forecast['dt'] = datetime.datetime.fromisoformat(forecast['dt'])
        if forecast['dt'].tzinfo is None:
            forecast['dt'] = forecast['dt'].astimezone()

    # Collect temperatures from now until departure time
    for forecast in weather_forecast:
        forecast_time = forecast['dt']
        if forecast_time.tzinfo is None:
            forecast_time = forecast_time.astimezone()

        if current_time <= forecast_time <= departure_time:
            outside_temperatures.append(forecast['temp'])
        if departure_temperature is None and forecast_time >= departure_time:
            departure_temperature = forecast['temp']
        if return_temperature is None and forecast_time >= return_time:
            return_temperature = forecast['temp']
        if forecast_time > return_time and return_temperature is not None and departure_temperature is not None:
            break  # We have all we need, so we can break the loop

    # Handle cases where temperature data is missing
    if departure_temperature is None:
        logging.error(f"{RED}No weather data available for departure time{RESET}")
        departure_temperature = weather_forecast[-1]['temp']
    if return_temperature is None:
        logging.error(f"{RED}No weather data available for return time{RESET}")
        exit(1)
    if not outside_temperatures:
        logging.error(f"{RED}No weather data available between now and departure time{RESET}")
        outside_temperatures = [weather_forecast[0]['temp']]  # Use the first temperature as a fallback

    logging.debug(f"{GREEN}Departure temperature: {departure_temperature}°C, Return temperature: {return_temperature}°C{RESET}")
    logging.debug(f"{GREEN}Collected {len(outside_temperatures)} outside temperatures from now until departure{RESET}")
    return departure_temperature, return_temperature, outside_temperatures

def parse_weekday(weekday_str):
    weekdays = {
        'Montag': 0, 'Monday': 0,
        'Dienstag': 1, 'Tuesday': 1,
        'Mittwoch': 2, 'Wednesday': 2,
        'Donnerstag': 3, 'Thursday': 3,
        'Freitag': 4, 'Friday': 4,
        'Samstag': 5, 'Saturday': 5,
        'Sonntag': 6, 'Sunday': 6,
    }
    return weekdays.get(weekday_str.capitalize())


def get_evcc_charging_mode(evcc_api_base_url, loadpoint_id):
    logging.debug(f"{GREEN}Retrieving EVCC charging mode from {evcc_api_base_url}/api/state{RESET}")
    cache_file = f"evcc_charge_mode_cache_{loadpoint_id}.json"
    try:
        # API-Request an EVCC
        response = requests.get(f"{evcc_api_base_url}/api/state")
        response.raise_for_status()  # Prüfe auf HTTP-Fehler
        evcc_charging_mode = response.json()
        # Prüfen, ob die gewünschten Daten existieren
        loadpoints = evcc_charging_mode.get('result', {}).get('loadpoints', [])
        if len(loadpoints) > loadpoint_id:
            mode = loadpoints[loadpoint_id].get('mode')
            if mode is not None:
                logging.debug(f"{GREEN}Loadpoint mode: {mode}{RESET}")
                # Cache the mode
                with open(cache_file, "w") as f:
                    json.dump({"charge_mode": mode}, f)
                return mode
            else:
                logging.error(f"{RED}Der Modus konnte nicht gefunden werden{RESET}")
                return None
        else:
            logging.error(f"{RED}Keine Loadpoints gefunden{RESET}")
            return None
    except requests.RequestException as e:
        logging.error(f"{RED}Fehler beim Abrufen der EVCC-Daten: {e}{RESET}")
        return None

# Weitere Funktionen entsprechend anpassen...

# Hauptprogramm
if __name__ == "__main__":
    logging.debug(f"{YELLOW}Starting the EV charging optimization program...{RESET}")

    # Ladepunkte, Autos und Zuordnungen einlesen
    loadpoints = load_loadpoints()
    cars = load_cars()
    assignments = load_assignments()
    evcc_base_url = load_evcc(settings)

    # Fahrplan auslesen
    usage_plan = read_usage_plan()
    if not usage_plan:
        logging.error(f"{RED}Kein gültiger Fahrplan gefunden. Programm wird beendet.{RESET}")
        exit(1)

    # Wetterdaten abrufen
    weather_forecast = get_weather_forecast(API_KEY, LATITUDE, LONGITUDE)
    if not weather_forecast:
        logging.error(f"{RED}Keine Wetterdaten verfügbar. Programm wird beendet.{RESET}")
        exit(1)

    # Solarprognose abrufen
    solar_forecast = solarweather.get_solar_forecast(SOLCAST_API_URL)
    if not solar_forecast:
        logging.error(f"{RED}Keine Solarprognosedaten verfügbar. Programm wird beendet.{RESET}")
        exit(1)

    # Initialisiere Gesamtliste der Energiebedarfe
    total_ev_energy_gap = 0
    car_energy_requirements = {}

    # Für jedes Auto in den Zuordnungen
    for assignment in assignments:
        loadpoint_id = assignment['LOADPOINT_ID']
        car_name = assignment.get('CAR_NAME')

        # Prüfen, ob ein Auto angeschlossen ist
        if not car_name:
            logging.debug(f"{YELLOW}Kein Auto an Ladepunkt {loadpoint_id} angeschlossen. Überspringe.{RESET}")
            continue

        # Ladepunkt und Auto-Informationen abrufen
        loadpoint = next((lp for lp in loadpoints if lp['LOADPOINT_ID'] == loadpoint_id), None)
        car = next((c for c in cars if c['CAR_NAME'] == car_name), None)

        if not loadpoint or not car:
            logging.error(f"{RED}Ladepunkt oder Auto nicht gefunden für Zuweisung: {assignment}{RESET}")
            continue

        # Fahrplan für das Auto abrufen
        car_schedule = usage_plan.get(car_name)
        if not car_schedule:
            logging.debug(f"{YELLOW}Kein Fahrplan für Auto {car_name} gefunden. Überspringe.{RESET}")
            continue

        # Verwende den nächsten bevorstehenden Eintrag im Fahrplan
        if not car_schedule:
            logging.debug(f"{YELLOW}Kein bevorstehender Fahrplaneintrag für Auto {car_name}. Überspringe.{RESET}")
            continue

        next_trip = car_schedule[0]
        departure_time = next_trip['departure_datetime'].astimezone()
        return_time = next_trip['return_datetime'].astimezone()
        total_distance = next_trip['total_distance']

        # Überprüfen, ob Wetterdaten den Zeitraum bis zur Abfahrt abdecken
        last_weather_time = max(
            [entry['dt'] if isinstance(entry['dt'], datetime.datetime) else datetime.datetime.fromisoformat(entry['dt']) for entry in weather_forecast]
        )

        # Ensure last_weather_time is timezone-aware
        if last_weather_time.tzinfo is None:
            last_weather_time = last_weather_time.astimezone()

        # Ensure departure_time is timezone-aware
        if departure_time.tzinfo is None:
            departure_time = departure_time.astimezone()

        # Check if weather data covers the period until departure
        if last_weather_time < departure_time:
            logging.error(f"{RED}Wetterdaten decken den Zeitraum bis zur Abfahrt nicht vollständig ab für Auto {car_name}. Programm wird beendet.{RESET}")
            exit(1)

        # Temperaturen für Abfahrts- und Rückkehrzeiten abrufen
        departure_temperature, return_temperature, outside_temperatures = get_temperature_for_times(
            weather_forecast, departure_time, return_time
        )

        # Überprüfen, ob Temperaturdaten verfügbar sind
        if departure_temperature is None or return_temperature is None:
            logging.error(f"{RED}Wetterdaten für Abfahrts- oder Rückkehrzeit nicht verfügbar für Auto {car_name}. Programm wird beendet.{RESET}")
            exit(1)
        if not outside_temperatures:
            logging.error(f"{RED}Keine Wetterdaten zwischen jetzt und Abfahrtszeit verfügbar für Auto {car_name}. Programm wird beendet.{RESET}")
            exit(1)

        # Verbleibende Stunden bis zur Abfahrt berechnen
        current_time = datetime.datetime.now().astimezone()
        remaining_time = departure_time - current_time
        remaining_hours = remaining_time.total_seconds() / 3600
        logging.debug(f"{YELLOW}Verbleibende Stunden bis zur Abfahrt für {car_name}: {remaining_hours:.2f} Stunden{RESET}")

        # Ladezustand und Lademodus aus EVCC abrufen
        evcc_charging_mode = get_evcc_charging_mode(evcc_base_url, loadpoint_id)



        # Benötigte Energie für das Auto berechnen
        ev_energy = vehicle.calculate_ev_energy_consumption(
            departure_temperature,
            return_temperature,
            total_distance,
            car['CONSUMPTION'],
            car['BUFFER_DISTANCE'],
        )

        # Benötigten SoC berechnen
        required_soc = vehicle.calculate_required_soc(
            ev_energy,
            car['BATTERY_CAPACITY'],
            car['DEGRADATION'],
            car['BATTERY_YEAR']
        )
            
        # EVCC API Base URL einmal aus den globalen Einstellungen laden
        evcc_base_url = settings['EVCC']['EVCC_API_BASE_URL']

        # Benötigten SoC für das aktuelle Fahrzeug am Ladepunkt abrufen
        current_soc = vehicle.get_evcc_soc(evcc_base_url, loadpoint_id)


        # Fehlende Energie für das Auto berechnen
        ev_energy_gap = utils.calculate_energy_gap(
            required_soc,
            current_soc,
            car['BATTERY_CAPACITY'],  
            car['DEGRADATION'],       
            car['BATTERY_YEAR']       
        )

        # Speichere die Energiebedarfe
        car_energy_requirements[car_name] = {
            'ev_energy_gap': ev_energy_gap,
            'required_soc': required_soc,
            'current_soc': current_soc,
            'loadpoint_id': loadpoint_id,
            'loadpoint': loadpoint,
            'car': car,
            'departure_time': departure_time,
            'remaining_hours': remaining_hours
        }

        total_ev_energy_gap += ev_energy_gap

    # Heizenergie für das Haus berechnen
    # Hier kannst du die Funktion anpassen, um die Heizenergie nur einmal zu berechnen
    energy_consumption_house = utils.calculate_climate_control_energy_house(
        outside_temperatures,
        remaining_hours,
        solar_forecast,
        HEATED_AREA,
        INDOOR_TEMPERATURE,
        MAXIMUM_PV,
        ENERGY_CERTIFICATE,
        SUMMER_THRESHOLD,
        BASE_LOAD
        )

    # Verfügbare Solarenergie unter Berücksichtigung des Hausverbrauchs berechnen
    available_solar_energy = utils.calculate_available_solar_energy(
        solar_forecast,
        departure_time,
        energy_consumption_house,
        BASE_LOAD
    )

    # Wenn Loadmanagement aktiviert ist
    if LOADMANAGEMENT:
        logging.debug(f"{GREEN}Loadmanagement ist aktiviert.{RESET}")
        # Berechne die Gesamtladedauer
        total_charge_hours = 0
        for car_name, car_info in car_energy_requirements.items():
            ev_energy_gap =  car_info['ev_energy_gap']
            charger_energy = car_info['loadpoint']['CHARGER_ENERGY']
            charge_hours = ev_energy_gap / charger_energy
            total_charge_hours += charge_hours
            car_energy_requirements[car_name]['charge_hours'] = charge_hours

        # Zusätzliche Energie, die gekauft werden muss
        ev_energy_additional_purchase = total_ev_energy_gap - available_solar_energy
        if ev_energy_additional_purchase < 0:
            ev_energy_additional_purchase = 0  # Kein zusätzlicher Kauf erforderlich

        # Hier kann die Logik erweitert werden, um die Ladefenster entsprechend zu planen
        # Für jedes Auto die minSoC setzen usw.

    else:
        logging.debug(f"{GREEN}Loadmanagement ist deaktiviert.{RESET}")
        # Individuelle Berechnungen für jedes Auto
        for car_name, car_info in car_energy_requirements.items():
            ev_energy_gap = car_info['ev_energy_gap']
            if ev_energy_gap > 0:
                # Zusätzliche Energie, die gekauft werden muss
                ev_energy_additional_purchase = ev_energy_gap - available_solar_energy
                if ev_energy_additional_purchase < 0:
                    ev_energy_additional_purchase = 0  # Kein zusätzlicher Kauf erforderlich

                # Weitere Berechnungen und Aktionen pro Auto...
                # Strompreise abrufen, Ladefenster finden, SoC setzen, etc.

    # Das Programm kann entsprechend erweitert werden, um die Ladefenster zu planen und die notwendigen API-Aufrufe zu tätigen.

