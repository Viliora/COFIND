from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv
import time  # Tambahkan untuk penundaan
from datetime import datetime, timedelta
from huggingface_hub import InferenceClient

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS

# Configure Google Places API (prefer using .env for key)
GOOGLE_PLACES_API_KEY = os.getenv('GOOGLE_PLACES_API_KEY') or 'YOUR_API_KEY'

# Configure Hugging Face Inference API (gunakan env, jangan hardcode token)
HF_API_TOKEN = os.getenv('HF_API_TOKEN')  # Pastikan diset di environment (.env)
HF_MODEL = os.getenv('HF_MODEL', "meta-llama/Llama-3.1-8B-Instruct")  # default model

# Initialize Hugging Face Inference Client (optional)
hf_client = None
if HF_API_TOKEN:
    hf_client = InferenceClient(api_key=HF_API_TOKEN)
else:
    print("[WARNING] HF_API_TOKEN tidak diset. Endpoint LLM akan nonaktif.")

print(f"Using API Key: {GOOGLE_PLACES_API_KEY}")

# ============================================================================
# CACHING SYSTEM untuk LLM Context Data
# ============================================================================
# In-memory cache untuk menghindari repeated API calls
# Format: { 'location_name': { 'data': [...], 'timestamp': datetime, 'expires_at': datetime } }
COFFEE_SHOPS_CACHE = {}
CACHE_TTL_MINUTES = int(os.getenv('CACHE_TTL_MINUTES', 30))  # Default 30 menit

def get_cache_key(location_str):
    """Generate cache key dari location string (normalized)"""
    return location_str.lower().strip()

def is_cache_valid(cache_entry):
    """Check apakah cache masih valid (belum expired)"""
    if not cache_entry:
        return False
    return datetime.now() < cache_entry.get('expires_at', datetime.min)

def get_cached_coffee_shops(location_str):
    """Ambil data coffee shops dari cache jika masih valid"""
    cache_key = get_cache_key(location_str)
    cache_entry = COFFEE_SHOPS_CACHE.get(cache_key)
    
    if is_cache_valid(cache_entry):
        age_seconds = (datetime.now() - cache_entry['timestamp']).total_seconds()
        print(f"[CACHE HIT] Using cached data for '{location_str}' (age: {age_seconds:.0f}s)")
        return cache_entry['data']
    
    print(f"[CACHE MISS] No valid cache for '{location_str}'")
    return None

def set_cached_coffee_shops(location_str, data):
    """Simpan data coffee shops ke cache dengan TTL"""
    cache_key = get_cache_key(location_str)
    now = datetime.now()
    expires_at = now + timedelta(minutes=CACHE_TTL_MINUTES)
    
    COFFEE_SHOPS_CACHE[cache_key] = {
        'data': data,
        'timestamp': now,
        'expires_at': expires_at
    }
    print(f"[CACHE SET] Cached data for '{location_str}' (expires in {CACHE_TTL_MINUTES} min)")

def clear_cache(location_str=None):
    """Clear cache untuk lokasi tertentu atau semua cache"""
    if location_str:
        cache_key = get_cache_key(location_str)
        if cache_key in COFFEE_SHOPS_CACHE:
            del COFFEE_SHOPS_CACHE[cache_key]
            print(f"[CACHE CLEAR] Cleared cache for '{location_str}'")
    else:
        COFFEE_SHOPS_CACHE.clear()
        print("[CACHE CLEAR] Cleared all cache")
# ============================================================================

# Enable CORS for /api/*
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Root endpoint
@app.route('/')
def home():
    return jsonify({"message": "Welcome to COFIND API"})

# Test endpoint untuk debug
@app.route('/api/test', methods=['GET'])
def test_api():
    return jsonify({
        "status": "ok",
        "message": "Flask server is running",
        "timestamp": time.time(),
        "hf_client_ready": hf_client is not None,
        "cache_ttl_minutes": CACHE_TTL_MINUTES,
        "cached_locations": len(COFFEE_SHOPS_CACHE)
    })

