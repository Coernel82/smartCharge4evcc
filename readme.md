![a futuristic image of ev and solar panels](assets/project_graphic.jpg)
# 🚨 Disclaimer

**Warning:** This project is in **alpha status**. Expect inconsistencies in the code and naming conventions, bugs and missing docstrings. I am a hobby programmer Use at your own risk! There are inconsistensies in the naming conventions of the variables a mix of German and English. Also this code was created with the help of AI and therefore should not be used for AI traning. ⚠️
## 📋 Table of Contents

- [🚨 Disclaimer](#-disclaimer)
- [SmartCharge 🚗⚡](#smartcharge-)
- [🌟 Features](#-features)
- [Prerequisites](#prerequisites)
- [🛠️ Installation](#️-installation)
- [🚀 Usage](#-usage)
- [🧐 How It Works](#-how-it-works)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

---


# SmartCharge 🚗⚡

Welcome to **SmartCharge**, a smart charging solution for electric vehicles (EVs) that integrates multiple load points and home battery systems. This program optimizes your EV charging schedule based on solar production forecasts, weather conditions, electricity prices, and home energy consumption. 🌞🌧️💡

### What this program does in some short sentences:
Using evcc's api it sets up your car trips (using a schedule) and loads the car to the minimum amount possible using the cheapest energy price possible taking into consideration future charges from PV, energy consumption of the car considering the trip lenght and the temperatures. PV charge is estimated with solcast and added to the EV. Remaining energy is used to "cache" this in the home battery. Also the energy consumption of the house is estimated by multiple factors. This energy is precharged into the battery if this is economically  resonable - of course at cheapest cost possible.

### Prospect
Include heatpump to preheat the house (so that the heatpump can be blocked when energy is expensive). This is different to the two implemented logics:
- car charging: known departure and return time, known energy, known weather, known SoC
- battery charging: hourly resolution of energy requirements, known Soc
- heatpump: hourly resolution, unknown SoC (= temperature). Solution: energy readings from the heatpump in kWh or include thermometer (in my case in the exhaust air of the ventilation system before the heat exchanger to get an average home temperature) and get readings from MQTT
- create a web interface using websockets to have the data available in real time and also to make setup of trips without danger of error

# Participation
I highly depend on your participation now. Before creating pull requests please open an issue and let me assign the issue to you to make sure that not multiple people are working on the same function.
There is a lot to do:
- testing
- looking at the TODO: / FIXME: / BUG: comments here and in the code



---


## 🌟 Features

- **Multiple Load Point Support**: Manage charging for multiple EVs simultaneously.
- **Home Battery Integration**: Optimize charging based on home battery status and capacity.
- **Solar Forecasting**: Utilize solar production forecasts to prioritize charging when solar energy is abundant. 🌞
- **Weather Integration**: Adjust charging plans based on weather conditions. ☔
- **Electricity Price Optimization**: Schedule charging during off-peak hours to save on electricity costs. 💰
- **evcc Integration**: Seamlessly integrate with [evcc (Electric Vehicle Charge Controller) GitHub Link ](https://github.com/evcc-io/evcc) / [Non GitHub link](https://www.evcc.io)

---

## Prerequisites
- PV installation
- home battery (TODO: settings: USE_HOMEBATTERY: true / false)
- Python
- evcc
- InfluxDB (also set up in evcc)
- A Solcast account with your photovoltaic (PV) system set up. You can create an account and set up your PV system [here](https://www.solcast.com/free-rooftop-solar-forecasting).
- An OpenWeather account to retrieve weather data. You can create an account and get your API key [here](https://home.openweathermap.org/users/sign_up).
- a contract with tibber and your [acces token] (https://developer.tibber.com/settings/accesstoken), alternatively: integrate another source for energy prices such as Fraunhofer or Awattar - see - [Contributing](#contributing)

## 🛠️ Installation
If these instructions say ``sudo`` do so. If not, do not!
Follow these steps to set up SmartCharge on your system:

### 1. Clone the Repository

```bash
git clone https://github.com/Coernel82/smartCharge4evcc.git
cd smartCharge4evcc 
```


### 2. Set Up a Virtual Environment on Debian based Systems (Raspberry Pi!)

It's recommended to use a Python virtual environment to manage dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
```

To deactivate / leave the virtual environment simply use ``deactivate``

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Settings

- Update the `settings_example.json` file in the `backend/data` directory with your specific configuration and copy it to create the real settings `mv settings_example.json settings.json`

---

## 🚀 Usage

### Running SmartCharge Manually for testing

Activate your virtual environment and run the `smartCharge.py` script:

```bash
source venv/bin/activate 
python smartCharge.py
```

### Running SmartCharge *Hourly* with Cron - this is what you need to do!

To run SmartCharge automatically every hour (you must run it every hour, not every 30 minutes, not every two hours), you can use a cron job. We'll create a bash script to ensure the virtual environment is activated when the script runs.

Note: You may run it every 10 minutes or so - you are welcome to test it and open an issue. There might be finder resolutions for weather and other data available. However at the moment running more often than once an hour only might be making sense in case of cheap home battery charging to prevent charging more than needed.

#### 1. Create a Bash Script and make it executable


```bash
cat <<EOF > run_smartcharge.sh
#!/bin/bash
source /home/evcc/venv/bin/activate
python /home/evcc/smartCharge4evcc/backend/smartCharge.py
deactivate
EOF
chmod +x run_smartcharge.sh
```
This will create your bashfile without opening nano or any other editor.

#### 2. Edit Crontab

Run `crontab -e` and add the following line to schedule the script hourly:

```bash
0 * * * * /home/evcc/smartCharge4evcc/run_smartcharge.sh >> /home/evcc/SmartCharge4evcc/smartcharge.log 2>&1
```

This runs the script at the top of every hour and logs output to `smartcharge.log`.
Delete ``>> /home/evcc/smartCharge4evcc/smartcharge.log 2>&1`` if you don't need the log any more.

---

## 🧐 How It Works

SmartCharge intelligently schedules your EV charging by considering several factors:

1. **Weather Forecasting** ⛅
    - Retrieves weather data to predict temperature and adjust charging accordingly as the car uses different amounts of energy when it is warm or cold. Also heating of your home is influenced.
2. **Solar Production Forecast** 🌤️
    - Uses Solcast API to get solar generation forecasts.
3. **Electricity Prices** 💹
    - Fetches current and future electricity prices from the TIBBER API (TODO: or other sources.)
4. **Home Battery Status** 🔋
    - Monitors home battery capacity and state of charge to optimize energy usage. Charges as much as needed but as little as possible to be able to use the battery when energy is more expansive than using it from the battery. Takes degradation and additional charging costs due to wear and efficiency into consideration.
5. **Vehicle Usage Plan** 🚘
    - Considers your vehicle's upcoming trips from `usage_plan.json` to ensure it's charged when needed.
6. **Energy Consumption Data** 📊
    - Reads energy consumption patterns to predict baseload and peak times.

By combining these data points, SmartCharge determines the most cost-effective and energy-efficient charging schedule for your EVs.

### Components Breakdown

- **utils.py**: Helper functions for calculations and data handling.
- **initialize_smartcharge.py**: Loads settings and initializes the application.
- **smartCharge.py**: The main script that orchestrates the charging schedule.
- **vehicle.py**: Handles vehicle-specific calculations like energy consumption and SOC (State of Charge).
- **home.py**: Manages home energy consumption, battery status, and interactions with home devices.
- **solarweather.py**: Fetches and processes weather and solar data.
- **evcc.py**: Interfaces with the EVCC API to set charging parameters.
- **settings.json**: Configuration file containing API keys and user settings.
- **usage_plan.json**: User-defined schedule for vehicle usage.

---

## 🤝 Contributing

Contributions are welcome! Please fork the repository and create a pull request. For major changes, please open an issue first to discuss what you would like to change. 🛠️

---

## 📄 License

MIT

 

---

Enjoy smart charging! If you encounter any issues or have suggestions, feel free to open an issue on GitHub. 😊
