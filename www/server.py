from flask import Flask, jsonify, request  
import json
import os
from flask_cors import CORS

app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Path to the usage_plan.json file
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'usage_plan.json')

def load_data():
    """Load data from the JSON file"""
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    """Save data to the JSON file"""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

@app.route('/get_data')
def get_data():
    """API endpoint to return the data from usage_plan.json"""
    data = load_data()
    return jsonify(data)

@app.route('/add_non_recurring_trip', methods=['POST'])
def add_non_recurring_trip():
    """API endpoint to add a non-recurring trip"""
    try:
        data = load_data()  # Load current JSON data
        new_trip = request.json  # Get the new trip data from the request

        # Add the new trip to the non_recurring list
        data['non_recurring'].append(new_trip)

        # Save the updated data to the JSON file
        save_data(data)

        return jsonify({'status': 'success', 'message': 'Trip added successfully'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/add_recurring_trip', methods=['POST'])
def add_recurring_trip():
    """API endpoint to add a recurring trip"""
    try:
        data = load_data()  # Load current JSON data
        new_trip = request.json  # Get the new recurring trip data from the request

        # Add the new trip to the recurring list
        data['recurring'].append(new_trip)

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

if __name__ == '__main__':
    app.run(debug=True)
