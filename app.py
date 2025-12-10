from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
import json
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
        context = _fetch_coffeeshops_with_reviews_from_json(location, max_shops=max_shops)
        
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

# Helper function untuk mapping sinonim keyword (untuk logika relevansi LLM)
def _get_keyword_synonyms(keyword):
    """
    Mengembalikan daftar sinonim untuk keyword tertentu.
    Digunakan untuk membantu LLM memahami bahwa berbagai variasi kata memiliki makna yang sama.
    
    Args:
        keyword: Kata kunci yang ingin dicari sinonimnya (lowercase)
    
    Returns:
        List of synonyms untuk keyword tersebut
    """
    keyword = keyword.lower().strip()
    
    # Mapping sinonim untuk berbagai keyword
    synonym_map = {
        # 24 jam / jam operasional
        '24 jam': ['buka 24 jam', 'buka sampai larut', 'larut malam', 'buka malam', 
                   'buka sampai subuh', 'buka tengah malam', 'operasional 24 jam',
                   'buka sepanjang hari', 'tutup larut', 'buka sampai dini hari'],
        'buka malam': ['24 jam', 'buka sampai larut', 'larut malam', 'buka sampai subuh',
                       'buka tengah malam', 'operasional 24 jam', 'buka sepanjang hari',
                       'tutup larut', 'buka sampai dini hari'],
        'buka sampai larut': ['24 jam', 'buka malam', 'larut malam', 'buka sampai subuh',
                             'buka tengah malam', 'operasional 24 jam', 'buka sepanjang hari',
                             'tutup larut', 'buka sampai dini hari'],
        'larut malam': ['24 jam', 'buka malam', 'buka sampai larut', 'buka sampai subuh',
                       'buka tengah malam', 'operasional 24 jam', 'buka sepanjang hari',
                       'tutup larut', 'buka sampai dini hari'],
        
        # WiFi / Internet
        'wifi bagus': ['wifi kencang', 'wifi stabil', 'wifi cepat', 'koneksi internet lancar',
                      'internet kencang', 'wifi aman', 'wifi tidak ngadat'],
        'wifi kencang': ['wifi bagus', 'wifi stabil', 'wifi cepat', 'koneksi internet lancar',
                        'internet kencang', 'wifi aman', 'wifi tidak ngadat'],
        'wifi stabil': ['wifi bagus', 'wifi kencang', 'wifi cepat', 'koneksi internet lancar',
                       'internet kencang', 'wifi aman', 'wifi tidak ngadat'],
        
        # Musholla / Tempat Sholat
        'musholla': ['tempat sholat', 'tempat sholat tersedia', 'ada musholla', 'ruang sholat',
                    'tempat ibadah', 'mushola'],
        'tempat sholat': ['musholla', 'tempat sholat tersedia', 'ada musholla', 'ruang sholat',
                         'tempat ibadah', 'mushola'],
        
        # Colokan / Terminal Listrik
        'colokan banyak': ['terminal listrik ada', 'stopkontak tersedia', 'colokan di setiap meja',
                          'terminal listrik', 'stopkontak banyak', 'colokan tersedia'],
        'terminal listrik': ['colokan banyak', 'stopkontak tersedia', 'colokan di setiap meja',
                            'terminal listrik ada', 'stopkontak banyak', 'colokan tersedia'],
        'stopkontak': ['colokan banyak', 'terminal listrik', 'colokan di setiap meja',
                      'terminal listrik ada', 'stopkontak tersedia', 'colokan tersedia'],
        
        # Cozy / Nyaman / Suasana Hangat
        'cozy': ['nyaman', 'hangat', 'tenang', 'santai', 'ambience tenang', 'suasananya cozy',
                'atmosfernya hangat', 'tempatnya nyaman', 'suasana hangat', 'tempat tenang',
                'suasananya hangat', 'atmosfer hangat', 'nyaman banget', 'cozy banget'],
        'nyaman': ['cozy', 'hangat', 'tenang', 'santai', 'ambience tenang', 'suasananya cozy',
                  'atmosfernya hangat', 'tempatnya nyaman', 'suasana hangat', 'tempat tenang'],
        
        # Ruang Belajar / Kerja / Tugas
        'ruang belajar': ['belajar', 'cocok buat belajar', 'ngerjain tugas', 'kerja', 'wfc',
                         'work from cafe', 'enak buat kerja', 'pas buat ngerjain tugas',
                         'cocok buat kerja', 'buat kerja', 'buat belajar', 'tempat kerja',
                         'tempat belajar', 'cocok kerja', 'enak belajar', 'ruang belajar',
                         'cocok sebagai ruang belajar', 'tempat favorit buat ruang belajar',
                         'cocok buat ruang belajar', 'buat ruang belajar'],
        'belajar': ['ruang belajar', 'cocok buat belajar', 'ngerjain tugas', 'kerja', 'wfc',
                   'work from cafe', 'enak buat kerja', 'pas buat ngerjain tugas',
                   'cocok sebagai ruang belajar', 'tempat favorit buat ruang belajar',
                   'cocok buat belajar', 'buat belajar', 'tempat belajar', 'enak belajar',
                   'cocok buat ruang belajar', 'buat ruang belajar', 'cocok buat belajar',
                   'cocok sebagai ruang belajar'],
        'kerja': ['ruang belajar', 'belajar', 'cocok buat belajar', 'ngerjain tugas', 'wfc',
                 'work from cafe', 'enak buat kerja', 'pas buat ngerjain tugas', 'cocok buat kerja'],
        'wfc': ['ruang belajar', 'belajar', 'kerja', 'work from cafe', 'enak buat kerja',
               'pas buat ngerjain tugas', 'cocok buat kerja'],
        'tugas': ['ruang belajar', 'belajar', 'ngerjain tugas', 'kerja', 'wfc', 'work from cafe'],
        
        # Sofa / Kursi Nyaman
        'sofa': ['kursi nyaman', 'kursi empuk', 'ruas sofa', 'kursi cukup nyaman', 'sofa nyaman',
                'sofa empuk', 'kursi', 'tempat duduk nyaman', 'kursi sofa', 'ruas sofa nyaman'],
        'kursi nyaman': ['sofa', 'kursi empuk', 'ruas sofa', 'kursi cukup nyaman', 'sofa nyaman',
                        'sofa empuk', 'kursi', 'tempat duduk nyaman'],
        
        # Ruangan Dingin / AC
        'ruangan dingin': ['ac', 'dingin', 'sejuk', 'adem', 'ruangan sejuk', 'ruangan adem',
                          'ac dingin', 'udara dingin', 'hawa dingin', 'ruangan ber-ac',
                          'ruangan ber ac', 'dingin ac', 'sejuk ac'],
        'ac': ['ruangan dingin', 'dingin', 'sejuk', 'adem', 'ruangan sejuk', 'ruangan adem',
              'ac dingin', 'udara dingin', 'hawa dingin', 'ruangan ber-ac'],
        'dingin': ['ruangan dingin', 'ac', 'sejuk', 'adem', 'ruangan sejuk', 'ruangan adem'],
        
        # Aesthetic / Estetik / Kekinian
        'aesthetic': ['estetik', 'kekinian', 'desain', 'dekor', 'tiap sudut kayak sengaja didesain buat foto',
                     'aesthetic banget', 'estetik banget', 'kekinian banget', 'desain aesthetic',
                     'dekor aesthetic', 'instagramable', 'foto-foto', 'kece', 'instagram worthy'],
        'estetik': ['aesthetic', 'kekinian', 'desain', 'dekor', 'tiap sudut kayak sengaja didesain buat foto',
                   'aesthetic banget', 'estetik banget', 'kekinian banget'],
        'kekinian': ['aesthetic', 'estetik', 'desain', 'dekor', 'kekinian banget', 'aesthetic banget'],
        
        # Live Music / Musik
        'live music': ['musik', 'akustik', 'pertunjukan live music', 'musiknya santai', 'musiknya tenang',
                      'musiknya lembut', 'ada live music', 'pertunjukan musik', 'live musik',
                      'musik live', 'akustik live', 'pertunjukan akustik', 'live music-nya', 'live musicnya',
                      'musiknya', 'musik santai', 'musik tenang'],
        'musik': ['live music', 'akustik', 'pertunjukan live music', 'musiknya santai', 'musiknya tenang',
                 'musiknya lembut', 'ada live music', 'pertunjukan musik', 'live musik'],
        'akustik': ['live music', 'musik', 'pertunjukan live music', 'akustik live', 'pertunjukan akustik'],
        
        # Parkir Luas / Parkiran
        'parkiran luas': ['parkir luas', 'parkir mobil nyaman', 'parkir luas', 'tempat parkir luas',
                         'parkiran', 'parkir', 'parkir nyaman', 'parkir mobil', 'parkir motor',
                         'tempat parkir', 'area parkir luas', 'parkir aman'],
        'parkir luas': ['parkiran luas', 'parkir mobil nyaman', 'parkir', 'tempat parkir luas',
                       'parkiran', 'parkir nyaman', 'parkir mobil', 'parkir motor'],
        'parkir': ['parkiran luas', 'parkir luas', 'parkir mobil nyaman', 'tempat parkir luas',
                  'parkiran', 'parkir nyaman', 'parkir mobil', 'parkir motor'],
        
        # Gaming / Ngegame
        'gaming': ['ngegame', 'main game', 'bermain game', 'untuk gaming', 'cocok gaming',
                  'enak untuk ngegame', 'main game', 'gaming santai', 'cocok buat gaming',
                  'tempat gaming', 'coffee shop gaming', 'ngegame santai'],
        'ngegame': ['gaming', 'main game', 'bermain game', 'untuk gaming', 'cocok gaming',
                   'enak untuk ngegame', 'gaming santai', 'cocok buat gaming', 'tempat gaming'],
        'main game': ['gaming', 'ngegame', 'bermain game', 'untuk gaming', 'cocok gaming',
                     'enak untuk ngegame', 'gaming santai'],
        'bermain game': ['gaming', 'ngegame', 'main game', 'untuk gaming', 'cocok gaming',
                        'enak untuk ngegame', 'gaming santai'],
    }
    
    # Cek apakah keyword ada di mapping
    if keyword in synonym_map:
        return synonym_map[keyword]
    
    # Cek partial match (jika keyword mengandung salah satu key)
    for key, synonyms in synonym_map.items():
        if key in keyword or keyword in key:
            return synonyms
    
    # Jika tidak ada mapping, kembalikan list kosong
    return []

