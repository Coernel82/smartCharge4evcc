from flask import Flask, jsonify, request, render_template, send_from_directory
import json
import os
from flask_cors import CORS
import uuid

app = Flask(__name__)

# Enable CORS for all routes
# CORS(app, resources={r"/*": {"origins": "*"}})
CORS(app)

# Load data from JSON file
def load_data():
    with open('usage_plan.json', 'r') as f:
        return json.load(f)

# Save data to JSON file
def save_data(data):
    with open('usage_plan.json', 'w') as f:
        json.dump(data, f, indent=4)

# Serve the main HTML file
@app.route('/')
def index():
    return render_template('index.html')

# Serve the settings HTML file
@app.route('/settings.html')
def settings():
    return render_template('settings.html')

# App route for favicon
@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico')

# Serve static files
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/templates/time_series_data.json')
def serve_time_series_data():
    return send_from_directory('templates', 'time_series_data.json')

# Path to the usage_plan.json file
USAGE_PLAN = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend', 'data', 'usage_plan.json'))
# USAGE_PLAN = os.path.join(os.path.dirname(__file__), 'usage_plan.json')

SETTINGS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend', 'data', 'settings.json'))

def load_data():
    """Load data from the JSON file"""
    with open(USAGE_PLAN, 'r') as f:
        return json.load(f)


def save_data(data):
    """Save data to the JSON file"""
    with open(USAGE_PLAN, 'w') as f:
        json.dump(data, f, indent=4)

@app.route('/get_data')
def get_data():
    """API endpoint to return the data from usage_plan.json"""
    data = load_data()
    return jsonify(data)

@app.route('/load_settings')
def load_settings():
    try:
        settings_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend', 'data', 'settings.json'))
        with open(settings_path, 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/add_non_recurring_trip', methods=['POST'])
def add_non_recurring_trip():
    """API endpoint to add a non-recurring trip"""
    try:
        data = load_data()  # Load current JSON data
        new_trip = request.json  # Get the new trip data from the request

        # Extrahieren Sie die Marke aus den neuen Fahrtdaten
        brand = new_trip.get('brand')
        if not brand:
            return jsonify({'error': 'Brand not specified'}), 400

        if brand not in data:
            return jsonify({'error': f'Brand "{brand}" does not exist'}), 400

        # Entfernen Sie die Marke aus den Fahrtdaten, da sie nicht innerhalb der Fahrt benötigt wird
        new_trip.pop('brand', None)

        # Add a unique id to the trip
        new_trip['id'] = 'nrt-' + str(uuid.uuid4())
        

        # Fügen Sie die neue Fahrt zur non_recurring Liste der entsprechenden Marke hinzu
        data[brand]['non_recurring'].append(new_trip)
        save_data(data)

        return jsonify({'message': 'Trip added successfully'}), 201
    except Exception as e:
        print(f"Error adding trip: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/add_recurring_trip', methods=['POST'])
def add_recurring_trip():
    """API endpoint to add a recurring trip"""
    try:
        data = load_data()  # Load current JSON data
        new_trip = request.json  # Get the new recurring trip data from the request

        # Extrahieren Sie die Marke aus den neuen Fahrtdaten
        brand = new_trip.get('brand')
        if not brand:
            return jsonify({'error': 'Brand not specified'}), 400

        if brand not in data:
            return jsonify({'error': f'Brand "{brand}" does not exist'}), 400

        # Entfernen Sie die Marke aus den Fahrtdaten, da sie nicht innerhalb der Fahrt benötigt wird
        new_trip.pop('brand', None)
        
        # Add a unique id to the trip
        new_trip['id'] = 'rt-' + str(uuid.uuid4())

        # Add the new trip to the recurring list
        data[brand]['recurring'].append(new_trip)

        # Save the updated data to the JSON file
        save_data(data)

        return jsonify({'status': 'success', 'message': 'Recurring trip added successfully'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/test_json')
def test_json():
    """Test route to check if the JSON file is being read correctly"""
    try:
        data = load_data()
        return jsonify({"status": "success", "data": data}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# app route save settings to ../backend/data/settings.json
@app.route('/save_settings', methods=['POST'])
def save_settings():
    """API endpoint to save settings to settings.json"""
    try:
        settings = request.json
        settings_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'settings.json')
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=4)
        return jsonify({'message': 'Settings saved successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# editing and deleting trips
@app.route('/get_trip/<trip_id>', methods=['GET'])
def get_trip(trip_id):
    """API endpoint to get a specific trip by ID"""
    try:
        data = load_data()
        for brand in data:
            for trip_type in ['non_recurring', 'recurring']:
                for trip in data[brand][trip_type]:
                    if trip['id'] == trip_id:
                        return jsonify({'status': 'success', 'trip': trip}), 200
        return jsonify({'status': 'error', 'message': 'Trip not found'}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/edit_trip', methods=['POST'])
def edit_trip():
    """API endpoint to edit a trip"""
    try:
        data = load_data()
        updated_trip = request.json
        trip_id = updated_trip.get('id')
        if not trip_id:
            return jsonify({'error': 'Trip ID not specified'}), 400
        for brand in data:
            for trip_type in ['non_recurring', 'recurring']:
                for trip in data[brand][trip_type]:
                    if trip['id'] == trip_id:
                        trip.update(updated_trip)
                        save_data(data)
                        return jsonify({'message': 'Trip updated successfully'}), 200
        return jsonify({'error': 'Trip not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete_trip', methods=['POST'])
def delete_trip():
    """API endpoint to delete a trip"""
    try:
        data = load_data()
        trip_id = request.json.get('id')
        if not trip_id:
            return jsonify({'error': 'Trip ID not specified'}), 400
        for brand in data:
            for trip_type in ['non_recurring', 'recurring']:
                data[brand][trip_type] = [trip for trip in data[brand][trip_type] if trip['id'] != trip_id]
        save_data(data)
        return jsonify({'message': 'Trip deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/update_holiday_mode', methods=['POST'])
def update_holiday_mode():
    """API endpoint to update the holiday mode status"""
    # empty code
    try:
        data = request.get_json()
        holiday_mode = data.get('HOLIDAY_MODE', False)
        if isinstance(holiday_mode, str):
            holiday_mode = holiday_mode.lower() == 'true'
        if not isinstance(holiday_mode, bool):
            return jsonify({'error': 'HOLIDAY_MODE must be a boolean'}), 400
        settings = load_settings().json
        settings['HolidayMode']['HOLIDAY_MODE'] = holiday_mode
        settings_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend', 'data', 'settings.json'))
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    print("Holiday mode updated")
    return



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


