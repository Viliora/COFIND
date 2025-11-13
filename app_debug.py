from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv
import time  # Tambahkan untuk penundaan

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

# Debug endpoint - untuk melihat raw data dari Google Places API
@app.route('/api/debug/coffeeshops/detail/<place_id>', methods=['GET'])
def debug_coffee_shop_detail(place_id):
    """
    Debug endpoint untuk melihat raw response dari Google Places API
    Gunakan untuk inspect berapa banyak reviews yang dikirim Google
    
    URL: http://localhost:5000/api/debug/coffeeshops/detail/{place_id}
    """
    try:
        base_url = "https://maps.googleapis.com/maps/api/place/details/json"
        
        params = {
            'place_id': place_id,
            'fields': 'name,rating,formatted_phone_number,formatted_address,geometry,photos,reviews,opening_hours,price_level,website',
            'language': 'id',
            'reviews_sort': 'newest',
            'key': GOOGLE_PLACES_API_KEY
        }

        print(f"\n[DEBUG] Making request to Google Places API Details")
        print(f"[DEBUG] Place ID: {place_id}")
        print(f"[DEBUG] URL: {base_url}")
        
        response = requests.get(base_url, params=params)
        data = response.json()

        if data.get('status') == 'OK':
            result = data.get('result', {})
            
            # Extract review info
            reviews = result.get('reviews', [])
            reviews_with_text = [r for r in reviews if (r.get('text', '').strip())]
            
            debug_info = {
                'status': 'success',
                'place_name': result.get('name'),
                'place_id': place_id,
                'google_response_status': data.get('status'),
                'total_reviews_from_google': len(reviews),
                'reviews_with_text': len(reviews_with_text),
                'message': f'Google returned {len(reviews)} reviews total, {len(reviews_with_text)} with text content',
                'all_reviews': reviews,  # Raw data dari Google
                'reviews_with_text_only': reviews_with_text,  # Filtered
            }
            
            print(f"[DEBUG] Total reviews from Google: {len(reviews)}")
            print(f"[DEBUG] Reviews with text: {len(reviews_with_text)}")
            
            return jsonify(debug_info)
        else:
            return jsonify({
                'status': 'error',
                'message': f"Google Places API error: {data.get('status')}",
                'error_details': data.get('error_message'),
                'full_response': data
            }), 400
    except Exception as e:
        error_message = f"Error: {str(e)}"
        print(f"[DEBUG] ERROR: {error_message}")
        return jsonify({
            'status': 'error',
            'message': error_message
        }), 500

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

        coffee_shops = []  # Data coffee shop yang akan dikirim ke frontend
        while True:
            print(f"Making request to Google Places API: {base_url} with params {params}")
            response = requests.get(base_url, params=params)
            data = response.json()

            print(f"Response status: {data.get('status')}, error_message: {data.get('error_message')}")

            if data.get('status') == 'OK':
                results = data.get('results', [])
                for place in results:
                    coffee_shop = {
                        'place_id': place.get('place_id'),
                        'name': place.get('name'),
                        'address': place.get('vicinity') or place.get('formatted_address'),
                        'rating': place.get('rating'),
                        'user_ratings_total': place.get('user_ratings_total'),
                        'location': place.get('geometry', {}).get('location'),
                        'business_status': place.get('business_status'),
                        'price_level': place.get('price_level'),
                        'photos': []  # Start with empty list for photos
                    }

                    # Cek apakah ada foto dan ambil foto URL
                    if 'photos' in place:
                        for photo in place['photos']:
                            photo_reference = photo.get('photo_reference')
                            if photo_reference:
                                # Ambil URL foto menggunakan fungsi get_place_photo
                                photo_url = get_place_photo(photo_reference)
                                if photo_url:
                                    coffee_shop['photos'].append(photo_url)

                    coffee_shops.append(coffee_shop)

                # Cek apakah ada halaman berikutnya
                next_page_token = data.get('next_page_token')
                if next_page_token:
                    # Menambahkan penundaan sebelum mengambil halaman berikutnya
                    time.sleep(2)  # Delay untuk memastikan next_page_token valid
                    params['pagetoken'] = next_page_token  # Gunakan token untuk halaman berikutnya
                else:
                    break  # Jika tidak ada halaman berikutnya, hentikan pengulangan
            else:
                error_message = f"Google Places API error: {data.get('status')} - {data.get('error_message', 'Unknown error')}"
                print(error_message)
                return jsonify({'status': 'error', 'message': error_message}), 400

        return jsonify({'status': 'success', 'data': coffee_shops})

    except Exception as e:
        error_message = f"Error: {str(e)}"
        print(error_message)
        return jsonify({'status': 'error', 'message': error_message}), 500


# Flask - Endpoint untuk mengambil detail tempat berdasarkan place_id
@app.route('/api/coffeeshops/detail/<place_id>', methods=['GET'])
def get_coffee_shop_detail(place_id):
    try:
        # Memanggil fungsi untuk mengambil detail berdasarkan place_id
        coffee_shop_details = get_place_details(place_id)  # Fungsi ini memanggil Places Details API
        if coffee_shop_details.get('status') == 'success':
            return jsonify(coffee_shop_details)
        else:
            return jsonify({'status': 'error', 'message': 'Coffee shop details not found'}), 404
    except Exception as e:
        error_message = f"Error: {str(e)}"
        print(error_message)
        return jsonify({'status': 'error', 'message': error_message}), 500

def get_place_details(place_id):
    try:
        base_url = "https://maps.googleapis.com/maps/api/place/details/json"
        
        # Menggunakan place_id untuk mendapatkan detail tempat
        params = {
            'place_id': place_id,
            'fields': 'name,rating,formatted_phone_number,formatted_address,geometry,photos,reviews,opening_hours,price_level,website',
            'language': 'id',  # tampilkan data dalam Bahasa Indonesia jika tersedia
            'reviews_sort': 'newest',  # urutkan ulasan dari yang terbaru (jika tersedia)
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
            return {
                'status': 'error',
                'message': f"Google Places API error: {data.get('status')}"
            }
    except Exception as e:
        error_message = f"Error: {str(e)}"
        print(error_message)
        return {
            'status': 'error',
            'message': error_message
        }

# Fungsi untuk mendapatkan foto tempat dari Google Places API
def get_place_photo(photo_reference):
    base_url = "https://maps.googleapis.com/maps/api/place/photo"
    params = {
        'maxwidth': 400,  # Menentukan lebar foto
        'photo_reference': photo_reference,  # Gunakan photo_reference dari respons API
        'key': GOOGLE_PLACES_API_KEY  # Gunakan API Key yang valid
    }
    response = requests.get(base_url, params=params)
    if response.status_code == 200:
        return response.url  # Kembalikan URL foto
    else:
        return None  # Jika gagal, kembalikan None

if __name__ == '__main__':
    # Jalankan app secara langsung untuk pengembangan
    # Gunakan host 127.0.0.1 (localhost) dan port 5000 sebagai default
    # Debug True membantu melihat perubahan kode dan stacktrace saat development
    app.run(debug=True, host='127.0.0.1', port=5000)