def _expand_keywords_with_synonyms(keywords):
    """
    Expand keywords dengan menambahkan sinonim-sinonimnya.
    Digunakan untuk membantu LLM memahami berbagai variasi kata yang memiliki makna sama.
    
    Args:
        keywords: List of keywords (lowercase)
    
    Returns:
        List of expanded keywords (original + synonyms)
    """
    expanded = set(keywords)  # Gunakan set untuk menghindari duplikasi
    
    # Cek apakah ada keyword gaming/ngegame
    gaming_keywords = ['gaming', 'ngegame', 'main game', 'bermain game', 'untuk gaming', 'cocok gaming']
    has_gaming = any(gk in ' '.join(keywords).lower() for gk in gaming_keywords)
    
    for keyword in keywords:
        synonyms = _get_keyword_synonyms(keyword)
        expanded.update(synonyms)
    
    # Jika user mencari gaming, tambahkan fasilitas yang relevan dengan gaming
    if has_gaming:
        gaming_facilities = [
            'wifi bagus', 'wifi kencang', 'wifi stabil', 'koneksi internet lancar',
            'stopkontak banyak', 'colokan banyak', 'terminal listrik', 'colokan di setiap meja',
            '24 jam', 'buka malam', 'buka sampai larut', 'larut malam'
        ]
        expanded.update(gaming_facilities)
        print(f"[KEYWORD EXPANSION] Gaming detected, added gaming facilities: {gaming_facilities}")
    
    return list(expanded)

# Helper function untuk fetch coffee shops dengan REVIEWS dari file JSON lokal
def _fetch_coffeeshops_with_reviews_from_json(location_str, max_shops=15, keywords=None):
    """
    Fetch coffee shops DENGAN REVIEWS dari file JSON lokal (places.json dan reviews.json) untuk LLM context.
    Reviews digunakan sebagai bukti/evidence dalam rekomendasi.
    Coffee shops diurutkan berdasarkan rating dan jumlah review untuk mendapatkan yang terbaik.
    JIKA ADA KEYWORDS: Prioritaskan coffee shop yang memiliki review relevan dengan keywords.
    
    Args:
        location_str: Nama lokasi untuk filter (e.g., "Pontianak") - saat ini tidak digunakan karena semua data dari Pontianak
        max_shops: Maksimal jumlah coffee shops yang di-fetch (default: 15)
        keywords: List of keywords untuk pre-filter coffee shops yang relevan (optional)
    
    Returns:
        String berisi daftar coffee shops dengan reviews untuk LLM context
    """
    try:
        print(f"[JSON+REVIEWS] Loading coffee shops with reviews from local JSON files")
        
        # Path ke file JSON (relatif dari app.py di root)
        places_json_path = os.path.join('frontend-cofind', 'src', 'data', 'places.json')
        reviews_json_path = os.path.join('frontend-cofind', 'src', 'data', 'reviews.json')
        
        # Baca places.json
        if not os.path.exists(places_json_path):
            print(f"[JSON+REVIEWS] Error: File {places_json_path} tidak ditemukan")
            return "Error: File places.json tidak ditemukan."
        
        with open(places_json_path, 'r', encoding='utf-8') as f:
            places_data = json.load(f)
        
        coffee_shops = places_data.get('data', [])
        if not coffee_shops:
            print(f"[JSON+REVIEWS] Error: Tidak ada data coffee shop di places.json")
            return "Tidak ada data coffee shop yang ditemukan."
        
        # Baca reviews.json
        reviews_data = {}
        if os.path.exists(reviews_json_path):
            with open(reviews_json_path, 'r', encoding='utf-8') as f:
                reviews_data = json.load(f)
        else:
            print(f"[JSON+REVIEWS] Warning: File {reviews_json_path} tidak ditemukan, akan menggunakan data tanpa reviews")
        
        reviews_by_place_id = reviews_data.get('reviews_by_place_id', {})
        
        # PENTING: Jika ada keywords, prioritaskan coffee shop yang memiliki review relevan
        relevant_shops = []
        other_shops = []
        
        if keywords and len(keywords) > 0:
            print(f"[JSON+REVIEWS] Pre-filtering coffee shops dengan keywords: {keywords[:10]}... (total: {len(keywords)})")
            
            for shop in coffee_shops:
                place_id = shop.get('place_id', '')
                shop_reviews = reviews_by_place_id.get(place_id, [])
                
                # Cek apakah ada review yang relevan dengan keywords
                has_relevant_review = False
                for review in shop_reviews:
                    review_text = (review.get('text', '') or '').strip().lower()
                    if review_text and len(review_text) > 20:
                        # Cek apakah review mengandung minimal salah satu keyword
                        for kw in keywords:
                            kw_lower = kw.lower().strip()
                            if len(kw_lower) >= 3 and kw_lower in review_text:
                                has_relevant_review = True
                                print(f"[JSON+REVIEWS] ✅ Found relevant shop: {shop.get('name', 'Unknown')} (keyword: '{kw}')")
                                break
                        if has_relevant_review:
                            break
                
                if has_relevant_review:
                    relevant_shops.append(shop)
                else:
                    other_shops.append(shop)
            
            print(f"[JSON+REVIEWS] Found {len(relevant_shops)} coffee shops with relevant reviews, {len(other_shops)} other shops")
        else:
            # Jika tidak ada keywords, semua coffee shops masuk ke other_shops
            other_shops = coffee_shops
        
        # Sort coffee shops berdasarkan rating (descending) dan jumlah review (descending)
        # Priority: Rating lebih tinggi > Jumlah review lebih banyak
        def sort_key(shop):
            rating = shop.get('rating', 0)
            if isinstance(rating, str):
                try:
                    rating = float(rating)
                except (ValueError, TypeError):
                    rating = 0
            elif rating is None:
                rating = 0
            
            total_ratings = shop.get('user_ratings_total', 0)
            if total_ratings is None:
                total_ratings = 0
            
            # Return tuple untuk sorting: (rating descending, total_ratings descending)
            # Negatif untuk descending order
            return (-rating, -total_ratings)
        
        # Sort relevant shops dan other shops terpisah
        relevant_shops_sorted = sorted(relevant_shops, key=sort_key)
        other_shops_sorted = sorted(other_shops, key=sort_key)
        
        # Gabungkan: relevant shops di depan, lalu top other shops
        # Prioritaskan relevant shops, tapi tetap ambil top other shops untuk konteks lengkap
        relevant_count = len(relevant_shops_sorted)
        other_count = max(0, max_shops - relevant_count)
        
        coffee_shops = relevant_shops_sorted + other_shops_sorted[:other_count]
        
        if keywords and len(keywords) > 0:
            print(f"[JSON+REVIEWS] Final selection: {len(relevant_shops_sorted)} relevant shops + {other_count} top-rated shops = {len(coffee_shops)} total")
        else:
            print(f"[JSON+REVIEWS] Selected top {len(coffee_shops)} coffee shops (sorted by rating & review count), preparing context...")
        
        # Format context
        context_lines = [
            f"DAFTAR COFFEE SHOP DI {location_str.upper()} DENGAN REVIEW",
            f"Total: {len(coffee_shops)} coffee shop pilihan terbaik\n"
        ]
        
        for i, shop in enumerate(coffee_shops, 1):
            place_id = shop.get('place_id', '')
            name = shop.get('name', 'Unknown')
            rating = shop.get('rating', 'N/A')
            total_ratings = shop.get('user_ratings_total', 0)
            address = shop.get('address', 'No address')
            price_level = shop.get('price_level')
            
            # Generate Google Maps URL
            maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
            
            # Format entry dengan reviews (TANPA ALAMAT untuk mengurangi token)
            context_lines.append(f"{i}. {name}")
            context_lines.append(f"   • Rating: {rating}/5.0 ({total_ratings} reviews)")
            context_lines.append(f"   • Google Maps: {maps_url}")
            
            # REVIEWS - Ambil dari reviews.json (max 3 reviews per coffee shop)
            reviews = reviews_by_place_id.get(place_id, [])
            if reviews:
                context_lines.append(f"   • Review dari Pengunjung:")
                review_count = 0
                for review in reviews[:3]:  # Max 3 reviews per coffee shop
                    review_text = review.get('text', '').strip()
                    if review_text and len(review_text) > 20:  # Min 20 karakter
                        review_rating = review.get('rating', 0)
                        author_name = review.get('author_name', 'Anonim')
                        
                        # Truncate review yang terlalu panjang
                        if len(review_text) > 150:
                            review_text = review_text[:147] + "..."
                        
                        context_lines.append(f"     - {author_name} ({review_rating}⭐): \"{review_text}\"")
                        review_count += 1
                
                if review_count == 0:
                    context_lines.append(f"     - (Belum ada review dengan teks)")
            else:
                context_lines.append(f"   • Review: Belum ada review tersedia")
            
            context_lines.append("")  # Separator
        
        context = "\n".join(context_lines)
        
        print(f"[JSON+REVIEWS] Context prepared: {len(coffee_shops)} shops with reviews, {len(context)} characters")
        return context
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[JSON+REVIEWS] Error: {str(e)}")
        print(f"[JSON+REVIEWS] Traceback: {error_detail}")
        return f"Error mengambil data coffee shop dengan review dari JSON: {str(e)}"

