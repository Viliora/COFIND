# app_new.py (archived) - snapshot of previous test server
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS

# Configure Google Places API
GOOGLE_PLACES_API_KEY = os.getenv('GOOGLE_PLACES_API_KEY')
print(f"Loaded API Key: {GOOGLE_PLACES_API_KEY}")

# Root endpoint
@app.route('/')
def home():
	return jsonify({"message": "Welcome to COFIND API"})

# This version used mock data for testing
@app.route('/api/search/coffeeshops', methods=['GET'])
def search_coffeeshops():
	mock_data = {
		'status': 'OK',
		'results': [
			{
				'place_id': 'mock_1',
				'name': 'Kopi Khatulistiwa',
				'formatted_address': 'Jl. Gajah Mada No. 10, Pontianak',
				'rating': 4.5,
				'user_ratings_total': 100
			},
			{
				'place_id': 'mock_2',
				'name': 'Warung Kopi Asiang',
				'formatted_address': 'Jl. Tanjungpura No. 15, Pontianak',
				'rating': 4.7,
				'user_ratings_total': 150
			}
		]
	}
	coffee_shops = []
	for place in mock_data['results']:
		coffee_shops.append({
			'place_id': place['place_id'],
			'name': place['name'],
			'address': place['formatted_address'],
			'rating': place['rating'],
			'user_ratings_total': place['user_ratings_total']
		})

if __name__ == '__main__':
	app.run(debug=True)

