import requests
import logging
import datetime
import json
import os
import numpy as np
import pytz
import math

# User-Config

# OneCall API 3.0 von OpenWeather
API_KEY = "5bf34700a4b4c39182ad26f1abf1890d"
LATITUDE = 50.934
LONGITUDE = 7.294

# Car
BATTERY_CAPACITY = 50 * 1000        # BATTERY_CAPACITY of EV in Wh
BATTERY_YEAR = 2021                 # year of purchase to calculate degradation
DEGRADATION = 0.02                  # degradation rate per year
BUFFER_DISTANCE = 20                # how many kilometers should be a reserve
CONSUMPTION = 16 * 1000             # energy consumption in Wh per 100 km (17,1 - 15,6 kWh is what Opel says)

# Loadpoint
LOADPOINT_ID = 1
CAR_NAME = "Opel"
EVCC_API_BASE_URL = "http://192.168.178.28:7070"
CHARGER_ENERGY = 7200               # Maximum charger power in Watt
MINIMUM_CHARGE_POWER = 1380         # Determines the PV energy that can be used for the car

# House
ENERGY_CERTIFICATE = 7 * 1000       # Heating energy required per m²*a*K (Wh/(m²*a*K))
HEATED_AREA = 222                   # Heated area of house
INDOOR_TEMPERATURE = 21             # Indoor temperature in °C
BASE_LOAD = 400                     # Base energy consumption for light, ventilation etc. in W

# Energy: SOLCAST und TIBBER API-URLs und Header
SOLCAST_API_URL = "https://api.solcast.com.au/rooftop_sites/cfd2-137d-2164-9340/forecasts?format=json&api_key=tzQI1cc2BbsvohK8W7hfuHGoPDzzQMXi&hours=24"
TIBBER_API_URL = "https://api.tibber.com/v1-beta/gql"
tibber_headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer 5n3THamg76PhUjvpg8EdjaxN8dUXNTx4lW7w3b_UZOY"
}