# Endpoint untuk LLM Text Generation & Analysis menggunakan Hugging Face
@app.route('/api/llm/analyze', methods=['POST'])
def llm_analyze():
    """
    Endpoint untuk menganalisis user input dengan context dari file JSON lokal
    
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
        
        # Step 1: Extract keywords SEBELUM fetch coffee shops (untuk pre-filtering)
        # Cek apakah input adalah comma-separated keywords atau natural language
        if ',' in user_text and len(user_text.split(',')) > 1:
            # Format: comma-separated keywords
            keywords = [kw.strip().lower() for kw in user_text.split(',') if kw.strip()]
        else:
            # Format: natural language - akan di-extract nanti, tapi untuk sekarang gunakan user_text sebagai keyword
            keywords = [user_text.strip().lower()] if user_text.strip() else []
        
        # Expand keywords dengan sinonim untuk pre-filtering yang lebih baik
        if keywords:
            expanded_keywords_for_filter = _expand_keywords_with_synonyms(keywords)
            print(f"[LLM] Pre-filtering with expanded keywords: {expanded_keywords_for_filter[:10]}... (total: {len(expanded_keywords_for_filter)})")
        else:
            expanded_keywords_for_filter = []
        
        # Step 2: Fetch coffee shops DENGAN REVIEWS dari file JSON lokal
        # PENTING: Gunakan expanded keywords untuk pre-filtering coffee shops yang relevan
        print(f"[LLM] Fetching coffee shops WITH REVIEWS from local JSON files for location: {location}")
        places_context = _fetch_coffeeshops_with_reviews_from_json(location, max_shops=15, keywords=expanded_keywords_for_filter)
        
        # Debug: Print sample reviews untuk verify data
        print(f"[LLM] Context preview (first 500 chars):")
        print(places_context[:500] if len(places_context) > 500 else places_context)
        print(f"[LLM] Total context length: {len(places_context)} characters")
        
        # Step 2: Build system prompt dengan context REVIEWS untuk bukti rekomendasi
        system_prompt = f"""Anda adalah asisten rekomendasi coffee shop yang AKURAT dan JUJUR. Anda menggunakan data NYATA dari file JSON lokal.

DATA COFFEE SHOP DI {location.upper()} DENGAN INFORMASI LENGKAP:
{places_context}

🎯 ATURAN UTAMA:
1. HANYA rekomendasikan jika ADA review yang relevan dengan kata kunci user
2. Review harus BENAR-BENAR menyebutkan atau berhubungan erat dengan kata kunci
3. Jika tidak ada review yang relevan, JANGAN rekomendasikan - langsung jawab: "Maaf, tidak ada coffee shop yang sesuai dengan preferensi Anda saat ini."
4. JANGAN memberikan rekomendasi yang dipaksakan atau diada-adakan

🚨 WAJIB - REVIEW SEBAGAI BUKTI:
- SETIAP coffee shop yang direkomendasikan WAJIB disertai dengan review pengunjung yang relevan
- Review adalah BUKTI bahwa coffee shop sesuai dengan kata kunci user
- TANPA review = TIDAK BOLEH direkomendasikan
- Review HARUS dikutip PERSIS dari data (copy-paste, tidak boleh diubah)
- Format review: "Teks review lengkap" - Nama User (Rating⭐)
- Jika tidak ada review yang relevan untuk coffee shop tertentu, JANGAN rekomendasikan coffee shop tersebut

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
Alamat: [alamat lengkap - ambil dari Google Maps URL atau data yang tersedia]
Google Maps: [URL dari data - WAJIB ada]
Berdasarkan Ulasan Pengunjung: "review text dengan **kata kunci** bold" - Nama User (Rating⭐) [Verifikasi: URL]
Berdasarkan Ulasan Pengunjung: "review text kedua dengan **kata kunci** bold" - Nama User (Rating⭐) [Verifikasi: URL] (OPSIONAL - hanya jika ada 2+ review yang relevan)

CATATAN: Alamat tidak ada di context data untuk mengurangi token, tapi Anda bisa menggunakan Google Maps URL untuk mendapatkan informasi lokasi, atau gunakan alamat yang sudah Anda ketahui dari data coffee shop.

⚠️ PENTING: Baris "Berdasarkan Ulasan Pengunjung" adalah WAJIB dan TIDAK BOLEH DILEWATKAN!
- Setiap rekomendasi HARUS memiliki review sebagai bukti
- Jika tidak ada review yang relevan, JANGAN rekomendasikan coffee shop tersebut
- Review harus dikutip LENGKAP dari data, tidak boleh dipotong atau diubah

⚠️ BATASAN JUMLAH REKOMENDASI:
- JUMLAH FLEKSIBEL: 1-3 coffee shop (TIDAK WAJIB 3)
- Jika hanya ada 1 yang relevan → output 1 saja
- Jika ada 2 yang relevan → output 2 saja
- Jika ada 3+ yang relevan → output SEMUA yang relevan (maksimal 3 TERBAIK berdasarkan rating dan relevansi review)
- PENTING: Jika ada BANYAK coffee shop dengan review yang relevan, prioritaskan yang memiliki rating lebih tinggi dan review lebih banyak
- JANGAN memaksa output 3 jika tidak ada yang relevan
- JANGAN hanya output 1 jika ada lebih banyak yang relevan - output SEMUA yang relevan (maksimal 3)
- SETIAP coffee shop yang direkomendasikan HARUS memiliki review yang menyebutkan kata kunci

📋 CARA MENGUTIP REVIEW (WAJIB UNTUK SETIAP REKOMENDASI):
- COPY PASTE teks review PERSIS kata per kata dari data
- Gunakan nama user ASLI dan rating ASLI
- Jika ada link [Verifikasi: URL], sertakan juga untuk bukti
- Format: "Teks review asli" - Nama User (Rating⭐) [Verifikasi: URL]
- Review adalah BUKTI WAJIB - tidak ada review = tidak ada rekomendasi
- Setiap coffee shop yang direkomendasikan HARUS memiliki minimal 1 review yang relevan
- JIKA ADA 2+ REVIEW YANG RELEVAN: Tampilkan 2 review untuk bukti yang lebih kuat
- Prioritas: Review yang paling relevan dengan kata kunci user (yang paling banyak menyebutkan kata kunci)

🔍 KRITERIA RELEVANSI KETAT:
- Review HARUS menyebutkan kata kunci atau sinonim/makna yang sangat dekat
- Contoh RELEVAN: 
  * User cari "wifi bagus" → Review: "wifinya kencang" ✅
  * User cari "musholla" → Review: "ada musholla" atau "tempat sholat tersedia" ✅
  * User cari "24 jam" → Review: "buka 24 jam", "buka sampai larut", "larut malam", "buka malam", "buka sampai subuh" ✅
  * User cari "buka malam" → Review: "24 jam", "buka sampai larut", "larut malam", "buka sampai subuh" ✅
  * User cari "cozy" → Review: "nyaman", "hangat", "tenang", "atmosfernya hangat", "suasananya cozy" ✅
  * User cari "ruang belajar" → Review: "belajar", "kerja", "wfc", "ngerjain tugas", "cocok buat belajar", "Tempat favorit buat ruang belajar", "cocok sebagai ruang belajar" ✅
  * User cari "belajar" → Review: "belajar", "cocok buat belajar", "ruang belajar", "Tempat favorit buat ruang belajar", "cocok sebagai ruang belajar" ✅
  * User cari "sofa" → Review: "kursi nyaman", "kursi empuk", "ruas sofa" ✅
  * User cari "ruangan dingin" → Review: "ac", "dingin", "sejuk", "ruangan sejuk" ✅
  * User cari "aesthetic" → Review: "estetik", "kekinian", "desain", "dekor" ✅
  * User cari "live music" → Review: "musik", "akustik", "pertunjukan live music", "musiknya santai" ✅
  * User cari "parkiran luas" → Review: "parkir luas", "parkir mobil nyaman", "parkir" ✅
  * User cari "gaming" atau "ngegame" → Review: "gaming", "ngegame", "main game", "bermain game", "enak untuk ngegame" ✅
  * User cari "gaming" atau "ngegame" → Review: "wifi bagus", "wifi kencang", "stopkontak banyak", "colokan banyak", "24 jam", "buka malam" ✅ (RELEVAN karena gaming membutuhkan fasilitas tersebut)
