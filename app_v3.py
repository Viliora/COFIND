# app_v3.py
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
API_KEY = 'AIzaSyBJVmhFXkZrtyD0y1CgNWjBVAodKdY07cU'
PLACES_API_BASE = 'https://places.googleapis.com/v1/places'

# Root endpoint
@app.route('/')
def home():
    return jsonify({"message": "Welcome to COFIND API"})

# Endpoint untuk mencari coffee shop menggunakan Google Places API
@app.route('/api/search/coffeeshops', methods=['GET'])
def search_coffeeshops():
    try:
        # Search nearby places using Google Places API
        location = {
            "latitude": 0.0263303,
            "longitude": 109.3425039
        }
        
        headers = {
            'Content-Type': 'application/json',
            'X-Goog-Api-Key': API_KEY,
            'X-Goog-FieldMask': 'places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.location,places.id,places.businessStatus,places.priceLevel'
        }

        search_params = {
            'includedTypes': ['cafe'],
            'locationRestriction': {
                'circle': {
                    'center': location,
                    'radius': 5000.0
                }
            },
            'maxResultCount': 10
        }

        # Make the API request
        response = requests.post(
            f'{PLACES_API_BASE}:searchNearby',
            headers=headers,
            json=search_params
        )
        
        print("API Response:", response.status_code)
        print("Response content:", response.text)

        if response.status_code == 200:
            data = response.json()
            places = data.get('places', [])
            
            coffee_shops = []
            for place in places:
                coffee_shop = {
                    'place_id': place.get('id'),
                    'name': place.get('displayName', {}).get('text', ''),
                    'address': place.get('formattedAddress', ''),
                    'rating': place.get('rating', 0),
                    'user_ratings_total': place.get('userRatingCount', 0),
                    'location': place.get('location', {}),
                    'business_status': place.get('businessStatus', ''),
                    'price_level': place.get('priceLevel', '')
                }
                coffee_shops.append(coffee_shop)

            return jsonify({
                'status': 'success',
                'data': coffee_shops
            })
        else:
            error_message = f"Google Places API error: {response.status_code}"
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
        headers = {
            'X-Goog-Api-Key': API_KEY,
            'X-Goog-FieldMask': 'id,displayName,formattedAddress,location,rating,userRatingCount,currentOpeningHours,primaryType,photos,priceLevel,websiteUri,nationalPhoneNumber,reviews'
        }

        # Make the API request
        response = requests.get(
            f'{PLACES_API_BASE}/{place_id}',
            headers=headers
        )

        if response.status_code == 200:
            place = response.json()
            
            place_details = {
                'name': place.get('displayName', {}).get('text', ''),
                'address': place.get('formattedAddress', ''),
                'phone': place.get('nationalPhoneNumber', ''),
                'rating': place.get('rating', 0),
                'location': place.get('location', {}),
                'reviews': place.get('reviews', []),
                'opening_hours': place.get('currentOpeningHours', {}).get('weekdayDescriptions', []),
                'price_level': place.get('priceLevel', ''),
                'website': place.get('websiteUri', ''),
                'photos': place.get('photos', [])
            }
            
            return jsonify({
                'status': 'success',
                'data': place_details
            })
        else:
            error_message = f"Google Places API error: {response.status_code}"
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