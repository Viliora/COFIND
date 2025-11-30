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
# CACHING SYSTEM DISABLED - Using direct API calls
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
        "hf_client_ready": hf_client is not None
    })

# Cache endpoints removed - caching disabled

# DEBUG Endpoint untuk melihat raw pagination response
@app.route('/api/debug/pagination', methods=['GET'])
def debug_pagination():
    """Debug endpoint untuk melihat bagaimana pagination bekerja"""
    try:
        lat = request.args.get('lat', type=float, default=-0.026330)
        lng = request.args.get('lng', type=float, default=109.342506)
        
        base_url = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json'
        params = {
            'location': f"{lat},{lng}",
            'radius': '5000',
            'type': 'cafe',
            'keyword': 'coffee',
            'key': GOOGLE_PLACES_API_KEY
        }
        
        all_pages = []
        page_number = 1
        
        while page_number <= 3:  # Max 3 pages
            print(f"[DEBUG PAGINATION] Fetching page {page_number}")
            response = requests.get(base_url, params=params)
            data = response.json()
            
            page_info = {
                'page_number': page_number,
                'status': data.get('status'),
                'results_count': len(data.get('results', [])),
                'has_next_page': 'next_page_token' in data,
                'next_page_token': data.get('next_page_token', None),
                'shop_names': [r.get('name') for r in data.get('results', [])]
            }
            
            all_pages.append(page_info)
            
            # Check for next page
            next_page_token = data.get('next_page_token')
            if next_page_token and page_number < 3:
                time.sleep(2)
                params['pagetoken'] = next_page_token
                page_number += 1
            else:
                break
        
        return jsonify({
            'status': 'success',
            'total_pages': len(all_pages),
            'total_shops': sum(p['results_count'] for p in all_pages),
            'pages': all_pages
        })
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }), 500