# Endpoint untuk melihat status cache
@app.route('/api/cache/status', methods=['GET'])
def cache_status():
    """Endpoint untuk melihat status cache LLM context"""
    try:
        cache_info = []
        now = datetime.now()
        
        for location, entry in COFFEE_SHOPS_CACHE.items():
            age_seconds = (now - entry['timestamp']).total_seconds()
            expires_in_seconds = (entry['expires_at'] - now).total_seconds()
            
            cache_info.append({
                'location': location,
                'cached_at': entry['timestamp'].isoformat(),
                'expires_at': entry['expires_at'].isoformat(),
                'age_seconds': int(age_seconds),
                'expires_in_seconds': int(expires_in_seconds),
                'is_valid': is_cache_valid(entry),
                'data_size': len(entry['data'])
            })
        
        return jsonify({
            'status': 'success',
            'cache_ttl_minutes': CACHE_TTL_MINUTES,
            'total_cached_locations': len(COFFEE_SHOPS_CACHE),
            'cache_entries': cache_info
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Endpoint untuk clear cache
@app.route('/api/cache/clear', methods=['POST'])
def clear_cache_endpoint():
    """Endpoint untuk manual clear cache"""
    try:
        data = request.get_json() or {}
        location = data.get('location')
        
        if location:
            clear_cache(location)
            message = f"Cache cleared for location: {location}"
        else:
            clear_cache()
            message = "All cache cleared"
        
        return jsonify({
            'status': 'success',
            'message': message,
            'remaining_cached_locations': len(COFFEE_SHOPS_CACHE)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# DEBUG Endpoint untuk melihat raw review context
@app.route('/api/debug/reviews-context', methods=['GET'])
def debug_reviews_context():
    """Debug endpoint untuk melihat review context yang dikirim ke LLM"""
    try:
        location = request.args.get('location', 'Pontianak')
        max_shops = int(request.args.get('max_shops', 5))
        
        print(f"[DEBUG] Fetching reviews context for: {location}")
        context = _fetch_coffeeshops_with_reviews_context(location, use_cache=False, max_shops=max_shops)
        
        return jsonify({
            'status': 'success',
            'location': location,
            'max_shops': max_shops,
            'context_length': len(context),
            'context_preview': context[:1000],  # First 1000 chars
            'full_context': context  # Full context untuk debug
        })
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }), 500

# Endpoint untuk mencari coffee shop menggunakan Google Places API
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
            'fields': 'place_id,name,rating,formatted_phone_number,formatted_address,geometry,photos,reviews,opening_hours,price_level,website,user_ratings_total',
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

# Helper function untuk fetch coffee shops dengan REVIEWS untuk LLM context
def _fetch_coffeeshops_with_reviews_context(location_str, use_cache=True, max_shops=10):
    """
    Fetch coffee shops DENGAN REVIEWS dari Google Places API untuk LLM context.
    Reviews digunakan sebagai bukti/evidence dalam rekomendasi.
    
    Args:
        location_str: Nama lokasi untuk search (e.g., "Pontianak")
        use_cache: Gunakan cache jika tersedia (default: True)
        max_shops: Maksimal jumlah coffee shops yang di-fetch detail (default: 10)
    
    Returns:
        String berisi daftar coffee shops dengan reviews untuk LLM context
    """
    try:
        # Step 1: Check cache terlebih dahulu (jika enabled)
        cache_key_with_reviews = f"{location_str}_with_reviews"
        if use_cache:
            cached_context = get_cached_coffee_shops(cache_key_with_reviews)
            if cached_context:
                return cached_context
        
        print(f"[PLACES+REVIEWS] Fetching coffee shops with reviews for: {location_str}")
        
        # Step 2: Text Search untuk mendapat coffee shops di lokasi
        base_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            'query': f'coffee shop {location_str}',
            'language': 'id',
            'key': GOOGLE_PLACES_API_KEY
        }
        
        response = requests.get(base_url, params=params)
        data = response.json()
        
        if data.get('status') != 'OK' or not data.get('results'):
            print(f"[PLACES+REVIEWS] No results found for location: {location_str}")
            return "Tidak ada data coffee shop yang ditemukan untuk lokasi ini."
        
        all_shops = data.get('results', [])[:max_shops]  # Ambil max_shops pertama
        print(f"[PLACES+REVIEWS] Found {len(all_shops)} coffee shops, fetching details...")
        
        # Step 3: Fetch details dengan reviews untuk setiap coffee shop
        context_lines = [
            f"DAFTAR COFFEE SHOP DI {location_str.upper()} DENGAN REVIEW",
            f"Total: {len(all_shops)} coffee shop pilihan terbaik\n"
        ]
        
        for i, shop in enumerate(all_shops, 1):
            place_id = shop.get('place_id')
            name = shop.get('name', 'Unknown')
            
            print(f"[PLACES+REVIEWS] Fetching details for {i}/{len(all_shops)}: {name}")
            
            # Fetch details untuk mendapat reviews
            details_result = get_place_details(place_id)
            
            if details_result.get('status') == 'success':
                detail = details_result.get('data', {})
                
                rating = detail.get('rating', shop.get('rating', 'N/A'))
                total_ratings = detail.get('user_ratings_total', shop.get('user_ratings_total', 0))
                address = detail.get('formatted_address', shop.get('formatted_address', 'No address'))
                price_level = detail.get('price_level', shop.get('price_level'))
                reviews = detail.get('reviews', [])
                
                # Generate Google Maps URL - gunakan place_id dari detail atau dari shop
                actual_place_id = detail.get('place_id', place_id)
                maps_url = f"https://www.google.com/maps/place/?q=place_id:{actual_place_id}"
                
                # Format entry dengan reviews
                context_lines.append(f"{i}. {name}")
                context_lines.append(f"   • Rating: {rating}/5.0 ({total_ratings} reviews)")
                
                if price_level:
                    price_indicator = '💰' * price_level
                    context_lines.append(f"   • Harga: {price_indicator} (Level {price_level}/4)")
                
                context_lines.append(f"   • Alamat: {address}")
                context_lines.append(f"   • Google Maps: {maps_url}")
                
                # REVIEWS - Ambil 3-5 review terbaik sebagai bukti
                if reviews:
                    context_lines.append(f"   • Review dari Pengunjung:")
                    review_count = 0
                    for review in reviews[:5]:  # Max 5 reviews per coffee shop
                        review_text = review.get('text', '').strip()
                        if review_text and len(review_text) > 20:  # Min 20 karakter
                            review_rating = review.get('rating', 0)
                            author_name = review.get('author_name', 'Anonim')
                            
                            # Truncate review yang terlalu panjang
                            if len(review_text) > 200:
                                review_text = review_text[:197] + "..."
                            
                            context_lines.append(f"     - {author_name} ({review_rating}⭐): \"{review_text}\"")
                            review_count += 1
                    
                    if review_count == 0:
                        context_lines.append(f"     - (Belum ada review dengan teks)")
                else:
                    context_lines.append(f"   • Review: Belum ada review tersedia")
                
                context_lines.append("")  # Separator
            else:
                # Fallback jika detail gagal di-fetch
                context_lines.append(f"{i}. {name}")
                context_lines.append(f"   • Rating: {shop.get('rating', 'N/A')}/5.0")
                context_lines.append(f"   • Alamat: {shop.get('formatted_address', 'No address')}")
                context_lines.append(f"   • Review: Tidak dapat diambil")
                context_lines.append("")
            
            # Delay untuk menghindari rate limit
            if i < len(all_shops):
                time.sleep(0.5)
        
        context = "\n".join(context_lines)
        
        # Step 4: Simpan ke cache
        set_cached_coffee_shops(cache_key_with_reviews, context)
        
        print(f"[PLACES+REVIEWS] Context prepared: {len(all_shops)} shops with reviews, {len(context)} characters")
        return context
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[PLACES+REVIEWS] Error: {str(e)}")
        print(f"[PLACES+REVIEWS] Traceback: {error_detail}")
        return f"Error mengambil data coffee shop dengan review: {str(e)}"

# Helper function untuk fetch coffee shops dari Google Places API sebagai context untuk LLM
def _fetch_coffeeshops_context(location_str, use_cache=True):
    """
    Fetch coffee shops dari Google Places API dan format sebagai context untuk LLM.
    Ini memastikan LLM memberikan rekomendasi berdasarkan data REAL, bukan hallucination.
    
    Args:
        location_str: Nama lokasi untuk search (e.g., "Pontianak")
        use_cache: Gunakan cache jika tersedia (default: True)
    
    Returns:
        String berisi daftar coffee shops yang diformat untuk LLM context
    """
    try:
        # Step 1: Check cache terlebih dahulu (jika enabled)
        if use_cache:
            cached_context = get_cached_coffee_shops(location_str)
            if cached_context:
                return cached_context
        
        print(f"[PLACES] Fetching coffee shops for location: {location_str}")
        
        # Step 2: Text Search untuk mendapat coffee shops di lokasi
        base_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            'query': f'coffee shop {location_str}',
            'language': 'id',
            'key': GOOGLE_PLACES_API_KEY
        }
        
        all_shops = []
        page_count = 0
        max_pages = 1  # Ambil 1 halaman = 20 results. Set ke 2-3 untuk lebih banyak data.
        
        # Step 3: Fetch data dengan pagination support
        while page_count < max_pages:
            response = requests.get(base_url, params=params)
            data = response.json()
            
            if data.get('status') == 'OK':
                results = data.get('results', [])
                all_shops.extend(results)
                page_count += 1
                
                print(f"[PLACES] Page {page_count}: fetched {len(results)} coffee shops")
                
                # Check jika ada next page
                next_page_token = data.get('next_page_token')
                if next_page_token and page_count < max_pages:
                    # Google memerlukan delay sebelum next_page_token valid
                    time.sleep(2)
                    params['pagetoken'] = next_page_token
                else:
                    break
            else:
                error_msg = data.get('error_message', data.get('status'))
                print(f"[PLACES] API error: {error_msg}")
                break
        
        # Step 4: Validasi hasil
        if not all_shops:
            print(f"[PLACES] No results found for location: {location_str}")
            return "Tidak ada data coffee shop yang ditemukan untuk lokasi ini."
        
        # Step 5: Format coffee shops menjadi context string untuk LLM
        # Sertakan informasi lebih detail untuk rekomendasi yang lebih baik
        context_lines = [
            f"DAFTAR COFFEE SHOP DI {location_str.upper()}",
            f"Total: {len(all_shops)} coffee shop ditemukan\n"
        ]
        
        for i, shop in enumerate(all_shops, 1):
            name = shop.get('name', 'Unknown')
            rating = shop.get('rating', 'N/A')
            total_ratings = shop.get('user_ratings_total', 0)
            address = shop.get('formatted_address', 'No address')
            price_level = shop.get('price_level')
            business_status = shop.get('business_status', 'UNKNOWN')
            types = shop.get('types', [])
            
            # Format entry
            context_lines.append(f"{i}. {name}")
            context_lines.append(f"   • Rating: {rating}/5.0 ({total_ratings} reviews)")
            
            # Price level indicator
            if price_level:
                price_indicator = '💰' * price_level
                context_lines.append(f"   • Harga: {price_indicator} (Level {price_level}/4)")
            
            # Status
            status_map = {
                'OPERATIONAL': '✅ Buka',
                'CLOSED_TEMPORARILY': '⏸️ Tutup Sementara',
                'CLOSED_PERMANENTLY': '❌ Tutup Permanen'
            }
            status_text = status_map.get(business_status, business_status)
            context_lines.append(f"   • Status: {status_text}")
            
            # Address
            context_lines.append(f"   • Alamat: {address}")
            
            # Types/Categories (ambil yang relevan saja)
            relevant_types = [t for t in types if t not in ['point_of_interest', 'establishment', 'food', 'store']]
            if relevant_types:
                types_str = ', '.join(relevant_types[:3])  # Max 3 types
                context_lines.append(f"   • Kategori: {types_str}")
            
            context_lines.append("")  # Empty line sebagai separator
        
        context = "\n".join(context_lines)
        
        # Step 6: Simpan ke cache untuk request berikutnya
        set_cached_coffee_shops(location_str, context)
        
        print(f"[PLACES] Context prepared: {len(all_shops)} shops, {len(context)} characters")
        return context
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[PLACES] Error fetching context: {str(e)}")
        print(f"[PLACES] Traceback: {error_detail}")
        return f"Error mengambil data coffee shop: {str(e)}"