- Contoh TIDAK RELEVAN:
  * User cari "musholla" → Review: "tempatnya nyaman" ❌
  * User cari "buka malam" → Review: "kopinya enak" ❌
  * User cari "24 jam" → Review: "tempatnya nyaman" ❌
  * User cari "cozy" → Review: "kopinya enak" ❌

PENTING: 
- Prioritas: KEJUJURAN > Memberikan rekomendasi
- Jika tidak ada yang sesuai, JUJUR katakan tidak ada
- JANGAN paksa rekomendasi yang tidak relevan
- OUTPUT: nama (bold), rating, alamat, Google Maps URL, review (minimal 1, maksimal 2 review jika ada yang relevan)
- Alamat dan Google Maps URL WAJIB diambil dari data yang tersedia
- REVIEW ADALAH BUKTI WAJIB - Setiap rekomendasi HARUS disertai review pengunjung yang relevan
- Jika coffee shop tidak memiliki review yang relevan dengan kata kunci, JANGAN rekomendasikan"""

        # Step 3: Extract keywords dari user input (mendukung natural language dan comma-separated)
        # Cek apakah input adalah comma-separated keywords atau natural language
        if ',' in user_text and len(user_text.split(',')) > 1:
            # Format: comma-separated keywords
            keywords = [kw.strip().lower() for kw in user_text.split(',') if kw.strip()]
        else:
            # Format: natural language - gunakan LLM untuk extract keywords
            # Buat prompt untuk ekstraksi keyword dari natural language
            extraction_prompt = f"""Anda adalah asisten yang ahli dalam mengekstrak kata kunci dari kalimat bahasa Indonesia.

KALIMAT USER:
"{user_text}"

Tugas Anda: Ekstrak kata kunci penting dari kalimat di atas yang relevan untuk mencari coffee shop.

ATURAN:
1. Ekstrak HANYA kata kunci yang relevan dengan coffee shop (fasilitas, suasana, fitur, dll)
2. Abaikan kata-kata umum seperti "saya", "ingin", "mencari", "yang", "untuk", "dan", "atau", dll
3. Fokus pada: wifi, musholla, colokan, cozy, belajar, kerja, sofa, ac, aesthetic, live music, parkir, 24 jam, dll
4. Output HANYA kata kunci yang dipisah koma, tanpa penjelasan
5. Gunakan bahasa Indonesia
6. Maksimal 10 kata kunci

CONTOH:
Input: "Saya ingin mencari coffee shop yang cozy, ada wifi kencang, dan cocok untuk kerja"
Output: cozy, wifi kencang, kerja

Input: "Tempat yang nyaman dengan musholla dan parkir luas"
Output: nyaman, musholla, parkir luas

Input: "Coffee shop aesthetic dengan live music dan ruangan dingin"
Output: aesthetic, live music, ruangan dingin

Sekarang ekstrak kata kunci dari kalimat user di atas:"""

            try:
                # Gunakan LLM untuk extract keywords (hanya jika hf_client tersedia)
                if hf_client:
                    extraction_response = hf_client.text_generation(
                        extraction_prompt,
                        max_new_tokens=50,
                        temperature=0.3,
                        return_full_text=False
                    )
                    
                    # Parse hasil ekstraksi
                    extracted_text = extraction_response.strip()
                    # Bersihkan dari format markdown atau karakter aneh
                    extracted_text = extracted_text.replace('**', '').replace('*', '').replace('"', '').replace("'", '').strip()
                    
                    # Split berdasarkan koma dan ambil keywords
                    keywords = [kw.strip().lower() for kw in extracted_text.split(',') if kw.strip()]
                    
                    # Jika ekstraksi gagal atau kosong, fallback ke split berdasarkan spasi
                    if not keywords:
                        print(f"[LLM] Keyword extraction returned empty, using fallback")
                        words = user_text.lower().split()
                        stop_words = {'saya', 'ingin', 'mencari', 'yang', 'untuk', 'dan', 'atau', 'dengan', 'ada', 'adalah', 'ini', 'itu', 'di', 'ke', 'dari', 'pada', 'oleh', 'coffee', 'shop', 'tempat', 'cafe', 'yang', 'dengan', 'untuk'}
                        keywords = [w for w in words if w not in stop_words and len(w) > 2]
                    else:
                        print(f"[LLM] Extracted keywords: {keywords}")
                else:
                    # Jika hf_client tidak tersedia, gunakan fallback
                    print(f"[LLM] HF client not available, using fallback extraction")
                    words = user_text.lower().split()
                    stop_words = {'saya', 'ingin', 'mencari', 'yang', 'untuk', 'dan', 'atau', 'dengan', 'ada', 'adalah', 'ini', 'itu', 'di', 'ke', 'dari', 'pada', 'oleh', 'coffee', 'shop', 'tempat', 'cafe', 'yang', 'dengan', 'untuk'}
                    keywords = [w for w in words if w not in stop_words and len(w) > 2]
            except Exception as e:
                print(f"[LLM] Error extracting keywords: {e}")
                # Fallback: split berdasarkan spasi
                words = user_text.lower().split()
                stop_words = {'saya', 'ingin', 'mencari', 'yang', 'untuk', 'dan', 'atau', 'dengan', 'ada', 'adalah', 'ini', 'itu', 'di', 'ke', 'dari', 'pada', 'oleh', 'coffee', 'shop', 'tempat', 'cafe', 'yang', 'dengan', 'untuk'}
                keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        # Expand keywords dengan sinonim untuk membantu LLM memahami variasi kata
        expanded_keywords = _expand_keywords_with_synonyms(keywords)
        
        # Buat display untuk keywords (termasuk sinonim yang relevan)
        keywords_display = ', '.join([f'"{kw}"' for kw in keywords])
        if expanded_keywords and len(expanded_keywords) > len(keywords):
            synonyms_display = ', '.join([f'"{syn}"' for syn in expanded_keywords if syn not in keywords])
            keywords_display += f' (atau sinonim: {synonyms_display})'
        
        # Step 4: Build user prompt khusus untuk KEYWORD-BASED RECOMMENDATION dengan BOLD
        if task == 'summarize':
            user_content = f"""Kata kunci preferensi user:
{user_text}

🔗 PENTING - SINONIM YANG RELEVAN:
- Kata kunci "24 jam" = "buka sampai larut" = "larut malam" = "buka malam" = "buka sampai subuh" = "buka tengah malam"
- Kata kunci "wifi bagus" = "wifi kencang" = "wifi stabil" = "koneksi internet lancar"
- Kata kunci "musholla" = "tempat sholat" = "tempat sholat tersedia" = "ada musholla"
- Kata kunci "colokan banyak" = "terminal listrik" = "stopkontak tersedia" = "colokan di setiap meja"
- Kata kunci "cozy" = "nyaman" = "hangat" = "tenang" = "santai" = "atmosfernya hangat" = "suasananya cozy"
- Kata kunci "ruang belajar" = "belajar" = "kerja" = "wfc" = "ngerjain tugas" = "cocok buat belajar" = "enak buat kerja"
- Kata kunci "sofa" = "kursi nyaman" = "kursi empuk" = "ruas sofa" = "kursi cukup nyaman"
- Kata kunci "ruangan dingin" = "ac" = "dingin" = "sejuk" = "adem" = "ruangan sejuk"
- Kata kunci "aesthetic" = "estetik" = "kekinian" = "desain" = "dekor" = "instagramable"
- Kata kunci "live music" = "musik" = "akustik" = "pertunjukan live music" = "musiknya santai" = "musiknya tenang"
- Kata kunci "parkiran luas" = "parkir luas" = "parkir mobil nyaman" = "parkir" = "tempat parkir luas"
- Kata kunci "gaming" = "ngegame" = "main game" = "bermain game" = "untuk gaming" = "cocok gaming" = "enak untuk ngegame"
- PENTING: Jika user mencari "gaming" atau "ngegame", review yang menyebutkan "wifi bagus", "wifi kencang", "stopkontak banyak", "colokan banyak", "24 jam", "buka malam" TETAP RELEVAN karena gaming membutuhkan fasilitas tersebut
- Jika user mencari salah satu variasi di atas, review yang menyebutkan variasi lain TETAP RELEVAN dan BOLEH direkomendasikan

Cari coffee shop yang reviewnya BENAR-BENAR menyebutkan kata kunci di atas atau sinonimnya. Jika tidak ada yang sesuai, jawab: "🙏 Maaf, tidak ada coffee shop yang sesuai dengan preferensi Anda saat ini." Jangan tambahkan penjelasan pembuka atau logika rekomendasi."""
        elif task == 'recommend':
            user_content = f"""KATA KUNCI PREFERENSI saya:
{user_text}

Tugas Anda: Cari coffee shop yang reviewnya BENAR-BENAR menyebutkan kata kunci di atas.