# DEBUG Endpoint untuk melihat raw review context
@app.route('/api/debug/reviews-context', methods=['GET'])
def debug_reviews_context():
    """Debug endpoint untuk melihat review context yang dikirim ke LLM"""
    try:
        location = request.args.get('location', 'Pontianak')
        max_shops = int(request.args.get('max_shops', 5))
        
        print(f"[DEBUG] Fetching reviews context for: {location}")
        context = _fetch_coffeeshops_with_reviews_context(location, max_shops=max_shops)
        
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
        page_number = 1
        while True:
            print(f"\n[PAGE {page_number}] Making request to Google Places API: {base_url}")
            print(f"[PAGE {page_number}] Params: {params}")
            response = requests.get(base_url, params=params)
            data = response.json()

            print(f"[PAGE {page_number}] Response status: {data.get('status')}, error_message: {data.get('error_message')}")

            if data.get('status') == 'OK':
                results = data.get('results', [])
                print(f"[PAGE {page_number}] Found {len(results)} coffee shops")
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

                    # Cek apakah ada foto dan ambil foto URL (HANYA 1 FOTO untuk optimasi)
                    if 'photos' in place and len(place['photos']) > 0:
                        # Ambil hanya foto pertama untuk menghindari socket exhaustion
                        photo = place['photos'][0]
                        photo_reference = photo.get('photo_reference')
                        if photo_reference:
                            try:
                                # Ambil URL foto dengan HD quality (1200px) untuk hero swiper
                                photo_url = get_place_photo(photo_reference, maxwidth=1200)
                                if photo_url:
                                    coffee_shop['photos'].append(photo_url)
                            except Exception as photo_error:
                                # Jika gagal ambil foto, skip saja (tidak critical)
                                print(f"[WARNING] Failed to fetch photo for {coffee_shop['name']}: {photo_error}")
                                pass

                    coffee_shops.append(coffee_shop)

                # Cek apakah ada halaman berikutnya
                next_page_token = data.get('next_page_token')
                if next_page_token:
                    print(f"[PAGE {page_number}] Next page token found: {next_page_token[:20]}...")
                    print(f"[PAGE {page_number}] Total coffee shops so far: {len(coffee_shops)}")
                    # Menambahkan penundaan sebelum mengambil halaman berikutnya
                    time.sleep(2)  # Delay untuk memastikan next_page_token valid
                    params['pagetoken'] = next_page_token  # Gunakan token untuk halaman berikutnya
                    page_number += 1
                else:
                    print(f"[PAGE {page_number}] No more pages. Total coffee shops: {len(coffee_shops)}")
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
            'fields': 'place_id,name,rating,formatted_phone_number,formatted_address,geometry,photos,reviews,opening_hours,price_level,website,user_ratings_total,business_status',
            'language': 'id',  # tampilkan data dalam Bahasa Indonesia jika tersedia
            'reviews_sort': 'newest',  # urutkan ulasan dari yang terbaru (jika tersedia)
            'key': GOOGLE_PLACES_API_KEY
        }

        print(f"[DETAIL] Making request to Places Details API for place_id: {place_id}")
        response = requests.get(base_url, params=params)
        data = response.json()

        if data.get('status') == 'OK':
            result = data.get('result', {})
            
            # PENTING: Konversi photo_reference menjadi URL foto
            photo_urls = []
            if 'photos' in result and len(result['photos']) > 0:
                print(f"[DETAIL] Found {len(result['photos'])} photos, converting to URLs...")
                # Ambil hingga 5 foto pertama dengan HD quality
                for photo in result['photos'][:5]:
                    photo_reference = photo.get('photo_reference')
                    if photo_reference:
                        try:
                            # HD quality (1200px) untuk detail page
                            photo_url = get_place_photo(photo_reference, maxwidth=1200)
                            if photo_url:
                                photo_urls.append(photo_url)
                                print(f"[DETAIL] Photo URL added (HD): {photo_url[:50]}...")
                        except Exception as photo_error:
                            print(f"[WARNING] Failed to fetch photo: {photo_error}")
                            pass
            
            # Replace photos dengan URL yang sudah dikonversi
            result['photos'] = photo_urls
            print(f"[DETAIL] Total photos converted: {len(photo_urls)}")
            
            return {
                'status': 'success',
                'data': result
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

# Session untuk reuse connections (menghindari socket exhaustion)
photo_session = requests.Session()

# Fungsi untuk mendapatkan foto tempat dari Google Places API
def get_place_photo(photo_reference, maxwidth=1200):
    """
    Get photo URL from Google Places API
    
    Args:
        photo_reference: Photo reference dari Places API
        maxwidth: Maximum width untuk foto (default 1200 untuk HD quality)
                  Options: 400 (low), 800 (medium), 1200 (high), 1600 (very high)
    
    Returns:
        URL foto atau None jika gagal
    """
    base_url = "https://maps.googleapis.com/maps/api/place/photo"
    params = {
        'maxwidth': maxwidth,  # HD quality untuk hero images
        'photo_reference': photo_reference,
        'key': GOOGLE_PLACES_API_KEY
    }
    try:
        # Gunakan session untuk reuse connection
        response = photo_session.get(base_url, params=params, timeout=10)
        if response.status_code == 200:
            return response.url  # Kembalikan URL foto
        else:
            return None  # Jika gagal, kembalikan None
    except Exception as e:
        print(f"[WARNING] Photo fetch error: {e}")
        return None

# Helper function untuk fetch coffee shops dengan REVIEWS untuk LLM context
def _fetch_coffeeshops_with_reviews_context(location_str, max_shops=30):
    """
    Fetch coffee shops DENGAN REVIEWS dari Google Places API untuk LLM context.
    Reviews digunakan sebagai bukti/evidence dalam rekomendasi.
    
    Args:
        location_str: Nama lokasi untuk search (e.g., "Pontianak")
        max_shops: Maksimal jumlah coffee shops yang di-fetch detail (default: 30)
    
    Returns:
        String berisi daftar coffee shops dengan reviews untuk LLM context
    """
    try:
        print(f"[PLACES+REVIEWS] Fetching coffee shops with reviews for: {location_str}")
        
        # Step 2: Text Search untuk mendapat coffee shops di lokasi (dengan pagination)
        base_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            'query': f'coffee shop {location_str}',
            'language': 'id',
            'key': GOOGLE_PLACES_API_KEY
        }
        
        all_shops = []
        page_count = 0
        max_pages = 3  # Google Places API max 3 pages (20 results per page = 60 total)
        
        while page_count < max_pages and len(all_shops) < max_shops:
            response = requests.get(base_url, params=params)
            data = response.json()
            
            if data.get('status') != 'OK':
                print(f"[PLACES+REVIEWS] API status: {data.get('status')}")
                break
            
            results = data.get('results', [])
            if not results:
                break
            
            all_shops.extend(results)
            page_count += 1
            print(f"[PLACES+REVIEWS] Page {page_count}: Got {len(results)} shops, total: {len(all_shops)}")
            
            # Check if there's a next page
            next_page_token = data.get('next_page_token')
            if not next_page_token or len(all_shops) >= max_shops:
                break
            
            # Google requires a short delay before using next_page_token
            time.sleep(2)
            params = {
                'pagetoken': next_page_token,
                'key': GOOGLE_PLACES_API_KEY
            }
        
        if not all_shops:
            print(f"[PLACES+REVIEWS] No results found for location: {location_str}")
            return "Tidak ada data coffee shop yang ditemukan untuk lokasi ini."
        
        # Limit to max_shops
        all_shops = all_shops[:max_shops]
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
                
                # Format entry dengan reviews (TANPA price level)
                context_lines.append(f"{i}. {name}")
                context_lines.append(f"   • Rating: {rating}/5.0 ({total_ratings} reviews)")
                context_lines.append(f"   • Alamat: {address}")
                context_lines.append(f"   • Google Maps: {maps_url}")
                
                # REVIEWS - Ambil 3 review terbaik sebagai bukti (dikurangi untuk efisiensi)
                if reviews:
                    context_lines.append(f"   • Review dari Pengunjung:")
                    review_count = 0
                    for review in reviews[:3]:  # Max 3 reviews per coffee shop (dikurangi dari 5)
                        review_text = review.get('text', '').strip()
                        if review_text and len(review_text) > 20:  # Min 20 karakter
                            review_rating = review.get('rating', 0)
                            author_name = review.get('author_name', 'Anonim')
                            author_url = review.get('author_url', '')  # Link ke profil Google Maps reviewer
                            
                            # Truncate review yang terlalu panjang (dikurangi dari 200 ke 150)
                            if len(review_text) > 150:
                                review_text = review_text[:147] + "..."
                            
                            # Tambahkan author_url untuk verifikasi
                            if author_url:
                                context_lines.append(f"     - {author_name} ({review_rating}⭐): \"{review_text}\" [Verifikasi: {author_url}]")
                            else:
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
        
        print(f"[PLACES+REVIEWS] Context prepared: {len(all_shops)} shops with reviews, {len(context)} characters")
        return context
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[PLACES+REVIEWS] Error: {str(e)}")
        print(f"[PLACES+REVIEWS] Traceback: {error_detail}")
        return f"Error mengambil data coffee shop dengan review: {str(e)}"