# Endpoint untuk LLM Text Generation & Analysis menggunakan Hugging Face
@app.route('/api/llm/analyze', methods=['POST'])
def llm_analyze():
    """
    Endpoint untuk menganalisis user input dengan context dari Google Places API
    
    Request JSON:
    {
        "text": "user input untuk dianalisis",
        "task": "analyze" | "summarize" | "recommend" (optional, default: analyze),
        "location": "lokasi untuk search coffee shop" (optional)
    }
    """
    try:
        if hf_client is None:
            return jsonify({
                'status': 'error',
                'message': 'HF_API_TOKEN tidak dikonfigurasi. LLM analyze endpoint nonaktif.'
            }), 503
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing required field: text'
            }), 400
        
        user_text = data.get('text', '').strip()
        task = data.get('task', 'analyze').lower()
        location = data.get('location', 'Pontianak')  # Default location
        
        if not user_text:
            return jsonify({
                'status': 'error',
                'message': 'Text cannot be empty'
            }), 400
        
        # Step 1: Fetch coffee shops DENGAN REVIEWS dari Google Places API
        print(f"[LLM] Fetching coffee shops WITH REVIEWS from Places API for location: {location}")
        places_context = _fetch_coffeeshops_with_reviews_context(location, use_cache=True, max_shops=10)
        
        # Debug: Print sample reviews untuk verify data
        print(f"[LLM] Context preview (first 500 chars):")
        print(places_context[:500] if len(places_context) > 500 else places_context)
        print(f"[LLM] Total context length: {len(places_context)} characters")
        
        # Step 2: Build system prompt dengan context REVIEWS untuk bukti rekomendasi
        system_prompt = f"""Anda adalah asisten rekomendasi coffee shop yang ahli dan profesional. Memberikan jawaban menggunakan data dengan bukti nyata dari review yang ada di places api. Jika anda tidak yakin atau data tidak ada, jawab: "Saya tidak menemukan informasi yang sesuai. jangan menambahkan output jika tidak ada "

DATA COFFEE SHOP DI {location.upper()} DENGAN REVIEW PENGUNJUNG LENGKAP DARI GOOGLE PLACES:
{places_context}

INSTRUKSI WAJIB (HARUS DIIKUTI):
1. Berikan HANYA rekomendasi coffee shop yang ADA dalam data di atas
2. WAJIB KUTIP REVIEW PERSIS dari data di atas - COPY PASTE review asli
3. Format kutipan: "Teks review ASLI dari data" - Nama User ASLI (Rating⭐)
4. MINIMAL 2 review per coffee shop yang direkomendasikan
5. DILARANG mengubah, meringkas, atau membuat review sendiri
6. DILARANG membuat nama user palsu (gunakan nama ASLI dari data)
7. Review harus WORD-FOR-WORD dari data yang diberikan
8. Berikan 2-3 rekomendasi terbaik
9. Gunakan bahasa Indonesia yang ramah

CARA MENGUTIP REVIEW YANG BENAR:
- Lihat data di atas, cari bagian "Review dari Pengunjung:"
- COPY PASTE teks review PERSIS seperti di data
- Gunakan nama user PERSIS seperti di data
- Sertakan rating PERSIS seperti di data

CONTOH CARA KUTIP (jika di data tertulis):
Data: "- John Doe (5⭐): "Tempatnya sangat nyaman untuk bekerja""
Kutip: • "Tempatnya sangat nyaman untuk bekerja" - John Doe (5⭐)

PENTING: 
- Review adalah kutipan LANGSUNG dari Google Places API
- JANGAN ubah atau ringkas review
- JANGAN buat nama user sendiri
- Kutip PERSIS seperti di data!"""

        # Step 3: Extract keywords dari user input untuk highlighting
        keywords = [kw.strip().lower() for kw in user_text.split(',') if kw.strip()]
        keywords_display = ', '.join([f'"{kw}"' for kw in keywords])
        
        # Step 4: Build user prompt khusus untuk KEYWORD-BASED RECOMMENDATION dengan BOLD
        if task == 'summarize':
            user_content = f"""Kata kunci preferensi user:
{user_text}

Ringkaskan preferensi ini dalam 2-3 kalimat, lalu berikan rekomendasi coffee shop dengan BUKTI REVIEW LENGKAP (nama user + isi komentar)."""
        elif task == 'recommend':
            user_content = f"""KATA KUNCI PREFERENSI saya (keyword-based):
{user_text}

Berikan 2-3 rekomendasi coffee shop terbaik yang MATCH dengan kata kunci di atas.

FORMAT WAJIB untuk setiap rekomendasi:
🏆 [Nama Coffee Shop] - Rating X/5.0
📍 Alamat: [alamat lengkap]
🗺️ Google Maps: [URL dari data]
💰 Harga: [level harga]

✅ Mengapa Cocok dengan Kata Kunci Anda:
[Jelaskan detail kenapa coffee shop ini cocok. WAJIB gunakan **bold** untuk kata kunci yang match.]
Contoh: "Coffee shop ini memiliki **wifi bagus** dan **terminal banyak** di setiap meja."

📝 Bukti dari Review Pengunjung:
WAJIB kutip MINIMAL 2 review lengkap. Jika review menyebutkan kata kunci, gunakan **bold** untuk highlight:
• "Review dengan **kata kunci yang match**" - Nama Customer (X⭐)

INSTRUKSI BOLD/HIGHLIGHT:
1. Jika review atau penjelasan menyebutkan kata kunci user ({keywords_display}), gunakan **bold**
2. Format: **kata kunci** (diapit dua asterisk)
3. Match bisa partial (contoh: "wifi" match dengan "wifi bagus", "wifi kencang")
4. Case insensitive (wifi = Wifi = WIFI)

CONTOH CORRECT (dengan keyword highlighting):
✅ Mengapa Cocok:
"Coffee shop ini sangat sesuai karena memiliki **wifi cepat** dan **terminal banyak** di setiap meja..."

📝 Bukti dari Review:
• "Tempatnya nyaman, **wifi kencang** dan **colokan di setiap meja**!" - Sarah (5⭐)
• "**Smoking area** tersedia dan **AC dingin**" - Budi (4⭐)

PENTING:
- Kutip review PERSIS dari data
- Bold HANYA untuk kata yang MATCH dengan keyword user
- Minimal 2 review per rekomendasi"""
        else:  # analyze (default)
            user_content = f"""Kata kunci preferensi: {user_text}

Berikan rekomendasi coffee shop dengan BUKTI REVIEW. Gunakan **bold** untuk highlight kata kunci yang match."""
        
        # Step 4: Call Hugging Face Inference API dengan context
        print(f"[LLM] Calling HF API with task: {task}")
        print(f"[LLM] Model: {HF_MODEL}")
        
        response = hf_client.chat.completions.create(
            model=HF_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            max_tokens=1024,  # Increased untuk review lengkap (dari 256)
            temperature=0.5,  # Lower untuk lebih factual (dari 0.6)
            top_p=0.9
        )
        
        print(f"[LLM] Response received successfully")
        generated_text = response.choices[0].message.content
        print(f"[LLM] Generated text: {generated_text[:100]}")
        
        return jsonify({
            'status': 'success',
            'task': task,
            'input': user_text,
            'analysis': generated_text,
            'timestamp': time.time()
        }), 200
    
    except Exception as e:
        import traceback
        error_message = f"LLM Analysis Error: {str(e)}"
        traceback_str = traceback.format_exc()
        print(f"[ERROR] {error_message}")
        print(f"[TRACEBACK]\n{traceback_str}")
        return jsonify({
            'status': 'error',
            'message': error_message,
            'error_details': traceback_str
        }), 500

