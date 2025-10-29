# app.py (canonicalized from app_v2.py)
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

# Configure Google Places API (prefer using .env for key)
GOOGLE_PLACES_API_KEY = os.getenv('GOOGLE_PLACES_API_KEY') or 'YOUR_API_KEY'
print(f"Using API Key: {GOOGLE_PLACES_API_KEY}")

# Enable CORS for /api/*
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Root endpoint
@app.route('/')
def home():
    return jsonify({"message": "Welcome to COFIND API"})

# Endpoint untuk mencari coffee shop menggunakan Google Places API
@app.route('/api/search/coffeeshops', methods=['GET'])
def search_coffeeshops():
    try:
        # Baca query params: support `lat`+`lng` (nearbysearch) atau `location` string (textsearch)
        lat = request.args.get('lat', type=float)
        lng = request.args.get('lng', type=float)
        location_str = request.args.get('location')  # e.g. 'Pontianak' or an address
        radius = request.args.get('radius', default='5000')
        keyword = request.args.get('keyword', default='coffee')

        # Pilih endpoint berdasarkan input
        if lat is not None and lng is not None:
            # Nearby Search (menggunakan koordinat)
            base_url = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json'
            params = {
                'location': f"{lat},{lng}",
                'radius': radius,
                'type': 'cafe',
                'keyword': keyword,
                'key': GOOGLE_PLACES_API_KEY
            }
        elif location_str:
            # Text Search (gunakan nama lokasi / kota)
            # Contoh query: "coffee in Pontianak"
            base_url = 'https://maps.googleapis.com/maps/api/place/textsearch/json'
            params = {
                'query': f"{keyword} in {location_str}",
                'key': GOOGLE_PLACES_API_KEY
            }
        else:
            # Default ke koordinat pusat Pontianak jika tidak ada param
            lat = 0.0263303
            lng = 109.3425039
            base_url = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json'
            params = {
                'location': f"{lat},{lng}",
                'radius': radius,
                'type': 'cafe',
                'keyword': keyword,
                'key': GOOGLE_PLACES_API_KEY
            }

        print(f"Making request to Google Places API: {base_url} with params {params}")
        response = requests.get(base_url, params=params)
        data = response.json()

        print(f"Response status: {data.get('status')}, error_message: {data.get('error_message')}")

        if data.get('status') == 'OK':
            # Depending on endpoint, results key is 'results'
            results = data.get('results', [])
            coffee_shops = []
            for place in results[:10]:
                coffee_shop = {
                    'place_id': place.get('place_id'),
                    'name': place.get('name'),
                    'address': place.get('vicinity') or place.get('formatted_address'),
                    'rating': place.get('rating'),
                    'user_ratings_total': place.get('user_ratings_total'),
                    'location': place.get('geometry', {}).get('location'),
                    'business_status': place.get('business_status'),
                    'price_level': place.get('price_level'),
                    'photos': place.get('photos', [])
                }
                coffee_shops.append(coffee_shop)

            return jsonify({'status': 'success', 'data': coffee_shops})
        else:
            error_message = f"Google Places API error: {data.get('status')} - {data.get('error_message', 'Unknown error')}"
            print(error_message)
            return jsonify({'status': 'error', 'message': error_message}), 400

    except Exception as e:
        error_message = f"Error: {str(e)}"
        print(error_message)
        return jsonify({'status': 'error', 'message': error_message}), 500

# Endpoint untuk mendapatkan detail coffee shop
# Endpoint untuk mendapatkan detail coffee shop
@app.route('/api/coffeeshops', methods=['GET'])
def list_coffeeshops():
    try:
        # Ambil ID tempat dari database atau metode lain
        place_ids = ['place_id_1', 'place_id_2', 'place_id_3']  # Ganti dengan ID tempat yang sesuai
        
        coffee_shops = []
        for place_id in place_ids:
            place_details = get_place_details(place_id)
            if place_details.get('status') == 'success':
                coffee_shop = place_details.get('data')
                coffee_shops.append(coffee_shop)
        
        return jsonify({
            'status': 'success',
            'data': coffee_shops
        })
    except Exception as e:
        error_message = f"Error: {str(e)}"
        print(error_message)
        return jsonify({
            'status': 'error',
            'message': error_message
        }), 500

# Fungsi untuk mendapatkan detail tempat dari Places Details API
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
            return {
                'status': 'success',
                'data': data.get('result', {})
            }
        else:
            error_message = f"Google Places API error: {data.get('status')} - {data.get('error_message', 'Unknown error')}"
            print(error_message)
            return {
                'status': 'error',
                'message': error_message
            }
    except Exception as e:
        error_message = f"Error: {str(e)}"
        print(error_message)
        return {
            'status': 'error',
            'message': error_message
        }


if __name__ == '__main__':
    # Jalankan app secara langsung untuk pengembangan
    # Gunakan host 127.0.0.1 (localhost) dan port 5000 sebagai default
    # Debug True membantu melihat perubahan kode dan stacktrace saat development
    app.run(debug=True, host='127.0.0.1', port=5000)