⚠️ ATURAN KETAT - WAJIB DIIKUTI (TIDAK BOLEH DILANGGAR):
1. HANYA rekomendasikan jika ada review yang BENAR-BENAR menyebutkan kata kunci ({keywords_display}) atau sinonimnya
2. Review harus RELEVAN - bukan sekedar review positif biasa
3. JANGAN rekomendasikan coffee shop jika tidak ada review yang menyebutkan kata kunci atau sinonimnya
4. Jika tidak ada review yang relevan, LANGSUNG jawab: "Maaf, tidak ada coffee shop yang sesuai dengan preferensi Anda saat ini."
5. JANGAN memberikan rekomendasi yang dipaksakan
6. JANGAN tambahkan penjelasan pembuka seperti "Berdasarkan kata kunci..."
7. JANGAN tambahkan section "LOGIKA REKOMENDASI"
8. ⚠️ PENTING: Jika coffee shop tidak memiliki review yang menyebutkan kata kunci, JANGAN rekomendasikan coffee shop tersebut, meskipun ratingnya tinggi atau populer
9. ⚠️ PENTING - JUMLAH REKOMENDASI: Jika ada BANYAK coffee shop dengan review yang relevan, output SEMUA yang relevan (maksimal 3 terbaik berdasarkan rating). JANGAN hanya output 1 jika ada lebih banyak yang relevan!
10. ⚠️ CONTOH: Jika user mencari "24 jam", HANYA rekomendasikan coffee shop yang reviewnya menyebutkan "24 jam", "buka sampai larut", "larut malam", "buka malam", dll. JANGAN rekomendasikan coffee shop yang reviewnya hanya menyebutkan "cozy" atau "wifi bagus" tanpa menyebutkan jam operasional.

🚨 WAJIB - SETIAP REKOMENDASI HARUS DISERTAI REVIEW:
- Setiap coffee shop yang direkomendasikan WAJIB memiliki baris "Berdasarkan Ulasan Pengunjung"
- Review adalah BUKTI bahwa coffee shop sesuai dengan kata kunci
- TANPA review = TIDAK BOLEH direkomendasikan
- Review harus dikutip LENGKAP dan PERSIS dari data
- Jika tidak ada review yang relevan untuk coffee shop tertentu, JANGAN rekomendasikan coffee shop tersebut

🔗 PENTING - SINONIM YANG RELEVAN:
- Kata kunci "24 jam" = "buka sampai larut" = "larut malam" = "buka malam" = "buka sampai subuh" = "buka tengah malam"
- Kata kunci "wifi bagus" = "wifi kencang" = "wifi stabil" = "koneksi internet lancar"
- Kata kunci "musholla" = "tempat sholat" = "tempat sholat tersedia" = "ada musholla"
- Kata kunci "colokan banyak" = "terminal listrik" = "stopkontak tersedia" = "colokan di setiap meja"
- Kata kunci "cozy" = "nyaman" = "hangat" = "tenang" = "santai" = "atmosfernya hangat" = "suasananya cozy"
- Kata kunci "ruang belajar" = "belajar" = "kerja" = "wfc" = "ngerjain tugas" = "cocok buat belajar" = "enak buat kerja"
- Kata kunci "sofa" = "kursi nyaman" = "kursi empuk" = "ruas sofa" = "kursi cukup nyaman"
- Kata kunci "ruangan dingin" = "ac" = "dingin" = "sejuk" = "adem" = "ruangan sejuk"
- Kata kunci "aesthetic" = "estetik" = "kekinian" = "desain" = "dekor" = "instagramable"
- Kata kunci "live music" = "musik" = "akustik" = "pertunjukan live music" = "musiknya santai" = "musiknya tenang"
- Kata kunci "parkiran luas" = "parkir luas" = "parkir mobil nyaman" = "parkir" = "tempat parkir luas"
- Kata kunci "gaming" = "ngegame" = "main game" = "bermain game" = "untuk gaming" = "cocok gaming" = "enak untuk ngegame"
- PENTING: Jika user mencari "gaming" atau "ngegame", review yang menyebutkan "wifi bagus", "wifi kencang", "stopkontak banyak", "colokan banyak", "24 jam", "buka malam" TETAP RELEVAN karena gaming membutuhkan fasilitas tersebut
- Jika user mencari salah satu variasi di atas, review yang menyebutkan variasi lain TETAP RELEVAN dan BOLEH direkomendasikan

🚫 DILARANG KERAS:
- JANGAN gunakan emoji apapun (🏆📍📝🗺️🎯☕💡 dll)
- JANGAN tulis "Alamat:" atau alamat lengkap
- JANGAN tulis "Google Maps:" atau link maps
- JANGAN tulis format "Toko Kami - Rating X/5.0"

✅ FORMAT OUTPUT WAJIB (COPY PERSIS):
⚠️ JUMLAH COFFEE SHOP: FLEKSIBEL (1-3) - TIDAK WAJIB 3!
- Jika hanya ada 1 coffee shop yang relevan → output 1 saja
- Jika ada 2 coffee shop yang relevan → output 2 saja (JANGAN hanya output 1!)
- Jika ada 3+ coffee shop yang relevan → output SEMUA yang relevan (maksimal 3 terbaik berdasarkan rating dan relevansi review)
- PENTING: Jangan hanya output 1 coffee shop jika ada lebih banyak yang relevan - output SEMUA yang relevan (maksimal 3)
- JANGAN memaksa output 3 jika tidak ada yang relevan
- SETIAP coffee shop yang direkomendasikan HARUS memiliki review yang menyebutkan kata kunci

1. **Nama Coffee Shop**
Rating: X.X
Alamat: [alamat lengkap - gunakan alamat yang sudah Anda ketahui atau dari Google Maps URL]
Google Maps: [URL dari data]
Berdasarkan Ulasan Pengunjung: "Review yang menyebutkan **kata kunci**" - Nama User (Rating⭐) [Verifikasi: URL jika ada]

2. **Nama Coffee Shop Kedua** (OPSIONAL - hanya jika ada yang relevan)
Rating: X.X
Alamat: [alamat lengkap - gunakan alamat yang sudah Anda ketahui atau dari Google Maps URL]
Google Maps: [URL dari data]
Berdasarkan Ulasan Pengunjung: "Review yang menyebutkan **kata kunci**" - Nama User (Rating⭐) [Verifikasi: URL jika ada]

3. **Nama Coffee Shop Ketiga** (OPSIONAL - hanya jika ada yang relevan)
Rating: X.X
Alamat: [alamat lengkap - gunakan alamat yang sudah Anda ketahui atau dari Google Maps URL]
Google Maps: [URL dari data]
Berdasarkan Ulasan Pengunjung: "Review yang menyebutkan **kata kunci**" - Nama User (Rating⭐) [Verifikasi: URL jika ada]

CATATAN: Alamat tidak ada di context data untuk mengurangi token. Gunakan alamat yang sudah Anda ketahui dari data coffee shop atau dari Google Maps URL.

ATURAN FORMAT KETAT (WAJIB IKUTI - TIDAK BOLEH DILEWATKAN):
1. Mulai dengan nomor urut + titik + spasi + **Nama** (WAJIB diapit dua asterisk)
2. Baris kedua: "Rating: " + angka (contoh: "Rating: 4.5")
3. Baris ketiga: "Alamat: " + alamat lengkap dari data (WAJIB ada)
4. Baris keempat: "Google Maps: " + URL dari data (WAJIB ada)
5. Baris kelima: "Berdasarkan Ulasan Pengunjung: " + review lengkap (WAJIB - TIDAK BOLEH DILEWATKAN!)
6. Baris keenam (OPSIONAL): "Berdasarkan Ulasan Pengunjung: " + review kedua lengkap (HANYA jika ada 2+ review yang relevan)
7. Gunakan **bold** untuk kata dalam review yang MATCH dengan kata kunci
8. Format: Minimal 5 baris (dengan 1 review), maksimal 6 baris (dengan 2 reviews jika ada)
8. TIDAK ADA informasi tambahan lain
9. ⚠️ PENTING: Baris review adalah BUKTI WAJIB - jika tidak ada review yang relevan, JANGAN rekomendasikan coffee shop tersebut

🚨 PERINGATAN PENTING - OUTPUT TIDAK LENGKAP:
- Jika output Anda terpotong karena batas token, PASTIKAN untuk menyelesaikan baris "Berdasarkan Ulasan Pengunjung" untuk SETIAP coffee shop yang sudah Anda mulai
- JANGAN mulai rekomendasi coffee shop baru jika Anda tidak yakin bisa menyelesaikannya dengan review
- LEBIH BAIK output 1-2 coffee shop LENGKAP dengan review daripada 3 coffee shop TANPA review
- Jika Anda merasa output akan terpotong, HENTIKAN di coffee shop yang sudah lengkap dan jangan mulai yang baru

CONTOH OUTPUT YANG BENAR (COPY FORMAT INI):
1. **Toko Kami**
Rating: 4.8
Alamat: Jl. Kh.A.Dahlan Gg. Margosari No.3, Sungai Bangkong, Kec. Pontianak Kota, Kota Pontianak, Kalimantan Barat 78121, Indonesia
Google Maps: https://www.google.com/maps/place/?q=place_id:ChJM5X-4vIZHS4Rqyyj2I6Xh4U
Berdasarkan Ulasan Pengunjung: "**cozy**, enak bgt kopi sederhana favy" - Dzaky Farhan (5⭐)
Berdasarkan Ulasan Pengunjung: "Tempatnya **nyaman** dan hangat, cocok buat nongkrong" - Sarah (4⭐) (OPSIONAL - hanya jika ada 2+ review yang relevan)

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

