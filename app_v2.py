# app_v2.py
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
GOOGLE_PLACES_API_KEY = 'AIzaSyBJVmhFXkZrtyD0y1CgNWjBVAodKdY07cU'
print(f"Using API Key: {GOOGLE_PLACES_API_KEY}")

# Enable CORS for all domains
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Root endpoint
@app.route('/')
def home():
    return jsonify({"message": "Welcome to COFIND API"})

# Endpoint untuk mencari coffee shop menggunakan Google Places API
@app.route('/api/search/coffeeshops', methods=['GET'])
def search_coffeeshops():
    try:
        # Koordinat pusat Pontianak Kota
        lat = 0.0263303
        lng = 109.3425039
        
        # Base URL untuk Places API Nearby Search
        base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        
        # Parameters untuk request
        params = {
            'location': f"{lat},{lng}",
            'radius': '5000',  # 5km radius
            'type': 'cafe',
            'keyword': 'coffee',
            'key': GOOGLE_PLACES_API_KEY
        }

        print("Making request to Google Places API")
        response = requests.get(base_url, params=params)
        data = response.json()
        
        print(f"Response status: {data.get('status')}")
        
        if data.get('status') == 'OK':
            # Filter dan format hasil
            coffee_shops = []
            for place in data.get('results', [])[:10]:  # Ambil 10 coffee shop teratas
                coffee_shop = {
                    'place_id': place.get('place_id'),
                    'name': place.get('name'),
                    'address': place.get('vicinity'),
                    'rating': place.get('rating'),
                    'user_ratings_total': place.get('user_ratings_total'),
                    'location': place.get('geometry', {}).get('location'),
                    'business_status': place.get('business_status'),
                    'price_level': place.get('price_level'),
                    'photos': place.get('photos', [])
                }
                coffee_shops.append(coffee_shop)
            
            return jsonify({
                'status': 'success',
                'data': coffee_shops
            })
        else:
            error_message = f"Google Places API error: {data.get('status')} - {data.get('error_message', 'Unknown error')}"
            print(error_message)
            return jsonify({
                'status': 'error',
                'message': error_message
            }), 400
            
    except Exception as e:
        error_message = f"Error: {str(e)}"
        print(error_message)
        return jsonify({
            'status': 'error',
            'message': error_message
        }), 500

# Endpoint untuk mendapatkan detail coffee shop
@app.route('/api/coffeeshops/detail/<place_id>', methods=['GET'])
def get_place_details(place_id):
    try:
        base_url = "https://maps.googleapis.com/maps/api/place/details/json"
        
        params = {
            'place_id': place_id,
            'fields': 'name,rating,formatted_phone_number,formatted_address,geometry,photos,reviews,opening_hours,price_level,website',
            'key': GOOGLE_PLACES_API_KEY
        }

        print("Making request to Places Details API")
        response = requests.get(base_url, params=params)
        data = response.json()
        
        if data.get('status') == 'OK':
            result = data.get('result', {})
            place_details = {
                'name': result.get('name'),
                'address': result.get('formatted_address'),
                'phone': result.get('formatted_phone_number'),
                'rating': result.get('rating'),
                'location': result.get('geometry', {}).get('location'),
                'reviews': result.get('reviews', []),
                'opening_hours': result.get('opening_hours', {}).get('weekday_text', []),
                'price_level': result.get('price_level'),
                'website': result.get('website'),
                'photos': result.get('photos', [])
            }
            
            return jsonify({
                'status': 'success',
                'data': place_details
            })
        else:
            error_message = f"Google Places API error: {data.get('status')} - {data.get('error_message', 'Unknown error')}"
            print(error_message)
            return jsonify({
                'status': 'error',
                'message': error_message
            }), 400
            
    except Exception as e:
        error_message = f"Error: {str(e)}"
        print(error_message)
        return jsonify({
            'status': 'error',
            'message': error_message
        }), 500

if __name__ == '__main__':
    app.run(debug=True)