# Endpoint untuk LLM Chat - lebih interactive dengan context dari Places API
@app.route('/api/llm/chat', methods=['POST'])
def llm_chat():
    """
    Endpoint untuk chat interaktif dengan Llama tentang coffee shops
    
    Request JSON:
    {
        "message": "user message",
        "context": "optional context",
        "location": "lokasi untuk search coffee shop" (optional, default: Pontianak)
    }
    """
    try:
        if hf_client is None:
            return jsonify({
                'status': 'error',
                'message': 'HF_API_TOKEN tidak dikonfigurasi. LLM chat endpoint nonaktif.'
            }), 503
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing required field: message'
            }), 400
        
        user_message = data.get('message', '').strip()
        conversation_context = data.get('context', '').strip()
        location = data.get('location', 'Pontianak')
        
        if not user_message:
            return jsonify({
                'status': 'error',
                'message': 'Message cannot be empty'
            }), 400
        
        # Fetch coffee shops data untuk context
        places_context = _fetch_coffeeshops_context(location)
        
        # Build system prompt dengan real coffee shop data
        system_message = f"""Anda adalah AI assistant expert yang membantu user menemukan coffee shop terbaik.

DATA COFFEE SHOP YANG TERSEDIA DI {location.upper()}:
{places_context}

Gunakan data coffee shop di atas untuk memberikan rekomendasi yang SPESIFIK dan AKURAT.
Jangan membuat atau menyebutkan coffee shop yang tidak ada dalam data di atas.
Jadilah ramah, helpful, dan memberikan alasan detail untuk setiap rekomendasi."""
        
        # Build messages untuk chat
        messages = [
            {"role": "system", "content": system_message}
        ]
        
        # Add conversation context jika ada (dari chat history sebelumnya)
        if conversation_context:
            messages.append({"role": "assistant", "content": conversation_context})
        
        # Add user message
        messages.append({"role": "user", "content": user_message})
        
        # Call Hugging Face Inference API dengan chat.completions format
        print(f"[CHAT] Calling HF API for chat at location: {location}")
        print(f"[CHAT] Model: {HF_MODEL}")
        print(f"[CHAT] Message: {user_message[:100]}")
        
        response = hf_client.chat.completions.create(
            model=HF_MODEL,
            messages=messages,
            max_tokens=512,
            temperature=0.7,
            top_p=0.9
        )
        
        print(f"[CHAT] Response received successfully")
        generated_text = response.choices[0].message.content
        print(f"[CHAT] Generated reply: {generated_text[:100]}")
        
        return jsonify({
            'status': 'success',
            'message': user_message,
            'reply': generated_text,
            'timestamp': time.time()
        }), 200
    
    except Exception as e:
        import traceback
        error_message = f"LLM Chat Error: {str(e)}"
        traceback_str = traceback.format_exc()
        print(f"[ERROR] {error_message}")
        print(f"[TRACEBACK]\n{traceback_str}")
        return jsonify({
            'status': 'error',
            'message': error_message,
            'error_details': traceback_str
        }), 500

if __name__ == '__main__':
    # Jalankan app secara langsung untuk pengembangan
    # Gunakan host 0.0.0.0 untuk bind ke semua interface dan port 5000 sebagai default
    # Debug False untuk menghindari restart cycle saat development
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