❌ 1. **Toko Kami**
Rating: 4.8
Alamat: Jl. Ahmad Yani No. 123
Google Maps: https://...
(SALAH - TIDAK ADA REVIEW! Setiap rekomendasi WAJIB memiliki review sebagai bukti)

MULAI OUTPUT SEKARANG (langsung tulis tanpa penjelasan):"""
        else:  # analyze (default)
            user_content = f"""Kata kunci preferensi: {user_text}

🔗 PENTING - SINONIM YANG RELEVAN:
- Kata kunci "24 jam" = "buka sampai larut" = "larut malam" = "buka malam" = "buka sampai subuh" = "buka tengah malam"
- Kata kunci "wifi bagus" = "wifi kencang" = "wifi stabil" = "koneksi internet lancar"
- Kata kunci "musholla" = "tempat sholat" = "tempat sholat tersedia" = "ada musholla"
- Kata kunci "colokan banyak" = "terminal listrik" = "stopkontak tersedia" = "colokan di setiap meja"
- Kata kunci "cozy" = "nyaman" = "hangat" = "tenang" = "santai" = "atmosfernya hangat" = "suasananya cozy"
- Kata kunci "ruang belajar" = "belajar" = "kerja" = "wfc" = "ngerjain tugas" = "cocok buat belajar" = "enak buat kerja"
- Kata kunci "sofa" = "kursi nyaman" = "kursi empuk" = "ruas sofa" = "kursi cukup nyaman"
- Kata kunci "ruangan dingin" = "ac" = "dingin" = "sejuk" = "adem" = "ruangan sejuk"
- Kata kunci "aesthetic" = "estetik" = "kekinian" = "desain" = "dekor" = "instagramable"
- Kata kunci "live music" = "musik" = "akustik" = "pertunjukan live music" = "musiknya santai" = "musiknya tenang"
- Kata kunci "parkiran luas" = "parkir luas" = "parkir mobil nyaman" = "parkir" = "tempat parkir luas"
- Jika user mencari salah satu variasi di atas, review yang menyebutkan variasi lain TETAP RELEVAN dan BOLEH direkomendasikan

Cari coffee shop yang reviewnya BENAR-BENAR menyebutkan kata kunci di atas atau sinonimnya. 

🚨 PENTING - JUMLAH REKOMENDASI:
- Jika ada 1 coffee shop yang relevan → output 1
- Jika ada 2 coffee shop yang relevan → output 2 (JANGAN hanya output 1!)
- Jika ada 3+ coffee shop yang relevan → output SEMUA yang relevan (maksimal 3 terbaik berdasarkan rating)
- Jangan hanya output 1 jika ada lebih banyak yang relevan - output SEMUA yang relevan (maksimal 3)

Jika tidak ada review yang relevan, jawab: "🙏 Maaf, tidak ada coffee shop yang sesuai dengan preferensi Anda saat ini." Gunakan **bold** untuk highlight kata yang match. Jangan tambahkan penjelasan pembuka atau logika rekomendasi.