# Helper function untuk fetch coffee shops dari Google Places API sebagai context untuk LLM
def _fetch_coffeeshops_context(location_str):
    """
    Fetch coffee shops dari Google Places API dan format sebagai context untuk LLM.
    Ini memastikan LLM memberikan rekomendasi berdasarkan data REAL, bukan hallucination.
    
    Args:
        location_str: Nama lokasi untuk search (e.g., "Pontianak")
    
    Returns:
        String berisi daftar coffee shops yang diformat untuk LLM context
    """
    try:
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
        places_context = _fetch_coffeeshops_with_reviews_context(location, max_shops=30)  # Optimal: 30 coffee shops (balance antara akurasi dan performa)
        
        # Debug: Print sample reviews untuk verify data
        print(f"[LLM] Context preview (first 500 chars):")
        print(places_context[:500] if len(places_context) > 500 else places_context)
        print(f"[LLM] Total context length: {len(places_context)} characters")
        
        # Step 2: Build system prompt dengan context REVIEWS untuk bukti rekomendasi
        system_prompt = f"""Anda adalah asisten rekomendasi coffee shop yang AKURAT dan JUJUR. Anda menggunakan data NYATA dari Google Places API.

DATA COFFEE SHOP DI {location.upper()} DENGAN INFORMASI LENGKAP:
{places_context}

🎯 ATURAN UTAMA:
1. HANYA rekomendasikan jika ADA review yang relevan dengan kata kunci user
2. Review harus BENAR-BENAR menyebutkan atau berhubungan erat dengan kata kunci
3. Jika tidak ada review yang relevan, JANGAN rekomendasikan - langsung jawab: "Maaf, tidak ada coffee shop yang sesuai dengan preferensi Anda saat ini."
4. JANGAN memberikan rekomendasi yang dipaksakan atau diada-adakan

⚠️ ATURAN ANTI-HALUSINASI:
1. COPY PASTE review PERSIS dari data - DILARANG mengubah
2. DILARANG membuat nama user palsu - gunakan nama ASLI dari data
3. DILARANG menambah-nambah informasi yang tidak ada di data
4. DILARANG memberikan penjelasan "Logika Rekomendasi" atau "Mengapa Cocok"

🚫 FORMAT OUTPUT - DILARANG:
- JANGAN gunakan emoji apapun (🏆📍📝🗺️🎯☕💡 dll)
- JANGAN gunakan format "Nama - Rating X/5.0"

✅ FORMAT OUTPUT - WAJIB:
Nomor. **Nama Coffee Shop**
Rating: X.X
Alamat: [alamat lengkap dari data - WAJIB ada]
Google Maps: [URL dari data - WAJIB ada]
Berdasarkan Ulasan Pengunjung: "review text dengan **kata kunci** bold" - Nama User (Rating⭐) [Verifikasi: URL]

📋 CARA MENGUTIP REVIEW:
- COPY PASTE teks review PERSIS kata per kata dari data
- Gunakan nama user ASLI dan rating ASLI
- Jika ada link [Verifikasi: URL], sertakan juga untuk bukti
- Format: "Teks review asli" - Nama User (Rating⭐) [Verifikasi: URL]

🔍 KRITERIA RELEVANSI KETAT:
- Review HARUS menyebutkan kata kunci atau sinonim/makna yang sangat dekat
- Contoh RELEVAN: 
  * User cari "wifi bagus" → Review: "wifinya kencang" ✅
  * User cari "musholla" → Review: "ada musholla" atau "tempat sholat tersedia" ✅
- Contoh TIDAK RELEVAN:
  * User cari "musholla" → Review: "tempatnya nyaman" ❌
  * User cari "buka malam" → Review: "kopinya enak" ❌

PENTING: 
- Prioritas: KEJUJURAN > Memberikan rekomendasi
- Jika tidak ada yang sesuai, JUJUR katakan tidak ada
- JANGAN paksa rekomendasi yang tidak relevan
- OUTPUT HANYA 5 BARIS per coffee shop: nama (bold), rating, alamat, Google Maps URL, review
- Alamat dan Google Maps URL WAJIB diambil dari data yang tersedia"""

        # Step 3: Extract keywords dari user input untuk highlighting
        keywords = [kw.strip().lower() for kw in user_text.split(',') if kw.strip()]
        keywords_display = ', '.join([f'"{kw}"' for kw in keywords])
        
        # Step 4: Build user prompt khusus untuk KEYWORD-BASED RECOMMENDATION dengan BOLD
        if task == 'summarize':
            user_content = f"""Kata kunci preferensi user:
{user_text}

Cari coffee shop yang reviewnya BENAR-BENAR menyebutkan kata kunci di atas. Jika tidak ada yang sesuai, jawab: "🙏 Maaf, tidak ada coffee shop yang sesuai dengan preferensi Anda saat ini." Jangan tambahkan penjelasan pembuka atau logika rekomendasi."""
        elif task == 'recommend':
            user_content = f"""KATA KUNCI PREFERENSI saya:
{user_text}

Tugas Anda: Cari coffee shop yang reviewnya BENAR-BENAR menyebutkan kata kunci di atas.

⚠️ ATURAN KETAT:
1. HANYA rekomendasikan jika ada review yang menyebutkan kata kunci ({keywords_display})
2. Review harus RELEVAN - bukan sekedar review positif biasa
3. Jika tidak ada review yang relevan, LANGSUNG jawab: "Maaf, tidak ada coffee shop yang sesuai dengan preferensi Anda saat ini."
4. JANGAN memberikan rekomendasi yang dipaksakan
5. JANGAN tambahkan penjelasan pembuka seperti "Berdasarkan kata kunci..."
6. JANGAN tambahkan section "LOGIKA REKOMENDASI"

🚫 DILARANG KERAS:
- JANGAN gunakan emoji apapun (🏆📍📝🗺️🎯☕💡 dll)
- JANGAN tulis "Alamat:" atau alamat lengkap
- JANGAN tulis "Google Maps:" atau link maps
- JANGAN tulis format "Toko Kami - Rating X/5.0"

✅ FORMAT OUTPUT WAJIB (COPY PERSIS):

1. **Nama Coffee Shop**
Rating: X.X
Alamat: [alamat lengkap dari data]
Google Maps: [URL dari data]
Berdasarkan Ulasan Pengunjung: "Review yang menyebutkan **kata kunci**" - Nama User (Rating⭐) [Verifikasi: URL jika ada]

2. **Nama Coffee Shop Kedua**
Rating: X.X
Alamat: [alamat lengkap dari data]
Google Maps: [URL dari data]
Berdasarkan Ulasan Pengunjung: "Review yang menyebutkan **kata kunci**" - Nama User (Rating⭐) [Verifikasi: URL jika ada]

ATURAN FORMAT KETAT (WAJIB IKUTI):
1. Mulai dengan nomor urut + titik + spasi + **Nama** (WAJIB diapit dua asterisk)
2. Baris kedua: "Rating: " + angka (contoh: "Rating: 4.5")
3. Baris ketiga: "Alamat: " + alamat lengkap dari data (WAJIB ada)
4. Baris keempat: "Google Maps: " + URL dari data (WAJIB ada)
5. Baris kelima: "Berdasarkan Ulasan Pengunjung: " + review lengkap
6. Gunakan **bold** untuk kata dalam review yang MATCH dengan kata kunci
7. HANYA 5 baris per coffee shop: nama, rating, alamat, maps URL, review
8. TIDAK ADA informasi tambahan lain

CONTOH OUTPUT YANG BENAR (COPY FORMAT INI):
1. **Toko Kami**
Rating: 4.8
Alamat: Jl. Kh.A.Dahlan Gg. Margosari No.3, Sungai Bangkong, Kec. Pontianak Kota, Kota Pontianak, Kalimantan Barat 78121, Indonesia
Google Maps: https://www.google.com/maps/place/?q=place_id:ChJM5X-4vIZHS4Rqyyj2I6Xh4U
Berdasarkan Ulasan Pengunjung: "**cozy**, enak bgt kopi sederhana favy" - Dzaky Farhan (5⭐)

2. **Kopi Santai**
Rating: 4.5
Alamat: Jl. Ahmad Yani No. 123, Pontianak, Kalimantan Barat, Indonesia
Google Maps: https://www.google.com/maps/place/?q=place_id:ChABCDEF123456
Berdasarkan Ulasan Pengunjung: "Tempatnya **cozy** banget, **wifi** kencang" - Budi (5⭐) [Verifikasi: https://...]

CONTOH SALAH (JANGAN IKUTI):
❌ 🏆 Toko Kami - Rating 4.8/5.0
📍 Alamat: Jl. Ahmad Yani No. 123
📝 Berdasarkan Ulasan Pengunjung: ...

❌ Toko Kami (tanpa nomor dan **)

❌ 1. Toko Kami (tanpa **)

❌ 1. **Toko Kami**
Rating: 4.8
Berdasarkan Ulasan Pengunjung: ... (SALAH - tidak ada Alamat dan Google Maps URL)

MULAI OUTPUT SEKARANG (langsung tulis tanpa penjelasan):"""
        else:  # analyze (default)
            user_content = f"""Kata kunci preferensi: {user_text}

Cari coffee shop yang reviewnya BENAR-BENAR menyebutkan kata kunci di atas. Jika tidak ada review yang relevan, jawab: "🙏 Maaf, tidak ada coffee shop yang sesuai dengan preferensi Anda saat ini." Gunakan **bold** untuk highlight kata yang match. Jangan tambahkan penjelasan pembuka atau logika rekomendasi."""
        
        # Estimate token count (rough: 1 token ≈ 4 characters)
        estimated_context_tokens = len(places_context) // 4
        estimated_system_tokens = len(system_prompt) // 4
        estimated_user_tokens = len(str(user_content)) // 4
        estimated_total_input_tokens = estimated_context_tokens + estimated_system_tokens + estimated_user_tokens
        print(f"[LLM] Estimated input tokens - Context: {estimated_context_tokens}, System: {estimated_system_tokens}, User: {estimated_user_tokens}, Total: {estimated_total_input_tokens}")
        
        # Warning jika context terlalu besar
        if estimated_total_input_tokens > 6000:
            print(f"[WARNING] Input tokens sangat besar ({estimated_total_input_tokens} tokens). Mungkin exceed model limit!")
        
        # Step 4: Call Hugging Face Inference API dengan context
        print(f"[LLM] Calling HF API with task: {task}")
        print(f"[LLM] Model: {HF_MODEL}")
        
        response = hf_client.chat.completions.create(
            model=HF_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            max_tokens=1536,  # Optimal untuk 30 coffee shops dengan review
            temperature=0.1,  # Extremely low untuk strict format adherence
            top_p=0.8  # Fokus pada token dengan probabilitas tinggi
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
