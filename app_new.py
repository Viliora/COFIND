# app.py
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

# Endpoint untuk mencari coffee shop menggunakan Google Places API
@app.route('/api/search/coffeeshops', methods=['GET'])
def search_coffeeshops():
    try:
        # Get parameters from request
        location = request.args.get('location', 'Pontianak')  # Default ke Pontianak jika tidak ada lokasi
        radius = request.args.get('radius', '5000')  # Radius dalam meter (default 5km)
        
        # Validate API key
        if not GOOGLE_PLACES_API_KEY:
            return jsonify({
                'status': 'error',
                'message': 'Google Places API key is not configured'
            }), 500
        
        # Temporary static data for testing
        mock_data = {
            'status': 'OK',
            'results': [
                {
                    'place_id': 'mock_1',
                    'name': 'Kopi Khatulistiwa',
                    'formatted_address': 'Jl. Gajah Mada No. 10, Pontianak',
                    'rating': 4.5,
                    'user_ratings_total': 100,
                    'geometry': {'location': {'lat': 0.0263303, 'lng': 109.3425039}},
                    'photos': [],
                    'price_level': 2,
                    'business_status': 'OPERATIONAL'
                },
                {
                    'place_id': 'mock_2',
                    'name': 'Warung Kopi Asiang',
                    'formatted_address': 'Jl. Tanjungpura No. 15, Pontianak',
                    'rating': 4.7,
                    'user_ratings_total': 150,
                    'geometry': {'location': {'lat': 0.0263303, 'lng': 109.3425039}},
                    'photos': [],
                    'price_level': 1,
                    'business_status': 'OPERATIONAL'
                }
            ]
        }
        
        data = mock_data
        print("Using mock data for testing")
        
        if True:  # Always true for mock data
            # Filter dan format hasil
            coffee_shops = []
            for place in data.get('results', []):
                coffee_shop = {
                    'place_id': place.get('place_id'),
                    'name': place.get('name'),
                    'address': place.get('formatted_address'),
                    'rating': place.get('rating'),
                    'user_ratings_total': place.get('user_ratings_total'),
                    'location': place.get('geometry', {}).get('location'),
                    'photos': place.get('photos', []),
                    'price_level': place.get('price_level'),
                    'business_status': place.get('business_status'),
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
            
    except requests.exceptions.RequestException as e:
        error_message = f"Network error: {str(e)}"
        print(error_message)
        return jsonify({
            'status': 'error',
            'message': error_message
        }), 500
    except Exception as e:
        error_message = f"Unexpected error: {str(e)}"
        print(error_message)
        return jsonify({
            'status': 'error',
            'message': error_message
        }), 500

# Endpoint untuk mendapatkan detail coffee shop berdasarkan place_id
@app.route('/api/coffeeshops/detail/<place_id>', methods=['GET'])
def get_place_details(place_id):
    try:
        if not GOOGLE_PLACES_API_KEY:
            return jsonify({
                'status': 'error',
                'message': 'Google Places API key is not configured'
            }), 500

        base_url = "https://maps.googleapis.com/maps/api/place/details/json"
        
        params = {
            'place_id': place_id,
            'fields': 'name,rating,formatted_phone_number,formatted_address,geometry,photos,reviews,opening_hours,price_level,website',
            'key': GOOGLE_PLACES_API_KEY
        }
        
        print(f"Making request to Google Places Details API:")
        print(f"Base URL: {base_url}")
        print(f"Parameters: {params}")

        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        print(f"Response status code: {response.status_code}")
        print(f"Response body: {data}")
        
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
            
    except requests.exceptions.RequestException as e:
        error_message = f"Network error: {str(e)}"
        print(error_message)
        return jsonify({
            'status': 'error',
            'message': error_message
        }), 500
    except Exception as e:
        error_message = f"Unexpected error: {str(e)}"
        print(error_message)
        return jsonify({
            'status': 'error',
            'message': error_message
        }), 500

# Run the app
if __name__ == '__main__':
    app.run(debug=True)