🚨 WAJIB - SETIAP REKOMENDASI HARUS DISERTAI REVIEW:
- Setiap coffee shop yang direkomendasikan WAJIB memiliki review pengunjung yang relevan sebagai bukti
- Review harus dikutip LENGKAP dan PERSIS dari data
- Format: "Teks review lengkap" - Nama User (Rating⭐)
- TANPA review = TIDAK BOLEH direkomendasikan
- Jika tidak ada review yang relevan untuk coffee shop tertentu, JANGAN rekomendasikan coffee shop tersebut"""
        
        # Estimate token count (rough: 1 token ≈ 4 characters)
        estimated_context_tokens = len(places_context) // 4
        estimated_system_tokens = len(system_prompt) // 4
        estimated_user_tokens = len(str(user_content)) // 4
        estimated_total_input_tokens = estimated_context_tokens + estimated_system_tokens + estimated_user_tokens
        print(f"[LLM] Estimated input tokens - Context: {estimated_context_tokens}, System: {estimated_system_tokens}, User: {estimated_user_tokens}, Total: {estimated_total_input_tokens}")
        
        # Warning jika context terlalu besar
        # PENTING: Model Llama 3.1 8B memiliki context window 8,192 tokens (TOTAL: input + output)
        # Context window = batas maksimal TOTAL tokens yang bisa diproses dalam satu request
        # Input tokens = system prompt + user prompt + context data (coffee shops + reviews)
        # Output tokens = response yang dihasilkan LLM (dibatasi oleh max_tokens)
        # Total usage = input tokens + output tokens (HARUS <= 8,192)
        
        # Hitung estimasi total usage (input + output maksimal)
        requested_max_output_tokens = 3072  # Batas maksimal output yang kita minta (ditingkatkan untuk memastikan cukup ruang untuk review)
        estimated_total_usage = estimated_total_input_tokens + requested_max_output_tokens
        
        # Minimal output tokens yang diperlukan untuk output lengkap dengan review
        # Estimasi: 1 rekomendasi lengkap (nama, rating, alamat, maps, review) ≈ 200-300 tokens
        # Untuk 3 rekomendasi lengkap dengan review: minimal 900-1200 tokens
        MIN_OUTPUT_TOKENS_FOR_COMPLETE_RESPONSE = 1200  # Minimal untuk 3 rekomendasi lengkap dengan review
        
        # Sesuaikan max_tokens jika input terlalu besar (untuk menghindari melebihi context window)
        available_for_output = 8192 - estimated_total_input_tokens
        if available_for_output < 512:  # Sangat kritis - hampir tidak ada ruang untuk output
            print(f"[ERROR] Input terlalu besar! Hanya {available_for_output} tokens tersedia untuk output.")
            print(f"[ERROR] Output akan sangat terbatas atau request mungkin gagal!")
            actual_max_tokens = max(256, available_for_output - 100)  # Minimal 256, sisakan 100 untuk buffer
            print(f"[ERROR] ⚠️ PERINGATAN: max_tokens ({actual_max_tokens}) terlalu kecil untuk output lengkap dengan review!")
            print(f"[ERROR] Output mungkin terpotong sebelum review ditulis. Pertimbangkan mengurangi max_shops atau jumlah review.")
        elif available_for_output < MIN_OUTPUT_TOKENS_FOR_COMPLETE_RESPONSE:
            # Input besar, tapi masih ada ruang untuk output (meskipun terbatas)
            print(f"[WARNING] Input besar, mengurangi max_tokens dari {requested_max_output_tokens} ke {available_for_output - 100}")
            actual_max_tokens = available_for_output - 100  # Sisakan 100 tokens untuk buffer
            if actual_max_tokens < MIN_OUTPUT_TOKENS_FOR_COMPLETE_RESPONSE:
                print(f"[WARNING] ⚠️ PERINGATAN: max_tokens ({actual_max_tokens}) mungkin tidak cukup untuk output lengkap dengan review!")
                print(f"[WARNING] Output mungkin terpotong atau review tidak lengkap. Pertimbangkan mengurangi max_shops atau jumlah review.")
        elif available_for_output < requested_max_output_tokens:
            # Input cukup besar, tapi masih bisa menggunakan requested tokens
            print(f"[INFO] Input cukup besar, mengurangi max_tokens dari {requested_max_output_tokens} ke {available_for_output - 100}")
            actual_max_tokens = available_for_output - 100  # Sisakan 100 tokens untuk buffer
        else:
            actual_max_tokens = requested_max_output_tokens
        
        print(f"[LLM] ========== TOKEN BREAKDOWN ==========")
        print(f"[LLM] INPUT TOKENS (yang dikirim ke LLM):")
        print(f"  - Context data (coffee shops + reviews): ~{estimated_context_tokens} tokens")
        print(f"  - System prompt (aturan & format): ~{estimated_system_tokens} tokens")
        print(f"  - User prompt (kata kunci user): ~{estimated_user_tokens} tokens")
        print(f"  - TOTAL INPUT: {estimated_total_input_tokens} tokens")
        print(f"[LLM] OUTPUT TOKENS (response dari LLM):")
        print(f"  - Max output (requested): {requested_max_output_tokens} tokens")
        print(f"  - Max output (actual): {actual_max_tokens} tokens")
        print(f"[LLM] TOTAL USAGE:")
        print(f"  - Estimated total: {estimated_total_input_tokens + actual_max_tokens} tokens")
        print(f"  - Model context window: 8,192 tokens")
        print(f"  - Available space: {8192 - (estimated_total_input_tokens + actual_max_tokens)} tokens")
        print(f"[LLM] =====================================")
        
        # Warning jika total usage melebihi context window
        if estimated_total_input_tokens + actual_max_tokens > 8192:
            print(f"[ERROR] Total usage ({estimated_total_input_tokens + actual_max_tokens} tokens) MELEBIHI context window (8,192 tokens)!")
            print(f"[ERROR] URGENT: Kurangi max_shops atau jumlah review per shop!")
        elif estimated_total_input_tokens + actual_max_tokens > 7500:
            print(f"[WARNING] Total usage ({estimated_total_input_tokens + actual_max_tokens} tokens) mendekati context window (8,192 tokens)!")
            print(f"[WARNING] Pertimbangkan mengurangi max_shops atau jumlah review per shop.")
        elif estimated_total_input_tokens > 5000:
            print(f"[INFO] Input tokens cukup besar ({estimated_total_input_tokens} tokens). Masih dalam batas aman.")
        
        # Step 4: Call Hugging Face Inference API dengan context
        print(f"[LLM] Calling HF API with task: {task}")
        print(f"[LLM] Model: {HF_MODEL}")
        
        response = hf_client.chat.completions.create(
            model=HF_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            max_tokens=actual_max_tokens,  # Gunakan max_tokens yang sudah disesuaikan dengan context window
            temperature=0.2,  # Ditingkatkan dari 0.1 untuk output yang lebih natural namun tetap akurat
            top_p=0.85  # Sedikit lebih fleksibel untuk variasi output yang lebih baik
        )
        
        print(f"[LLM] Response received successfully")
        generated_text = response.choices[0].message.content
        print(f"[LLM] Generated text length: {len(generated_text)} characters")
        print(f"[LLM] Generated text preview (first 200 chars): {generated_text[:200]}")
        print(f"[LLM] Generated text preview (last 200 chars): {generated_text[-200:]}")
        
        # Validasi dan Post-processing: Pastikan setiap rekomendasi memiliki review
        import re
        
        try:
            # Baca data untuk post-processing
            places_json_path = os.path.join('frontend-cofind', 'src', 'data', 'places.json')
            reviews_json_path = os.path.join('frontend-cofind', 'src', 'data', 'reviews.json')
            
            # Baca places.json dan reviews.json
            coffee_shops_data = []
            reviews_by_place_id = {}
            if os.path.exists(places_json_path):
                with open(places_json_path, 'r', encoding='utf-8') as f:
                    places_data = json.load(f)
                    coffee_shops_data = places_data.get('data', [])
            
            if os.path.exists(reviews_json_path):
                with open(reviews_json_path, 'r', encoding='utf-8') as f:
                    reviews_data = json.load(f)
                    reviews_by_place_id = reviews_data.get('reviews_by_place_id', {})
        except Exception as e:
            print(f"[ERROR] Failed to load data for post-processing: {e}")
            coffee_shops_data = []
            reviews_by_place_id = {}
        
        # Parse coffee shop recommendations dari response
        shop_pattern = r'(\d+)\.\s*\*\*([^*]+)\*\*'
        shop_matches = list(re.finditer(shop_pattern, generated_text))
        num_recommended_shops = len(shop_matches)
        
        print(f"[LLM] Validation: Found {num_recommended_shops} recommended shops")
        
        # Process setiap coffee shop untuk memastikan ada review
        if num_recommended_shops > 0:
            # Process dari belakang ke depan untuk menghindari masalah index saat insert
            for match_idx in range(len(shop_matches) - 1, -1, -1):
                shop_match = shop_matches[match_idx]
                shop_number = int(shop_match.group(1))
                shop_name = shop_match.group(2).strip()
                
                # Tentukan batas section (dari match ini sampai match berikutnya atau akhir)
                section_start = shop_match.start()
                section_end = shop_matches[match_idx + 1].start() if match_idx + 1 < len(shop_matches) else len(generated_text)
                shop_section = generated_text[section_start:section_end]
                
                # Cek apakah sudah ada review
                has_review = 'Berdasarkan Ulasan Pengunjung:' in shop_section or 'Berdasarkan ulasan pengunjung:' in shop_section.lower()
                
                if not has_review:
                    print(f"[LLM] ⚠️ Coffee shop #{shop_number} ({shop_name}) TIDAK memiliki review, attempting to add...")
                    
                    # Cari coffee shop di data berdasarkan nama (dengan fuzzy matching)
                    shop_found = None
                    shop_name_lower = shop_name.lower().strip()
                    
                    # Exact match first
                    for shop in coffee_shops_data:
                        if shop.get('name', '').strip().lower() == shop_name_lower:
                            shop_found = shop
                            break
                    
                    # Fuzzy match jika exact match tidak ditemukan
                    if not shop_found:
                        for shop in coffee_shops_data:
                            shop_data_name = shop.get('name', '').strip().lower()
                            # Cek apakah nama mengandung kata-kata penting dari shop_name
                            shop_name_words = set(shop_name_lower.split())
                            shop_data_words = set(shop_data_name.split())
                            # Jika minimal 2 kata match, anggap sama
                            if len(shop_name_words & shop_data_words) >= 2:
                                shop_found = shop
                                break
                            # Atau jika shop_name adalah substring dari shop_data_name atau sebaliknya
                            if shop_name_lower in shop_data_name or shop_data_name in shop_name_lower:
                                shop_found = shop
                                break
                    
                    if shop_found:
                        place_id = shop_found.get('place_id', '')
                        shop_reviews = reviews_by_place_id.get(place_id, [])
                        
                        if shop_reviews:
                            # Cari review yang relevan dengan keywords user
                            relevant_review = None
                            
                            # Ambil keywords dari expanded_keywords jika ada
                            user_keywords = []
                            if 'expanded_keywords' in locals() and expanded_keywords:
                                user_keywords = expanded_keywords
                            elif 'keywords' in locals() and keywords:
                                user_keywords = keywords
                            
                            # PENTING: Hanya tambahkan review jika BENAR-BENAR relevan dengan keywords user
                            # JANGAN tambahkan review yang tidak relevan
                            if user_keywords:
                                # Cari review yang mengandung minimal salah satu keyword (maksimal 2 reviews)
                                relevant_reviews_list = []
                                for review in shop_reviews:
                                    review_text = review.get('text', '').strip()
                                    if review_text and len(review_text) > 20:
                                        review_lower = review_text.lower()
                                        # Cek apakah review mengandung salah satu keyword
                                        is_relevant = False
                                        for kw in user_keywords:
                                            kw_lower = kw.lower().strip()
                                            # Minimal 3 karakter untuk menghindari false positive
                                            if len(kw_lower) >= 3:
                                                # Cek substring match (termasuk untuk multi-word keywords seperti "live music")
                                                # Contoh: "live music" akan match dengan "live music-nya", "live music", "musik", dll
                                                if kw_lower in review_lower:
                                                    is_relevant = True
                                                    print(f"[LLM] ✅ Found relevant review for {shop_name}: keyword '{kw}' found in review")
                                                    print(f"[LLM] Review snippet: {review_text[:100]}...")
                                                    break
                                        
                                        if is_relevant:
                                            relevant_reviews_list.append(review)
                                            # Maksimal 2 reviews per coffee shop
                                            if len(relevant_reviews_list) >= 2:
                                                break
                                
                                if not relevant_reviews_list:
                                    print(f"[LLM] ⚠️ No relevant review found for {shop_name} with keywords: {user_keywords}")
                                    print(f"[LLM] ⚠️ SKIPPING review addition - coffee shop should not be recommended without relevant review")
                                    print(f"[LLM] ⚠️ Coffee shop ini akan dihapus dari response oleh filter karena tidak ada review relevan")
                            else:
                                # Jika tidak ada keywords, JANGAN tambahkan review (untuk keamanan)
                                print(f"[LLM] ⚠️ No keywords available - SKIPPING review addition for safety")
                                print(f"[LLM] ⚠️ Coffee shop ini akan dihapus dari response oleh filter karena tidak ada keywords untuk validasi")
                            
                            if relevant_reviews_list:
                                # Insert maksimal 2 reviews
                                reviews_to_insert = relevant_reviews_list[:2]
                                
                                # Cari posisi untuk insert (setelah Google Maps URL)
                                maps_pattern = r'Google Maps:\s*[^\n]+'
                                maps_match = re.search(maps_pattern, shop_section)
                                
                                if maps_match:
                                    # Insert setelah Google Maps (pastikan ada newline)
                                    insert_pos = section_start + maps_match.end()
                                    
                                    # Format semua review lines
                                    review_lines = []
                                    for review in reviews_to_insert:
                                        review_text = review.get('text', '').strip()
                                        if len(review_text) > 150:
                                            review_text = review_text[:147] + "..."
                                        author_name = review.get('author_name', 'Anonim')
                                        review_rating = review.get('rating', 0)
                                        
                                        # Format review line (sesuai format yang diharapkan frontend)
                                        review_line = f"\nBerdasarkan Ulasan Pengunjung: \"{review_text}\" - {author_name} ({review_rating}⭐)"
                                        review_lines.append(review_line)
                                    
                                    # Gabungkan semua review lines
                                    all_reviews_text = ''.join(review_lines)
                                    
                                    # Pastikan ada newline sebelum review
                                    if generated_text[insert_pos:insert_pos+1] != '\n':
                                        all_reviews_text = '\n' + all_reviews_text.lstrip('\n')
                                    
                                    generated_text = generated_text[:insert_pos] + all_reviews_text + generated_text[insert_pos:]
                                    print(f"[LLM] ✅ Added {len(reviews_to_insert)} review(s) for {shop_name} (after Google Maps at position {insert_pos})")
                                    for idx, review in enumerate(reviews_to_insert, 1):
                                        print(f"[LLM] Review #{idx} preview: {review.get('text', '')[:100]}...")
                                else:
                                    # Jika tidak ada Google Maps, cari setelah Alamat
                                    address_pattern = r'Alamat:\s*[^\n]+'
                                    address_match = re.search(address_pattern, shop_section)
                                    if address_match:
                                        insert_pos = section_start + address_match.end()
                                        if generated_text[insert_pos:insert_pos+1] != '\n':
                                            review_line = '\n' + review_line.lstrip('\n')
                                        generated_text = generated_text[:insert_pos] + review_line + generated_text[insert_pos:]
                                        print(f"[LLM] ✅ Added review for {shop_name} (after address at position {insert_pos})")
                                        print(f"[LLM] Review preview: {review_line[:100]}...")
                                    else:
                                        # Fallback: insert setelah rating
                                        rating_pattern = r'Rating:\s*[^\n]+'
                                        rating_match = re.search(rating_pattern, shop_section)
                                        if rating_match:
                                            insert_pos = section_start + rating_match.end()
                                            if generated_text[insert_pos:insert_pos+1] != '\n':
                                                review_line = '\n' + review_line.lstrip('\n')
                                            generated_text = generated_text[:insert_pos] + review_line + generated_text[insert_pos:]
                                            print(f"[LLM] ✅ Added review for {shop_name} (after rating at position {insert_pos})")
                                            print(f"[LLM] Review preview: {review_line[:100]}...")
                                        else:
                                            # Last resort: insert di akhir section
                                            if generated_text[section_end-1:section_end] != '\n':
                                                review_line = '\n' + review_line.lstrip('\n')
                                            generated_text = generated_text[:section_end] + review_line + generated_text[section_end:]
                                            print(f"[LLM] ✅ Added review for {shop_name} (at end of section)")
                                            print(f"[LLM] Review preview: {review_line[:100]}...")
                            else:
                                print(f"[LLM] ❌ No relevant reviews found for {shop_name} with keywords: {user_keywords if user_keywords else 'N/A'}")
                                print(f"[LLM] ⚠️ Coffee shop ini TIDAK BOLEH direkomendasikan karena tidak ada review yang relevan!")
                                print(f"[LLM] ⚠️ LLM seharusnya TIDAK merekomendasikan coffee shop ini. Ini adalah masalah di output LLM.")
                        else:
                            print(f"[LLM] ❌ No reviews in data for {shop_name} (place_id: {place_id})")
                            print(f"[LLM] ⚠️ Coffee shop ini TIDAK BOLEH direkomendasikan karena tidak ada review di data!")
                    else:
                        print(f"[LLM] ❌ Coffee shop {shop_name} not found in places.json")
                        print(f"[LLM] ⚠️ Coffee shop ini tidak ditemukan di data, mungkin nama tidak match.")
                else:
                    print(f"[LLM] ✅ Coffee shop #{shop_number} ({shop_name}) already has review")
        
        # Re-validate setelah post-processing
        final_review_matches = re.findall(r'Berdasarkan Ulasan Pengunjung:', generated_text, re.IGNORECASE)
        final_num_reviews = len(final_review_matches)
        print(f"[LLM] Final validation: {num_recommended_shops} shops, {final_num_reviews} reviews")
        print(f"[LLM] Final text length: {len(generated_text)} characters")
        
        # Filter: Hapus coffee shop yang tidak memiliki review relevan dari response
        # PENTING: Filter ini akan menghapus coffee shop yang reviewnya tidak relevan dengan keywords user
        print(f"[LLM] ========== FILTERING COFFEE SHOPS ==========")
        print(f"[LLM] Total recommended shops: {num_recommended_shops}")
        print(f"[LLM] Total reviews found: {final_num_reviews}")
        
        if num_recommended_shops > 0 and final_num_reviews < num_recommended_shops:
            missing_count = num_recommended_shops - final_num_reviews
            print(f"[WARNING] ⚠️ Masih ada {missing_count} coffee shop(s) tanpa review setelah post-processing!")
            print(f"[WARNING] Removing coffee shops without relevant reviews from response...")
            
            # Parse semua coffee shop dari response
            shop_pattern_final = r'(\d+)\.\s*\*\*([^*]+)\*\*'
            all_shop_matches = list(re.finditer(shop_pattern_final, generated_text))
            
            # Filter: Hanya keep coffee shop yang memiliki review RELEVAN dengan keywords
            filtered_sections = []
            shop_counter = 1
            
            # Ambil keywords untuk validasi relevansi (PENTING: gunakan expanded_keywords untuk matching yang lebih baik)
            user_keywords_for_filter = []
            if 'expanded_keywords' in locals() and expanded_keywords:
                user_keywords_for_filter = expanded_keywords
                print(f"[LLM] Using expanded_keywords for filter: {user_keywords_for_filter[:10]}... (total: {len(user_keywords_for_filter)})")
            elif 'keywords' in locals() and keywords:
                user_keywords_for_filter = keywords
                print(f"[LLM] Using keywords for filter: {user_keywords_for_filter}")
            else:
                print(f"[LLM] ⚠️ No keywords available for filter validation!")
            
            for idx, match in enumerate(all_shop_matches):
                shop_number = int(match.group(1))
                shop_name = match.group(2).strip()
                
                # Tentukan batas section
                section_start = match.start()
                section_end = all_shop_matches[idx + 1].start() if idx + 1 < len(all_shop_matches) else len(generated_text)
                shop_section = generated_text[section_start:section_end]
                
                # Cek apakah memiliki review
                has_review = 'Berdasarkan Ulasan Pengunjung:' in shop_section or 'Berdasarkan ulasan pengunjung:' in shop_section.lower()
                
                if has_review:
                    # PENTING: Cek apakah review BENAR-BENAR relevan dengan keywords user
                    is_relevant = False
                    if user_keywords_for_filter:
                        # Extract review text dari section
                        review_match = re.search(r'Berdasarkan Ulasan Pengunjung:\s*"([^"]+)"', shop_section, re.IGNORECASE)
                        if review_match:
                            review_text_lower = review_match.group(1).lower()
                            # Cek apakah review mengandung minimal salah satu keyword
                            for kw in user_keywords_for_filter:
                                kw_lower = kw.lower().strip()
                                if len(kw_lower) >= 3 and kw_lower in review_text_lower:
                                    is_relevant = True
                                    print(f"[LLM] ✅ Review is relevant for {shop_name}: keyword '{kw}' found")
                                    break
                        else:
                            # Jika tidak bisa extract review text, HAPUS coffee shop (untuk keamanan)
                            is_relevant = False
                            print(f"[LLM] ⚠️ Could not extract review text for {shop_name} - REMOVING for safety")
                    else:
                        # Jika tidak ada keywords, HAPUS coffee shop (untuk keamanan)
                        is_relevant = False
                        print(f"[LLM] ⚠️ No keywords available for validation - REMOVING {shop_name} for safety")
                    
                    if is_relevant:
                        # Renumber shop jika perlu
                        if shop_counter != shop_number:
                            shop_section = re.sub(rf'^{shop_number}\.', f'{shop_counter}.', shop_section, flags=re.MULTILINE)
                        filtered_sections.append(shop_section)
                        print(f"[LLM] ✅ Keeping coffee shop #{shop_counter} ({shop_name}) - has relevant review")
                        shop_counter += 1
                    else:
                        print(f"[LLM] ❌ Removing coffee shop #{shop_number} ({shop_name}) - review NOT relevant with keywords: {user_keywords_for_filter}")
                else:
                    print(f"[LLM] ❌ Removing coffee shop #{shop_number} ({shop_name}) - NO review at all")
            
            # Rebuild response dengan hanya coffee shop yang memiliki review
            if filtered_sections:
                # Ambil bagian sebelum coffee shop pertama (jika ada)
                first_shop_match = all_shop_matches[0] if all_shop_matches else None
                prefix = generated_text[:first_shop_match.start()] if first_shop_match else ""
                
                # Gabungkan semua section yang valid dengan newline
                generated_text = prefix + "\n\n".join(filtered_sections)
                print(f"[LLM] ✅ Filtered response: {len(filtered_sections)} coffee shop(s) with reviews kept (removed {missing_count} without reviews)")
            else:
                # Jika tidak ada coffee shop dengan review, return message
                generated_text = "Maaf, tidak ada coffee shop yang sesuai dengan preferensi Anda saat ini."
                print(f"[LLM] ⚠️ No coffee shops with relevant reviews found. Returning default message.")
        else:
            print(f"[LLM] ✅ Semua coffee shop memiliki review!")
        
        # Format keywords untuk ditampilkan (dengan format yang lebih readable)
        # Capitalize first letter of each keyword untuk tampilan yang lebih baik
        # Pastikan keywords sudah didefinisikan (dari ekstraksi sebelumnya)
        if 'keywords' in locals() and keywords:
            formatted_keywords = []
            for kw in keywords:
                # Capitalize setiap kata dalam keyword (untuk multi-word seperti "wifi kencang")
                words = kw.split()
                capitalized_words = [w.capitalize() for w in words]
                formatted_keywords.append(' '.join(capitalized_words))
            extracted_keywords_display = ', '.join(formatted_keywords)
        else:
            # Fallback ke input asli jika keywords tidak tersedia
            extracted_keywords_display = user_text
        
        return jsonify({
            'status': 'success',
            'task': task,
            'input': user_text,  # Input asli dari user
            'extracted_keywords': extracted_keywords_display,  # Keywords yang sudah diekstrak oleh LLM
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

# Endpoint untuk LLM Chat - lebih interactive dengan context dari file JSON lokal
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
        
        # Fetch coffee shops data untuk context dari JSON lokal
        places_context = _fetch_coffeeshops_with_reviews_from_json(location, max_shops=30)
        
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
