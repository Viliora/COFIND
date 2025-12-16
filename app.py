from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
import json
import re  # Untuk regex operations
from dotenv import load_dotenv
import time  # Tambahkan untuk penundaan
from datetime import datetime, timedelta
from huggingface_hub import InferenceClient

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS

# Configure Hugging Face Inference API (gunakan env, jangan hardcode token)
HF_API_TOKEN = os.getenv('HF_API_TOKEN')  # Pastikan diset di environment (.env)
HF_MODEL = os.getenv('HF_MODEL', "meta-llama/Llama-3.1-8B-Instruct")  # default model

# Initialize Hugging Face Inference Client (optional)
hf_client = None
if HF_API_TOKEN:
    hf_client = InferenceClient(api_key=HF_API_TOKEN)
else:
    print("[WARNING] HF_API_TOKEN tidak diset. Endpoint LLM akan nonaktif.")

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

# Daftar keywords yang tidak relevan dengan coffee shop (tidak perlu dianalisis oleh LLM)
IRRELEVANT_KEYWORDS = [
    # Hewan yang tidak relevan
    'dinosaurus', 'dinosaur', 'musang', 'kijang', 'rusa', 'gajah', 'harimau', 'singa', 'beruang',
    'kucing', 'anjing', 'kelinci', 'tikus', 'burung', 'ikan', 'ular', 'buaya', 'kura-kura',
    'kuda', 'sapi', 'kerbau', 'ayam', 'bebek', 'angsa', 'merpati', 'elang', 'rajawali',
    # Benda/objek yang tidak relevan
    'mobil', 'motor', 'sepeda', 'pesawat', 'kapal', 'kereta', 'truk', 'bus',
    'gunung', 'laut', 'sungai', 'danau', 'hutan', 'pantai', 'pulau',
    # Aktivitas yang tidak relevan
    'berenang', 'mendaki', 'memancing', 'berkebun', 'memasak', 'menjahit',
    # Objek abstrak yang tidak relevan
    'planet', 'bintang', 'bulan', 'matahari', 'galaksi', 'nebula',
    # Kata-kata random lainnya yang jelas tidak relevan
    'alien', 'robot', 'monster', 'hantu', 'setan', 'jin', 'peri',
]

def _filter_irrelevant_keywords(keywords):
    """
    Filter keywords yang tidak relevan dengan konteks coffee shop.
    Hanya mengembalikan keywords yang relevan untuk dianalisis oleh LLM.
    
    Args:
        keywords: List of keywords (lowercase)
    
    Returns:
        Tuple: (relevant_keywords, irrelevant_keywords_found)
    """
    if not keywords:
        return [], []
    
    relevant_keywords = []
    irrelevant_found = []
    
    for keyword in keywords:
        keyword_lower = keyword.lower().strip()
        
        # Cek apakah keyword mengandung kata yang tidak relevan
        is_irrelevant = False
        for irrelevant_kw in IRRELEVANT_KEYWORDS:
            # Cek exact match atau substring match
            if irrelevant_kw in keyword_lower or keyword_lower in irrelevant_kw:
                is_irrelevant = True
                irrelevant_found.append(keyword)
                print(f"[KEYWORD FILTER] Filtered irrelevant keyword: '{keyword}' (matched: '{irrelevant_kw}')")
                break
        
        if not is_irrelevant:
            relevant_keywords.append(keyword)
    
    return relevant_keywords, irrelevant_found

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
                # PENTING: Untuk keyword spesifik seperti musholla, WAJIB ada di review
                has_relevant_review = False
                for review in shop_reviews:
                    review_text = (review.get('text', '') or '').strip().lower()
                    if review_text and len(review_text) > 20:
                        # Cek apakah review mengandung minimal salah satu keyword
                        # Untuk keyword spesifik (musholla, tempat sholat, dll), harus exact match atau sinonim
                        for kw in keywords:
                            kw_lower = kw.lower().strip()
                            if len(kw_lower) >= 3:
                                # Cek exact match atau substring match
                                if kw_lower in review_text:
                                    has_relevant_review = True
                                    print(f"[JSON+REVIEWS] ✅ Found relevant shop: {shop.get('name', 'Unknown')} (keyword: '{kw}')")
                                    break
                                # Cek sinonim untuk keyword spesifik
                                elif kw_lower in ['musholla', 'mushola', 'tempat sholat', 'ruang sholat', 'tempat ibadah']:
                                    # Cek sinonim musholla (termasuk variasi dengan "ada", "lokasi", dll)
                                    musholla_synonyms = ['musholla', 'mushola', 'tempat sholat', 'tempat sholat tersedia', 'ada musholla', 'ruang sholat', 'tempat ibadah', 'lokasi musholla', 'musholla yang', 'musholla nyaman']
                                    if any(syn in review_text for syn in musholla_synonyms):
                                        has_relevant_review = True
                                        print(f"[JSON+REVIEWS] ✅ Found relevant shop: {shop.get('name', 'Unknown')} (keyword: '{kw}' via synonym)")
                                        break
                                # Cek jika keyword adalah bagian dari frasa yang lebih panjang (misal: "ada musholla" dalam review)
                                elif 'musholla' in kw_lower or 'mushola' in kw_lower:
                                    # Jika keyword mengandung "musholla", cek apakah review mengandung "musholla" atau variasi
                                    if 'musholla' in review_text or 'mushola' in review_text or 'tempat sholat' in review_text:
                                        has_relevant_review = True
                                        print(f"[JSON+REVIEWS] ✅ Found relevant shop: {shop.get('name', 'Unknown')} (keyword: '{kw}' contains musholla)")
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
        
        # Hitung total reviews yang digunakan
        total_reviews = sum(len(reviews_by_place_id.get(shop.get('place_id', ''), [])) for shop in coffee_shops)
        
        print(f"[JSON+REVIEWS] Context prepared: {len(coffee_shops)} shops with reviews, {total_reviews} total reviews, {len(context)} characters")
        print(f"[JSON+REVIEWS] 📊 SUMMARY: {len(coffee_shops)} coffee shops akan dianalisis oleh LLM")
        if keywords and len(keywords) > 0:
            print(f"[JSON+REVIEWS] 📊 Pre-filtered: {len(relevant_shops_sorted)} relevant shops + {len(other_shops_sorted[:other_count])} top-rated shops")
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
        
        # Step 1: Ekstraksi keywords dari user input berdasarkan review data
        # Langkah ini akan menganalisis review data untuk mengekstrak keywords yang relevan
        print(f"[LLM] Step 1: Extracting keywords from user input based on review data...")
        
        # Baca reviews.json untuk context ekstraksi keywords
        reviews_json_path = os.path.join('frontend-cofind', 'src', 'data', 'reviews.json')
        reviews_data = {}
        reviews_context_for_extraction = ""
        
        if os.path.exists(reviews_json_path):
            with open(reviews_json_path, 'r', encoding='utf-8') as f:
                reviews_data = json.load(f)
            
            # Ambil sample reviews untuk context ekstraksi (maksimal 20 review dari berbagai coffee shop)
            reviews_by_place_id = reviews_data.get('reviews_by_place_id', {})
            sample_reviews = []
            for place_id, reviews in list(reviews_by_place_id.items())[:5]:  # Ambil 5 coffee shop pertama
                sample_reviews.extend(reviews[:4])  # 4 review per coffee shop
                if len(sample_reviews) >= 20:
                    break
            
            # Buat context untuk ekstraksi keywords
            reviews_context_for_extraction = "\n".join([
                f"- {review.get('text', '')}" for review in sample_reviews[:20]
            ])
        
        # Buat prompt untuk ekstraksi keywords berdasarkan review data
        extraction_prompt = f"""Anda adalah asisten yang ahli dalam menganalisis preferensi user berdasarkan review coffee shop yang tersedia.

REVIEW DATA YANG TERSEDIA (contoh dari berbagai coffee shop):
{reviews_context_for_extraction[:2000]}

INPUT USER:
"{user_text}"

Tugas Anda: 
1. Analisis input user dan identifikasi keywords yang relevan dengan atribut coffee shop (fasilitas, suasana, kebutuhan spesifik)
2. Cek apakah keywords tersebut ada di review data yang tersedia atau relevan dengan atribut coffee shop yang umum
3. Hanya ekstrak keywords yang BENAR-BENAR relevan dengan atribut coffee shop yang ada di review data
4. Abaikan kata-kata yang tidak relevan atau tidak ada di review data (seperti hewan, benda, aktivitas yang tidak berhubungan)

ATURAN:
- Keywords harus relevan dengan atribut coffee shop yang ada di review data: wifi, wifi bagus, wifi kencang, colokan, colokan banyak, cozy, nyaman, tenang, hangat, musholla, parkir, parkir luas, 24 jam, buka malam, aesthetic, live music, ac, dingin, sejuk, sofa, kursi, belajar, kerja, gaming, ngegame, dll
- Abaikan kata-kata umum: "saya", "ingin", "mencari", "yang", "untuk", "dan", "atau", "dengan", "ada", "adalah", "ini", "itu", "di", "ke", "dari", "pada", "oleh", "coffee", "shop", "tempat", "cafe"
- Abaikan kata-kata yang tidak relevan dengan coffee shop: hewan (dinosaurus, musang, kijang, dll), benda yang tidak berhubungan, aktivitas yang tidak relevan
- Output HANYA keywords yang dipisah koma, tanpa penjelasan
- Gunakan bahasa Indonesia
- Maksimal 10 keywords
- Jika tidak ada keywords yang relevan, output: "TIDAK_ADA_KEYWORDS"

CONTOH:
Input: "Saya ingin coffee shop yang cozy untuk nugas dengan wifi yang bagus dan banyak colokan"
Output: cozy, wifi bagus, colokan banyak, belajar

Input: "Tempat yang nyaman dengan musholla dan parkir luas"
Output: nyaman, musholla, parkir luas

Input: "Coffee shop aesthetic dengan live music dan ruangan dingin"
Output: aesthetic, live music, ruangan dingin

Input: "Saya butuh tempat yang ada dinosaurus dan musang"
Output: TIDAK_ADA_KEYWORDS

Sekarang analisis input user dan ekstrak keywords yang relevan:"""

        # Ekstraksi keywords menggunakan LLM
        extracted_keywords_text = ""
        try:
            if hf_client:
                extraction_response = hf_client.text_generation(
                    extraction_prompt,
                    max_new_tokens=100,
                    temperature=0.3,
                    return_full_text=False
                )
                extracted_keywords_text = extraction_response.strip()
                # Bersihkan dari format markdown atau karakter aneh
                extracted_keywords_text = extracted_keywords_text.replace('**', '').replace('*', '').replace('"', '').replace("'", '').strip()
                print(f"[LLM] Extracted keywords text: {extracted_keywords_text}")
            else:
                # Fallback: gunakan metode sederhana
                words = user_text.lower().split()
                stop_words = {'saya', 'ingin', 'mencari', 'yang', 'untuk', 'dan', 'atau', 'dengan', 'ada', 'adalah', 'ini', 'itu', 'di', 'ke', 'dari', 'pada', 'oleh', 'coffee', 'shop', 'tempat', 'cafe'}
                extracted_keywords_text = ', '.join([w for w in words if w not in stop_words and len(w) > 2])
        except Exception as e:
            print(f"[LLM] Error extracting keywords: {e}")
            # Fallback: gunakan metode sederhana
            words = user_text.lower().split()
            stop_words = {'saya', 'ingin', 'mencari', 'yang', 'untuk', 'dan', 'atau', 'dengan', 'ada', 'adalah', 'ini', 'itu', 'di', 'ke', 'dari', 'pada', 'oleh', 'coffee', 'shop', 'tempat', 'cafe'}
            extracted_keywords_text = ', '.join([w for w in words if w not in stop_words and len(w) > 2])
        
        # Parse keywords dari hasil ekstraksi
        if extracted_keywords_text.upper() == "TIDAK_ADA_KEYWORDS" or not extracted_keywords_text:
            print(f"[LLM] ⚠️ Tidak ada keywords yang relevan ditemukan")
            return jsonify({
                'status': 'success',
                'task': task,
                'input': user_text,
                'extracted_keywords': '',
                'preferences_ai': 'Tidak ada keywords yang relevan dengan preferensi coffee shop',
                'analysis': 'Maaf, tidak ada coffee shop yang sesuai dengan preferensi Anda saat ini.',
                'timestamp': time.time()
            }), 200
        
        # Parse keywords dari hasil ekstraksi
        keywords = [kw.strip().lower() for kw in extracted_keywords_text.split(',') if kw.strip()]
        
        # Filter keywords yang tidak relevan dengan konteks coffee shop
        keywords, irrelevant_found = _filter_irrelevant_keywords(keywords)
        
        # Jika semua keywords tidak relevan setelah filtering, kembalikan error
        if not keywords:
            print(f"[LLM] ⚠️ Semua keywords tidak relevan setelah filtering")
            return jsonify({
                'status': 'success',
                'task': task,
                'input': user_text,
                'extracted_keywords': ', '.join(irrelevant_found) if irrelevant_found else '',
                'preferences_ai': 'Tidak ada keywords yang relevan dengan preferensi coffee shop',
                'analysis': 'Maaf, tidak ada coffee shop yang sesuai dengan preferensi Anda saat ini.',
                'timestamp': time.time()
            }), 200
        
        # Filter "butuh" dan stop words lainnya dari keywords sebelum digunakan
        # Pastikan hanya keyword yang relevan yang digunakan
        stop_words_final = {'butuh', 'perlu', 'ingin', 'mau', 'cari', 'mencari', 'ada', 'yang', 'untuk', 'dengan', 'dan', 'atau', 'dari', 'pada', 'oleh', 'saya', 'aku', 'kita', 'kami'}
        final_keywords = []
        for kw in keywords:
            kw_lower = kw.lower().strip()
            # Jika keyword adalah stop word tunggal, skip
            if kw_lower in stop_words_final and len(kw.split()) == 1:
                continue
            # Jika keyword mengandung stop word sebagai bagian dari frasa (misal: "ada musholla"), pertahankan
            if len(kw) >= 3:
                final_keywords.append(kw)
        # Jika setelah filtering keywords kosong, gunakan keywords asli (untuk safety)
        if not final_keywords:
            final_keywords = keywords
        keywords = final_keywords
        
        # Buat preferences_ai untuk ditampilkan di frontend
        preferences_ai = f"Preferensi berdasarkan analisis AI: {', '.join(keywords)}"
        print(f"[LLM] ✅ Preferences AI: {preferences_ai}")
        print(f"[LLM] ✅ Final keywords (after filtering stop words): {keywords}")
        
        # Gunakan keywords yang sudah diekstrak untuk analisis selanjutnya
        # Filtered user text sekarang hanya berisi keywords yang relevan
        filtered_user_text = ', '.join(keywords)
        
        # Expand keywords dengan sinonim untuk pre-filtering yang lebih baik
        if keywords:
            expanded_keywords_for_filter = _expand_keywords_with_synonyms(keywords)
            print(f"[LLM] Pre-filtering with expanded keywords: {expanded_keywords_for_filter[:10]}... (total: {len(expanded_keywords_for_filter)})")
        else:
            expanded_keywords_for_filter = []
        
        # Step 2: Fetch coffee shops DENGAN REVIEWS dari file JSON lokal
        # PENTING: Gunakan expanded keywords untuk pre-filtering coffee shops yang relevan
        # Jika ada keywords spesifik (seperti musholla), prioritaskan coffee shop yang relevan
        # Kurangi max_shops jika ada keywords untuk mengurangi context size dan menghindari melebihi token limit
        # Jika ada keywords relevan, prioritaskan hanya coffee shop yang relevan (max 5-8 shops)
        max_shops_for_context = 8 if keywords and len(keywords) > 0 else 15  # Kurangi jika ada keywords spesifik
        print(f"[LLM] Fetching coffee shops WITH REVIEWS from local JSON files for location: {location}")
        print(f"[LLM] Using max_shops={max_shops_for_context} to reduce context size (keywords: {len(keywords) if keywords else 0})")
        places_context = _fetch_coffeeshops_with_reviews_from_json(location, max_shops=max_shops_for_context, keywords=expanded_keywords_for_filter)
        
        # Debug: Print sample reviews untuk verify data
        print(f"[LLM] Context preview (first 500 chars):")
        print(places_context[:500] if len(places_context) > 500 else places_context)
        print(f"[LLM] Total context length: {len(places_context)} characters")
        
        # Hitung jumlah coffee shop yang ada di context
        shop_count_in_context = len(re.findall(r'^\d+\.\s+', places_context, re.MULTILINE))
        print(f"[LLM] 📊 Coffee shops dalam context untuk LLM: {shop_count_in_context} shops")
        
        # Log informasi tentang apa yang dikirim ke LLM
        print(f"[LLM] ========== INFORMASI ANALISIS LLM ==========")
        print(f"[LLM] ✅ Irrelevant keywords SUDAH DIFILTER sebelum dikirim ke LLM")
        print(f"[LLM] ✅ Irrelevant keywords yang difilter: {irrelevant_found if irrelevant_found else 'Tidak ada'}")
        print(f"[LLM] ✅ Keywords relevan yang digunakan: {keywords}")
        print(f"[LLM] ✅ Filtered user text yang dikirim ke LLM: '{filtered_user_text}'")
        print(f"[LLM] ✅ Expanded keywords untuk pre-filtering: {expanded_keywords_for_filter[:10]}... (total: {len(expanded_keywords_for_filter)})")
        print(f"[LLM] ============================================")
        
        # Step 2: Build system prompt dengan context REVIEWS untuk bukti rekomendasi
        system_prompt = f"""Anda adalah asisten rekomendasi coffee shop yang AKURAT dan JUJUR. Anda menggunakan data NYATA dari file JSON lokal dan menganalisis input user menggunakan Natural Language Processing (NLP).

DATA COFFEE SHOP DI {location.upper()} DENGAN INFORMASI LENGKAP:
{places_context}

🎯 ATURAN UTAMA - ANALISIS MENDALAM SEBELUM REKOMENDASI:
⚠️ PENTING: SEBELUM memberikan rekomendasi, WAJIB lakukan analisis mendalam terlebih dahulu untuk mengekstrak HANYA atribut pilihan/kriteria coffee shop yang relevan.

1. Analisis input user menggunakan Natural Language Processing untuk memahami maksud dan preferensi
2. Identifikasi HANYA kata-kata yang berkaitan dengan atribut pilihan/kriteria coffee shop:
   - Sifat-sifat: nyaman, cozy, tenang, hangat, santai, ramai, sepi, dll
   - Fasilitas: wifi, colokan, terminal listrik, musholla, printer, scanner, AC, sofa, kursi nyaman, dll
   - Jam operasional: 24 jam, buka malam, buka sampai larut, dll
   - Lokasi/parkir: parkir luas, parkir mudah, akses mudah, dll
   - Suasana/atmosfer: aesthetic, instagramable, live music, akustik, dll
   - Kebutuhan spesifik: cocok untuk kerja, belajar, meeting, gaming, dll
3. ABAIKAN semua kata yang TIDAK relevan dengan atribut pilihan/kriteria coffee shop (hewan, benda, aktivitas yang tidak berhubungan, dll)
4. Input user bisa berupa kalimat natural language (tidak terstruktur) atau kata kunci
5. Pahami konteks, sinonim, dan makna dari input user (bukan hanya keyword matching)
6. HANYA rekomendasikan jika ADA review yang relevan dengan atribut pilihan yang sudah diekstrak
7. Review harus BENAR-BENAR menyebutkan atau berhubungan erat dengan atribut pilihan yang sudah diekstrak
8. Jika tidak ada review yang relevan, JANGAN rekomendasikan - langsung jawab: "Maaf, tidak ada coffee shop yang sesuai dengan preferensi Anda saat ini."
9. JANGAN memberikan rekomendasi yang dipaksakan atau diada-adakan

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
- Untuk keyword SPESIFIK seperti "musholla", review WAJIB menyebutkan musholla atau sinonimnya (tempat sholat, ruang sholat, tempat ibadah, ada musholla, mushola)
- JANGAN merekomendasikan coffee shop jika review TIDAK menyebutkan keyword spesifik yang diminta user
- Contoh RELEVAN: 
  * User cari "wifi bagus" → Review: "wifinya kencang" ✅
  * User cari "musholla" → Review: "ada musholla" atau "tempat sholat tersedia" atau "musholla yang nyaman" ✅
  * User cari "musholla" → Review: "tempatnya nyaman" ❌ (TIDAK RELEVAN - tidak menyebutkan musholla)
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
        # CATATAN: Keywords sudah difilter di Step 1, jadi kita gunakan keywords yang sudah relevan
        # Untuk task 'analyze', kita tetap perlu extract keywords untuk display, tapi sudah menggunakan filtered_user_text
        # Cek apakah input adalah comma-separated keywords atau natural language
        if ',' in filtered_user_text and len(filtered_user_text.split(',')) > 1:
            # Format: comma-separated keywords
            keywords = [kw.strip().lower() for kw in filtered_user_text.split(',') if kw.strip()]
        else:
            # Format: natural language - extract keywords untuk pre-filtering (LLM akan melakukan deep NLP analysis)
            # Buat prompt untuk ekstraksi keyword dari natural language dengan fokus pada understanding
            extraction_prompt = f"""Anda adalah asisten yang ahli dalam memahami maksud user dari kalimat natural language.

KALIMAT USER:
"{filtered_user_text}"

Tugas Anda: Pahami maksud dan preferensi user, lalu ekstrak kata kunci penting yang relevan untuk mencari coffee shop.

ATURAN:
1. Pahami konteks dan maksud dari kalimat user (bukan hanya keyword matching)
2. Identifikasi preferensi inti: fasilitas, suasana, kebutuhan spesifik, dll
3. Ekstrak kata kunci yang relevan dengan coffee shop (wifi, musholla, colokan, cozy, belajar, kerja, sofa, ac, aesthetic, live music, parkir, 24 jam, dll)
4. Abaikan kata-kata umum seperti "saya", "ingin", "mencari", "yang", "untuk", "dan", "atau", dll
5. Output HANYA kata kunci yang dipisah koma, tanpa penjelasan
6. Gunakan bahasa Indonesia
7. Maksimal 10 kata kunci

CONTOH:
Input: "Saya ingin mencari coffee shop yang cozy, ada wifi kencang, dan cocok untuk kerja"
Output: cozy, wifi kencang, kerja

Input: "Tempat yang nyaman dengan musholla dan parkir luas"
Output: nyaman, musholla, parkir luas

Input: "Saya butuh coffee shop yang ada musholla"
Output: musholla

Input: "Coffee shop aesthetic dengan live music dan ruangan dingin"
Output: aesthetic, live music, ruangan dingin

Input: "Saya butuh tempat yang buka sampai larut malam"
Output: 24 jam, buka malam, buka sampai larut

Sekarang pahami maksud user dan ekstrak kata kunci dari kalimat di atas:"""

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
                    
                    # Filter stop words dari keywords yang diekstrak
                    stop_words_keywords = {'butuh', 'perlu', 'ingin', 'mau', 'cari', 'mencari', 'ada', 'yang', 'untuk', 'dengan', 'dan', 'atau', 'dari', 'pada', 'oleh', 'saya', 'aku', 'kita', 'kami'}
                    # Filter: hapus stop words tunggal, tapi pertahankan jika menjadi bagian dari keyword multi-word
                    filtered_extracted_keywords = []
                    for kw in keywords:
                        kw_lower = kw.lower().strip()
                        # Jika keyword adalah stop word tunggal, skip
                        if kw_lower in stop_words_keywords and len(kw.split()) == 1:
                            continue
                        # Jika keyword mengandung stop word sebagai bagian dari frasa (misal: "ada musholla"), pertahankan
                        if len(kw) >= 3:
                            filtered_extracted_keywords.append(kw)
                    keywords = filtered_extracted_keywords
                    
                    # Jika ekstraksi gagal atau kosong, fallback ke split berdasarkan spasi
                    if not keywords:
                        print(f"[LLM] Keyword extraction returned empty, using fallback")
                        words = user_text.lower().split()
                        stop_words = {'saya', 'ingin', 'mencari', 'yang', 'untuk', 'dan', 'atau', 'dengan', 'adalah', 'ini', 'itu', 'di', 'ke', 'dari', 'pada', 'oleh', 'coffee', 'shop', 'tempat', 'cafe', 'yang', 'dengan', 'untuk'}
                        # CATATAN: "ada" TIDAK dihapus dari stop_words karena bisa menjadi bagian dari keyword seperti "ada musholla"
                        # Tapi jika "ada" berdiri sendiri tanpa keyword lain, akan difilter nanti
                        keywords = [w for w in words if w not in stop_words and len(w) > 2]
                    else:
                        print(f"[LLM] Extracted keywords: {keywords}")
                else:
                    # Jika hf_client tidak tersedia, gunakan fallback
                    print(f"[LLM] HF client not available, using fallback extraction")
                    words = filtered_user_text.lower().split()
                    stop_words = {'saya', 'ingin', 'mencari', 'yang', 'untuk', 'dan', 'atau', 'dengan', 'ada', 'adalah', 'ini', 'itu', 'di', 'ke', 'dari', 'pada', 'oleh', 'coffee', 'shop', 'tempat', 'cafe', 'yang', 'dengan', 'untuk', 'butuh', 'perlu', 'mau', 'cari'}
                    keywords = [w for w in words if w not in stop_words and len(w) > 2]
            except Exception as e:
                print(f"[LLM] Error extracting keywords: {e}")
                # Fallback: split berdasarkan spasi
                words = filtered_user_text.lower().split()
                stop_words = {'saya', 'ingin', 'mencari', 'yang', 'untuk', 'dan', 'atau', 'dengan', 'ada', 'adalah', 'ini', 'itu', 'di', 'ke', 'dari', 'pada', 'oleh', 'coffee', 'shop', 'tempat', 'cafe', 'yang', 'dengan', 'untuk'}
                keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        # Validasi: Pastikan keywords yang diekstrak benar-benar relevan dan memiliki instruksi yang jelas
        # Jika keywords tidak jelas atau hanya deskripsi umum tanpa instruksi spesifik, return pesan tidak ada
        def _validate_keywords_relevance(keywords_list):
            """
            Validasi apakah keywords yang diekstrak benar-benar relevan dan memiliki instruksi yang jelas.
            Keywords harus berupa atribut pilihan/kriteria coffee shop yang spesifik, bukan hanya deskripsi umum.
            
            Returns:
                Tuple: (is_valid, reason)
            """
            if not keywords_list or len(keywords_list) == 0:
                return False, "Tidak ada keywords yang diekstrak"
            
            # Daftar keywords yang valid (atribut pilihan/kriteria coffee shop)
            valid_keyword_patterns = [
                # Sifat-sifat/Suasana
                'nyaman', 'cozy', 'tenang', 'hangat', 'santai', 'ramai', 'sepi', 'asri', 'hijau', 'teduh',
                # Fasilitas Internet
                'wifi', 'internet', 'koneksi',
                # Fasilitas Listrik
                'colokan', 'terminal', 'stopkontak', 'listrik',
                # Fasilitas Ibadah
                'musholla', 'sholat', 'ibadah',
                # Fasilitas Kerja/Belajar
                'printer', 'scanner', 'fotocopy', 'meeting', 'kerja', 'belajar',
                # Fasilitas Tempat Duduk
                'sofa', 'kursi', 'meja',
                # Fasilitas Suhu
                'ac', 'dingin', 'sejuk', 'adem',
                # Jam Operasional
                '24 jam', 'buka', 'malam', 'larut', 'subuh',
                # Lokasi/Parkir
                'parkir', 'akses',
                # Suasana/Atmosfer
                'aesthetic', 'instagramable', 'estetik', 'kekinian', 'desain', 'dekor',
                # Hiburan
                'music', 'musik', 'akustik', 'live',
                # Kebutuhan Spesifik
                'gaming', 'ngegame', 'game', 'nongkrong', 'wfc', 'tugas'
            ]
            
            # Kata-kata umum yang tidak memiliki instruksi spesifik (hanya deskripsi)
            general_words = ['coffee', 'shop', 'tempat', 'cafe', 'kopi', 'minum', 'makan', 'enak', 'bagus', 'baik', 'saya', 'ingin', 'mencari', 'yang', 'untuk', 'dan', 'atau', 'dengan', 'ada', 'adalah', 'ini', 'itu', 'di', 'ke', 'dari', 'pada', 'oleh', 'butuh', 'perlu', 'mau', 'cari']
            
            # Cek apakah minimal salah satu keyword mengandung pattern yang valid
            has_valid_keyword = False
            valid_keywords_found = []
            
            for kw in keywords_list:
                kw_lower = kw.lower().strip()
                
                # Skip jika keyword hanya berisi kata-kata umum
                is_general = any(gw in kw_lower for gw in general_words) and len(kw_lower.split()) <= 2
                if is_general:
                    continue
                
                # Cek apakah keyword mengandung minimal salah satu pattern yang valid
                for pattern in valid_keyword_patterns:
                    if pattern in kw_lower or kw_lower in pattern:
                        has_valid_keyword = True
                        valid_keywords_found.append(kw)
                        break
            
            if not has_valid_keyword:
                return False, f"Keywords yang diekstrak tidak relevan dengan atribut pilihan coffee shop atau hanya berisi deskripsi umum: {keywords_list}"
            
            # Cek apakah keywords hanya berisi kata-kata umum tanpa instruksi spesifik
            # Jika semua keywords adalah general words, maka tidak valid
            all_general = all(any(gw in kw.lower() for gw in general_words) for kw in keywords_list if len(kw) > 0)
            
            if all_general and len(keywords_list) > 0:
                return False, f"Keywords hanya berisi kata-kata umum tanpa instruksi spesifik: {keywords_list}"
            
            return True, f"Keywords valid: {valid_keywords_found}"
        
        # Validasi keywords sebelum melanjutkan
        # CATATAN: Validasi ini hanya untuk memastikan keywords tidak kosong setelah filtering
        # Untuk natural language, LLM akan melakukan analisis mendalam sendiri
        # Jadi validasi ini tidak boleh terlalu ketat untuk natural language
        is_keywords_valid = True
        validation_reason = "Keywords akan dianalisis oleh LLM"
        
        # Hanya validasi jika keywords benar-benar kosong atau hanya berisi stop words
        if not keywords or len(keywords) == 0:
            is_keywords_valid = False
            validation_reason = "Tidak ada keywords yang relevan setelah filtering"
        else:
            # Untuk natural language, biarkan LLM yang menganalisis
            # Validasi ketat hanya untuk comma-separated keywords
            if ',' in filtered_user_text and len(filtered_user_text.split(',')) > 1:
                # Untuk comma-separated, lakukan validasi lebih ketat
                is_keywords_valid, validation_reason = _validate_keywords_relevance(keywords)
        
        if not is_keywords_valid:
            print(f"[LLM] ⚠️ Keywords validation failed: {validation_reason}")
            print(f"[LLM] Keywords extracted: {keywords}")
            print(f"[LLM] Returning empty result with message: 'tidak ada coffee shop yang sesuai preferensi'")
            return jsonify({
                'status': 'success',
                'task': task,
                'input': user_text,
                'extracted_keywords': ', '.join(keywords) if keywords else '',
                'analysis': 'Maaf, tidak ada coffee shop yang sesuai dengan preferensi Anda saat ini.',
                'timestamp': time.time()
            }), 200
        
        print(f"[LLM] ✅ Keywords validation passed: {validation_reason}")
        print(f"[LLM] Keywords yang akan digunakan: {keywords}")
        print(f"[LLM] Filtered user text yang dikirim ke LLM: '{filtered_user_text}'")
        
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
{filtered_user_text}

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

⚠️ VALIDASI KETAT UNTUK KEYWORD SPESIFIK:
- Untuk keyword SPESIFIK seperti "musholla", coffee shop HANYA boleh direkomendasikan jika review BENAR-BENAR menyebutkan "musholla", "mushola", "tempat sholat", "ruang sholat", "tempat ibadah", atau "ada musholla"
- JANGAN merekomendasikan coffee shop jika review TIDAK menyebutkan keyword spesifik yang diminta user
- Jika user mencari "musholla" dan review hanya menyebutkan "tempatnya nyaman" atau "wifi bagus" TANPA menyebutkan musholla, JANGAN rekomendasikan coffee shop tersebut

Cari coffee shop yang reviewnya BENAR-BENAR menyebutkan kata kunci di atas atau sinonimnya. Jika tidak ada yang sesuai, jawab: "Maaf, tidak ada coffee shop yang sesuai dengan preferensi Anda saat ini." Jangan tambahkan penjelasan pembuka atau logika rekomendasi."""
        elif task == 'recommend':
            user_content = f"""PREFERENSI SAYA (Natural Language):
"{filtered_user_text}"

⚠️ PENTING - ANALISIS MENDALAM SEBELUM REKOMENDASI:
Sebelum memberikan rekomendasi, WAJIB lakukan analisis mendalam terlebih dahulu untuk mengekstrak HANYA atribut pilihan/kriteria coffee shop yang relevan.

🔍 STEP 1: ANALISIS INPUT USER (WAJIB DILAKUKAN TERLEBIH DAHULU):
1. Baca dan pahami kalimat user dengan teliti menggunakan Natural Language Processing (NLP)
2. Identifikasi HANYA kata-kata yang berkaitan dengan:
   - ✅ Sifat-sifat coffee shop: nyaman, cozy, tenang, hangat, santai, ramai, sepi, dll
   - ✅ Fasilitas coffee shop: wifi, colokan, terminal listrik, musholla, tempat sholat, printer, scanner, AC, ruangan dingin, sofa, kursi nyaman, dll
   - ✅ Kebutuhan spesifik: cocok untuk kerja, belajar, meeting, nongkrong, gaming, dll
   - ✅ Jam operasional: 24 jam, buka malam, buka sampai larut, buka sampai subuh, dll
   - ✅ Lokasi/parkir: parkir luas, parkir mudah, akses mudah, dll
   - ✅ Suasana/atmosfer: aesthetic, instagramable, live music, akustik, dll
3. ABAIKAN semua kata yang TIDAK relevan dengan atribut pilihan/kriteria coffee shop:
   - ❌ Hewan, benda, atau objek yang tidak berhubungan dengan coffee shop
   - ❌ Aktivitas yang tidak relevan dengan konteks coffee shop
   - ❌ Kata-kata umum seperti "saya", "ingin", "mencari", "yang", "untuk", "dan", "atau", dll
4. Ekstrak HANYA keywords/atribut pilihan yang relevan dengan coffee shop
5. Identifikasi sinonim dan variasi kata yang relevan dengan atribut pilihan yang diekstrak

📋 CONTOH ANALISIS:
Input: "Saya butuh coffee shop yang ada dinosaurus, musang, dan kijang"
Analisis: ❌ TIDAK ADA atribut pilihan yang relevan - semua keywords tidak relevan dengan coffee shop
Kesimpulan: Tidak ada rekomendasi yang bisa diberikan

Input: "Saya ingin tempat yang nyaman dengan wifi bagus dan parkir luas"
Analisis: ✅ Atribut pilihan yang relevan: nyaman, wifi bagus, parkir luas
Kesimpulan: Cari coffee shop dengan review yang menyebutkan nyaman, wifi bagus, atau parkir luas

Input: "Coffee shop yang cozy, ada musholla, dan menyediakan printer"
Analisis: ✅ Atribut pilihan yang relevan: cozy, musholla, printer
Kesimpulan: Cari coffee shop dengan review yang menyebutkan cozy, musholla, atau printer

🎯 STEP 2: CARI COFFEE SHOP YANG RELEVAN:
Setelah analisis selesai dan atribut pilihan sudah diekstrak:
1. Cari coffee shop yang reviewnya BENAR-BENAR relevan dengan atribut pilihan yang sudah diekstrak
2. Review harus menyebutkan atau berhubungan erat dengan atribut pilihan yang relevan
3. HANYA rekomendasikan jika ada review yang relevan dengan atribut pilihan yang sudah diekstrak
4. Jika tidak ada review yang relevan, LANGSUNG jawab: "Maaf, tidak ada coffee shop yang sesuai dengan preferensi Anda saat ini."

📝 DAFTAR ATRIBUT PILIHAN/KRITERIA COFFEE SHOP YANG RELEVAN:
✅ Sifat-sifat/Suasana: nyaman, cozy, tenang, hangat, santai, ramai, sepi, asri, hijau, teduh, dll
✅ Fasilitas Internet: wifi, wifi bagus, wifi kencang, wifi stabil, koneksi internet lancar, internet cepat, dll
✅ Fasilitas Listrik: colokan, colokan banyak, terminal listrik, stopkontak, stopkontak banyak, colokan di setiap meja, dll
✅ Fasilitas Ibadah: musholla, tempat sholat, tempat sholat tersedia, ada musholla, dll
✅ Fasilitas Kerja/Belajar: printer, scanner, fotocopy, ruang meeting, ruang kerja, ruang belajar, dll
✅ Fasilitas Tempat Duduk: sofa, kursi nyaman, kursi empuk, ruas sofa, meja besar, meja kecil, dll
✅ Fasilitas Suhu: AC, ruangan dingin, sejuk, adem, ruangan sejuk, dll
✅ Jam Operasional: 24 jam, buka malam, buka sampai larut, buka sampai subuh, buka tengah malam, dll
✅ Lokasi/Parkir: parkir luas, parkir mudah, parkir mobil nyaman, akses mudah, dll
✅ Suasana/Atmosfer: aesthetic, instagramable, estetik, kekinian, desain bagus, dekor bagus, dll
✅ Hiburan: live music, musik, akustik, pertunjukan live music, dll
✅ Kebutuhan Spesifik: cocok untuk kerja, belajar, meeting, nongkrong, gaming, ngegame, dll

⚠️ ATURAN KETAT - WAJIB DIIKUTI (TIDAK BOLEH DILANGGAR):
1. WAJIB lakukan analisis mendalam terlebih dahulu (Step 1) sebelum memberikan rekomendasi (Step 2)
2. HANYA ekstrak atribut pilihan/kriteria yang relevan dengan coffee shop (lihat daftar di atas)
3. ABAIKAN semua kata yang TIDAK ada dalam daftar atribut pilihan yang relevan
4. HANYA rekomendasikan jika ada review yang BENAR-BENAR relevan dengan atribut pilihan yang sudah diekstrak
5. Review harus RELEVAN secara semantik - bukan sekedar review positif biasa
6. Pahami sinonim dan variasi kata yang relevan (contoh: "wifi bagus" = "wifi kencang" = "internet lancar")
7. JANGAN rekomendasikan coffee shop jika tidak ada review yang relevan dengan atribut pilihan yang sudah diekstrak
8. Jika tidak ada review yang relevan, LANGSUNG jawab: "Maaf, tidak ada coffee shop yang sesuai dengan preferensi Anda saat ini."
9. JANGAN memberikan rekomendasi yang dipaksakan
10. JANGAN tambahkan penjelasan pembuka seperti "Berdasarkan preferensi Anda..."
11. JANGAN tambahkan section "LOGIKA REKOMENDASI"
12. ⚠️ PENTING: Jika coffee shop tidak memiliki review yang relevan, JANGAN rekomendasikan coffee shop tersebut, meskipun ratingnya tinggi atau populer
13. ⚠️ PENTING - JUMLAH REKOMENDASI: Jika ada BANYAK coffee shop dengan review yang relevan, output SEMUA yang relevan (maksimal 3 terbaik berdasarkan rating). JANGAN hanya output 1 jika ada lebih banyak yang relevan!
14. ⚠️ CONTOH ANALISIS NLP: 
    - User: "Saya ingin tempat yang buka sampai larut" → Analisis: atribut pilihan = jam operasional (24 jam, buka malam, buka sampai subuh)
    - User: "Tempat yang cocok untuk kerja" → Analisis: atribut pilihan = kebutuhan spesifik (kerja) → butuh wifi, colokan, suasana tenang
    - User: "Coffee shop yang cozy dan ada musholla" → Analisis: atribut pilihan = sifat-sifat (cozy) + fasilitas ibadah (musholla)
    - User: "Saya butuh coffee shop yang ada dinosaurus, musang, dan kijang" → Analisis: TIDAK ADA atribut pilihan yang relevan → Tidak ada rekomendasi

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
- Kata kunci "live music" = "akustik" = "pertunjukan live music" = "live musicnya santai" = "live musik"
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
            user_content = f"""PREFERENSI SAYA (Natural Language):
"{filtered_user_text}"

⚠️ PENTING - FILTER KEYWORDS TIDAK RELEVAN:
- Hanya analisis keywords yang relevan dengan konteks coffee shop (fasilitas, suasana, kebutuhan)
- Abaikan keywords yang tidak relevan seperti hewan, benda, atau aktivitas yang tidak berhubungan dengan coffee shop
- Fokus pada atribut pilihan yang relevan: wifi, cozy, colokan, musholla, live music, parkir, 24 jam, dll

Tugas Anda:
1. Analisis preferensi saya menggunakan Natural Language Processing (NLP)
2. Pahami maksud, konteks, dan kebutuhan yang saya inginkan
3. Identifikasi preferensi inti (fasilitas, suasana, kebutuhan spesifik)
4. Cari coffee shop yang reviewnya BENAR-BENAR relevan dengan preferensi yang saya maksud

🔗 PENTING - SINONIM YANG RELEVAN (untuk membantu pemahaman NLP):
- Kata kunci "24 jam" = "buka sampai larut" = "larut malam" = "buka malam" = "buka sampai subuh" = "buka tengah malam"
- Kata kunci "wifi bagus" = "wifi kencang" = "wifi stabil" = "koneksi internet lancar"
- Kata kunci "musholla" = "tempat sholat" = "tempat sholat tersedia" = "ada musholla"
- Kata kunci "colokan banyak" = "terminal listrik" = "stopkontak tersedia" = "colokan di setiap meja"
- Kata kunci "cozy" = "nyaman" = "hangat" = "tenang" = "santai" = "atmosfernya hangat" = "suasananya cozy"
- Kata kunci "ruang belajar" = "belajar" = "kerja" = "wfc" = "ngerjain tugas" = "cocok buat belajar" = "enak buat kerja"
- Kata kunci "sofa" = "kursi nyaman" = "kursi empuk" = "ruas sofa" = "kursi cukup nyaman"
- Kata kunci "ruangan dingin" = "ac" = "dingin" = "sejuk" = "adem" = "ruangan sejuk"
- Kata kunci "aesthetic" = "estetik" = "kekinian" = "desain" = "dekor" = "instagramable"
- Kata kunci "live music" = "akustik" = "pertunjukan live music" = "live musicnya santai" = "live musik"
- Kata kunci "parkiran luas" = "parkir luas" = "parkir mobil nyaman" = "parkir" = "tempat parkir luas"
- Jika user mencari salah satu variasi di atas, review yang menyebutkan variasi lain TETAP RELEVAN dan BOLEH direkomendasikan

⚠️ PENTING - VALIDASI KETAT UNTUK KEYWORD SPESIFIK:
- Untuk keyword SPESIFIK seperti "musholla", coffee shop HANYA boleh direkomendasikan jika review BENAR-BENAR menyebutkan "musholla", "mushola", "tempat sholat", "ruang sholat", "tempat ibadah", atau "ada musholla"
- JANGAN merekomendasikan coffee shop jika review TIDAK menyebutkan keyword spesifik yang diminta user
- Jika user mencari "musholla" dan review hanya menyebutkan "tempatnya nyaman" atau "wifi bagus" TANPA menyebutkan musholla, JANGAN rekomendasikan coffee shop tersebut
- Review HARUS menyebutkan keyword spesifik atau sinonimnya secara eksplisit

Cari coffee shop yang reviewnya BENAR-BENAR relevan dengan preferensi yang saya maksud (gunakan pemahaman NLP, bukan hanya keyword matching).

🚨 PENTING - JUMLAH REKOMENDASI:
- Jika ada 1 coffee shop yang relevan → output 1
- Jika ada 2 coffee shop yang relevan → output 2 (JANGAN hanya output 1!)
- Jika ada 3+ coffee shop yang relevan → output SEMUA yang relevan (maksimal 3 terbaik berdasarkan rating)
- Jangan hanya output 1 jika ada lebih banyak yang relevan - output SEMUA yang relevan (maksimal 3)

Jika tidak ada review yang relevan, jawab: "Maaf, tidak ada coffee shop yang sesuai dengan preferensi Anda saat ini." Gunakan **bold** untuk highlight kata dalam review yang relevan dengan preferensi saya. Jangan tambahkan penjelasan pembuka atau logika rekomendasi.

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
        
        try:
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
        except Exception as api_error:
            error_str = str(api_error)
            print(f"[LLM] API Error: {error_str}")
            
            # Handle specific error cases
            if "402" in error_str or "quota" in error_str.lower() or "payment" in error_str.lower():
                return jsonify({
                    'status': 'error',
                    'message': 'Kuota token LLM telah habis. Silakan cek akun Hugging Face Anda atau upgrade tier untuk mendapatkan lebih banyak token.',
                    'error_code': 'QUOTA_EXCEEDED',
                    'error_details': 'Hugging Face API quota has been exceeded. Please check your account or upgrade your tier.'
                }), 402
            elif "429" in error_str or "rate limit" in error_str.lower():
                return jsonify({
                    'status': 'error',
                    'message': 'Terlalu banyak request. Silakan tunggu beberapa saat sebelum mencoba lagi.',
                    'error_code': 'RATE_LIMIT',
                    'error_details': 'Rate limit exceeded. Please wait before trying again.'
                }), 429
            elif "401" in error_str or "unauthorized" in error_str.lower():
                return jsonify({
                    'status': 'error',
                    'message': 'Token API Hugging Face tidak valid atau tidak dikonfigurasi dengan benar.',
                    'error_code': 'UNAUTHORIZED',
                    'error_details': 'Invalid or missing Hugging Face API token.'
                }), 401
            else:
                # Generic error
                return jsonify({
                    'status': 'error',
                    'message': f'Terjadi kesalahan saat memanggil LLM API: {error_str}',
                    'error_code': 'API_ERROR',
                    'error_details': error_str
                }), 500
        print(f"[LLM] Generated text length: {len(generated_text)} characters")
        print(f"[LLM] Generated text preview (first 200 chars): {generated_text[:200]}")
        print(f"[LLM] Generated text preview (last 200 chars): {generated_text[-200:]}")
        
        # Validasi dan Post-processing: Pastikan setiap rekomendasi memiliki review
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
        
        # Hitung jumlah coffee shop yang ada di context (dari places_context yang sudah dibuat sebelumnya)
        shop_count_in_context = len(re.findall(r'^\d+\.\s+', places_context, re.MULTILINE)) if 'places_context' in locals() else 0
        
        print(f"[LLM] Validation: Found {num_recommended_shops} recommended shops")
        # Tampilkan summary analisis LLM
        print(f"[LLM] 📊 SUMMARY ANALISIS LLM:")
        print(f"[LLM] 📊   - Coffee shops yang dianalisis oleh LLM: {shop_count_in_context} shops")
        print(f"[LLM] 📊   - Coffee shops yang direkomendasikan: {num_recommended_shops} shops")
        
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
                                        # Filter keywords: hapus stop words seperti "butuh", "perlu", dll
                                        filtered_user_keywords = [kw for kw in user_keywords if kw.lower() not in ['butuh', 'perlu', 'ingin', 'mau', 'cari', 'mencari', 'ada', 'yang', 'untuk', 'dengan', 'dan', 'atau']]
                                        
                                        for kw in filtered_user_keywords:
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
                                                # Cek sinonim untuk keyword spesifik seperti musholla
                                                elif kw_lower in ['musholla', 'mushola', 'tempat sholat', 'ruang sholat', 'tempat ibadah']:
                                                    musholla_synonyms = ['musholla', 'mushola', 'tempat sholat', 'tempat sholat tersedia', 'ada musholla', 'ruang sholat', 'tempat ibadah']
                                                    if any(syn in review_lower for syn in musholla_synonyms):
                                                        is_relevant = True
                                                        print(f"[LLM] ✅ Found relevant review for {shop_name}: keyword '{kw}' found via synonym")
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
                        # Extract review text dari section (bisa ada 1 atau 2 review)
                        review_matches = re.findall(r'Berdasarkan Ulasan Pengunjung:\s*"([^"]+)"', shop_section, re.IGNORECASE)
                        if review_matches:
                            # Gabungkan semua review text untuk validasi
                            all_review_text = ' '.join(review_matches).lower()
                            
                            # Filter keywords: hapus stop words seperti "butuh", "perlu", dll
                            # CATATAN: "ada" TIDAK difilter jika menjadi bagian dari keyword multi-word seperti "ada musholla"
                            filtered_keywords = []
                            for kw in user_keywords_for_filter:
                                kw_lower = kw.lower().strip()
                                # Jika keyword adalah stop word tunggal, skip
                                if kw_lower in ['butuh', 'perlu', 'ingin', 'mau', 'cari', 'mencari', 'yang', 'untuk', 'dengan', 'dan', 'atau'] and len(kw.split()) == 1:
                                    continue
                                # Jika keyword mengandung "ada" sebagai bagian dari frasa (misal: "ada musholla"), pertahankan
                                if len(kw) >= 3:
                                    filtered_keywords.append(kw)
                            
                            # Cek apakah review mengandung minimal salah satu keyword yang relevan
                            for kw in filtered_keywords:
                                kw_lower = kw.lower().strip()
                                if len(kw_lower) >= 3:
                                    # Cek exact match atau substring match
                                    if kw_lower in all_review_text:
                                        is_relevant = True
                                        print(f"[LLM] ✅ Review is relevant for {shop_name}: keyword '{kw}' found")
                                        break
                                    # Cek sinonim untuk keyword spesifik seperti musholla
                                    elif kw_lower in ['musholla', 'mushola', 'tempat sholat', 'ruang sholat', 'tempat ibadah']:
                                        musholla_synonyms = ['musholla', 'mushola', 'tempat sholat', 'tempat sholat tersedia', 'ada musholla', 'ruang sholat', 'tempat ibadah', 'lokasi musholla', 'musholla yang', 'musholla nyaman']
                                        if any(syn in all_review_text for syn in musholla_synonyms):
                                            is_relevant = True
                                            print(f"[LLM] ✅ Review is relevant for {shop_name}: keyword '{kw}' found via synonym")
                                            break
                                    # Cek jika keyword adalah bagian dari frasa yang lebih panjang (misal: "ada musholla" dalam review)
                                    elif 'musholla' in kw_lower or 'mushola' in kw_lower:
                                        # Jika keyword mengandung "musholla", cek apakah review mengandung "musholla" atau variasi
                                        if 'musholla' in all_review_text or 'mushola' in all_review_text or 'tempat sholat' in all_review_text:
                                            is_relevant = True
                                            print(f"[LLM] ✅ Review is relevant for {shop_name}: keyword '{kw}' contains musholla")
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
        
        # Pastikan preferences_ai sudah didefinisikan
        if 'preferences_ai' not in locals():
            # Fallback jika preferences_ai belum didefinisikan
            if 'keywords' in locals() and keywords:
                preferences_ai = f"Preferensi berdasarkan analisis AI: {', '.join(keywords)}"
            else:
                preferences_ai = f"Preferensi berdasarkan analisis AI: {extracted_keywords_display}"
        
        return jsonify({
            'status': 'success',
            'task': task,
            'input': user_text,  # Input asli dari user
            'extracted_keywords': extracted_keywords_display,  # Keywords yang sudah diekstrak oleh LLM
            'preferences_ai': preferences_ai,  # Preferensi berdasarkan analisis AI
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

# Endpoint untuk saran keywords umum berdasarkan review data
@app.route('/api/llm/suggest-keywords', methods=['POST'])
def suggest_keywords():
    """
    Endpoint untuk memberikan saran keywords umum berdasarkan review data
    Memberikan saran keywords yang sebaiknya digunakan user dalam mencari coffee shop
    Tidak memerlukan user input, hanya menganalisis review data
    
    Request JSON: {} (tidak memerlukan input)
    """
    try:
        if hf_client is None:
            return jsonify({
                'status': 'error',
                'message': 'HF_API_TOKEN tidak dikonfigurasi. LLM suggest keywords endpoint nonaktif.'
            }), 503
        
        # Baca reviews.json untuk context saran keywords
        reviews_json_path = os.path.join('frontend-cofind', 'src', 'data', 'reviews.json')
        reviews_data = {}
        reviews_context_for_suggestion = ""
        
        if os.path.exists(reviews_json_path):
            with open(reviews_json_path, 'r', encoding='utf-8') as f:
                reviews_data = json.load(f)
            
            # Ambil semua reviews untuk analisis yang lebih lengkap
            reviews_by_place_id = reviews_data.get('reviews_by_place_id', {})
            all_reviews = []
            for place_id, reviews in reviews_by_place_id.items():
                all_reviews.extend(reviews)
            
            # Buat context untuk saran keywords (ambil lebih banyak review untuk analisis yang lebih baik)
            reviews_context_for_suggestion = "\n".join([
                f"- {review.get('text', '')}" for review in all_reviews[:50]  # Ambil 50 review untuk analisis lebih lengkap
            ])
        
        # Buat prompt untuk saran keywords umum berdasarkan review data
        suggestion_prompt = f"""Anda adalah asisten yang ahli dalam menganalisis review coffee shop untuk memberikan saran keywords yang sebaiknya digunakan user dalam mencari coffee shop.

REVIEW DATA DARI BERBAGAI COFFEE SHOP:
{reviews_context_for_suggestion[:3000]}

Tugas Anda: 
1. Analisis semua review di atas dan identifikasi keywords/atribut yang PALING SERING disebutkan atau PALING PENTING untuk coffee shop
2. Berikan saran keywords yang sebaiknya digunakan user dalam mencari coffee shop berdasarkan review data
3. Fokus pada atribut yang paling relevan dan sering disebutkan: fasilitas (wifi, colokan, musholla, parkir), suasana (cozy, nyaman, tenang), kebutuhan spesifik (belajar, kerja, gaming), dll
4. Output berupa SATU KALIMAT yang berisi saran keywords, format: "Preferensi berdasarkan analisis AI: [keyword1], [keyword2], [keyword3], ..."

ATURAN:
- Berikan 5-10 keywords yang paling relevan dan sering disebutkan di review
- Keywords harus relevan dengan atribut coffee shop: wifi, wifi bagus, wifi kencang, colokan, colokan banyak, cozy, nyaman, tenang, hangat, musholla, parkir, parkir luas, 24 jam, buka malam, aesthetic, live music, ac, dingin, sejuk, sofa, kursi, belajar, kerja, gaming, ngegame, dll
- Output HANYA satu kalimat dengan format: "Preferensi berdasarkan analisis AI: [keywords]"
- Gunakan bahasa Indonesia
- Jangan tambahkan penjelasan lain, hanya output kalimat saran

CONTOH OUTPUT:
"Preferensi berdasarkan analisis AI: wifi kencang, colokan banyak, nyaman, tenang, ruangan dingin, parkir luas, cozy, musholla, belajar, aesthetic"

Sekarang analisis review data dan berikan saran keywords yang sebaiknya digunakan:"""

        # Generate saran keywords menggunakan LLM
        suggested_text = ""
        try:
            if hf_client:
                suggestion_response = hf_client.text_generation(
                    suggestion_prompt,
                    max_new_tokens=150,
                    temperature=0.3,
                    return_full_text=False
                )
                suggested_text = suggestion_response.strip()
                # Bersihkan dari format markdown atau karakter aneh
                suggested_text = suggested_text.replace('**', '').replace('*', '').replace('"', '').replace("'", '').strip()
                print(f"[LLM] Suggested keywords text: {suggested_text}")
            else:
                # Fallback: berikan saran keywords umum
                suggested_text = "Preferensi berdasarkan analisis AI: wifi kencang, colokan banyak, nyaman, tenang, ruangan dingin, parkir luas, cozy, musholla"
        except Exception as e:
            print(f"[LLM] Error suggesting keywords: {e}")
            # Fallback: berikan saran keywords umum
            suggested_text = "Preferensi berdasarkan analisis AI: wifi kencang, colokan banyak, nyaman, tenang, ruangan dingin, parkir luas, cozy, musholla"
        
        # Pastikan format output sesuai
        if not suggested_text.startswith("Preferensi berdasarkan analisis AI:"):
            suggested_text = f"Preferensi berdasarkan analisis AI: {suggested_text}"
        
        return jsonify({
            'status': 'success',
            'preferences_ai': suggested_text,
            'keywords': []
        }), 200
    
    except Exception as e:
        import traceback
        error_message = f"Extract Keywords Error: {str(e)}"
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

# Endpoint untuk summarize review coffee shop berdasarkan place_id
@app.route('/api/llm/summarize-review', methods=['POST'])
def summarize_review():
    """
    Endpoint untuk membuat ringkasan review coffee shop berdasarkan place_id
    
    Request JSON:
    {
        "place_id": "ChIJ...",
        "shop_name": "Nama Coffee Shop" (optional)
    }
    """
    try:
        if hf_client is None:
            return jsonify({
                'status': 'error',
                'message': 'HF_API_TOKEN tidak dikonfigurasi. LLM summarize endpoint nonaktif.'
            }), 503
        
        data = request.get_json()
        if not data or 'place_id' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing required field: place_id'
            }), 400
        
        place_id = data.get('place_id', '').strip()
        shop_name = data.get('shop_name', 'Coffee Shop')
        
        if not place_id:
            return jsonify({
                'status': 'error',
                'message': 'place_id cannot be empty'
            }), 400
        
        # Baca reviews dari reviews.json
        reviews_json_path = os.path.join('frontend-cofind', 'src', 'data', 'reviews.json')
        reviews_data = {}
        
        if os.path.exists(reviews_json_path):
            with open(reviews_json_path, 'r', encoding='utf-8') as f:
                reviews_data = json.load(f)
        else:
            return jsonify({
                'status': 'error',
                'message': 'File reviews.json tidak ditemukan'
            }), 404
        
        reviews_by_place_id = reviews_data.get('reviews_by_place_id', {})
        shop_reviews = reviews_by_place_id.get(place_id, [])
        
        if not shop_reviews or len(shop_reviews) == 0:
            return jsonify({
                'status': 'error',
                'message': 'Tidak ada review untuk coffee shop ini'
            }), 404
        
        # Ambil maksimal 10 review terbaru untuk context
        reviews_for_summary = shop_reviews[:10]
        
        # Format reviews untuk context
        reviews_text = []
        for review in reviews_for_summary:
            review_text = review.get('text', '').strip()
            rating = review.get('rating', 0)
            author = review.get('author_name', 'Anonim')
            if review_text and len(review_text) > 20:
                reviews_text.append(f"- {author} ({rating}⭐): \"{review_text}\"")
        
        if not reviews_text:
            return jsonify({
                'status': 'error',
                'message': 'Tidak ada review yang valid untuk di-summarize'
            }), 404
        
        reviews_context = '\n'.join(reviews_text)
        
        # Build system prompt untuk summarize
        system_prompt = f"""Anda adalah asisten yang ahli dalam meringkas review coffee shop. Tugas Anda adalah membuat ringkasan SINGKAT (maksimal 1 kalimat, 15-30 kata) yang menonjolkan keunikan atau hal otentik dari coffee shop berdasarkan review pengunjung.

ATURAN KETAT:
1. Ringkasan HARUS singkat (maksimal 1 kalimat, 15-30 kata)
2. Fokus pada keunikan, keistimewaan, atau hal otentik yang disebutkan di review
3. Gunakan bahasa Indonesia yang natural dan menarik
4. JANGAN gunakan emoji
5. JANGAN gunakan nama coffee shop di awal kalimat
6. JANGAN gunakan frasa pembuka seperti:
   - "{shop_name} menawarkan..."
   - "Coffee shop ini menawarkan..."
   - "Tempat ini menawarkan..."
   - "Menawarkan suasana..."
   - "Dengan suasana..."
   - "Memiliki..."
   - "Berlokasi di..."
7. LANGSUNG ke poin utama tanpa pembuka apapun
8. Contoh format yang BENAR:
   - "Interior mewah dengan area outdoor yang cozy"
   - "Suasana tenang dengan wifi kencang, cocok untuk ruang belajar"
   - "Desain aesthetic dengan live music dan ruangan ber-AC"
   - "Tempat favorit untuk WFC dengan colokan banyak dan sofa nyaman"
9. Contoh format yang SALAH (JANGAN IKUTI):
   - "{shop_name} menawarkan interior mewah..." ❌
   - "Menawarkan suasana tenang..." ❌
   - "Coffee shop ini memiliki desain aesthetic..." ❌

REVIEW PENGUNJUNG:
{reviews_context}

Buat ringkasan SINGKAT (maksimal 1 kalimat, 15-30 kata) yang menonjolkan keunikan atau hal otentik dari coffee shop berdasarkan review di atas. LANGSUNG mulai dengan poin utama, TANPA nama coffee shop atau frasa pembuka apapun."""
        
        # Build user prompt
        user_prompt = f"Buat ringkasan singkat (maksimal 1 kalimat, 15-30 kata) yang menonjolkan keunikan atau hal otentik dari coffee shop \"{shop_name}\" berdasarkan review pengunjung di atas."
        
        # Call Hugging Face Inference API
        print(f"[SUMMARIZE] Summarizing reviews for place_id: {place_id}")
        print(f"[SUMMARIZE] Total reviews: {len(reviews_for_summary)}")
        
        response = hf_client.chat.completions.create(
            model=HF_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=100,  # Ringkas, cukup untuk 1 kalimat
            temperature=0.3,  # Lebih deterministik untuk konsistensi
            top_p=0.85
        )
        
        generated_text = response.choices[0].message.content.strip()
        
        # Clean up: hapus quotes jika ada, trim whitespace
        generated_text = generated_text.replace('"', '').replace("'", '').strip()
        
        # Post-processing: Hapus nama coffee shop dan frasa pembuka yang tidak diinginkan
        shop_name_lower = shop_name.lower()
        generated_text_lower = generated_text.lower()
        
        # Hapus nama coffee shop di awal jika ada
        if generated_text_lower.startswith(shop_name_lower):
            generated_text = generated_text[len(shop_name):].strip()
            # Hapus koma, titik, atau spasi di awal
            generated_text = generated_text.lstrip('.,;: ')
        
        # Hapus frasa pembuka yang tidak diinginkan
        unwanted_prefixes = [
            f"{shop_name} menawarkan",
            f"{shop_name} memiliki",
            f"{shop_name} dengan",
            "menawarkan suasana",
            "menawarkan",
            "memiliki suasana",
            "memiliki",
            "dengan suasana",
            "coffee shop ini menawarkan",
            "coffee shop ini memiliki",
            "tempat ini menawarkan",
            "tempat ini memiliki",
            "berlokasi di",
        ]
        
        for prefix in unwanted_prefixes:
            if generated_text_lower.startswith(prefix.lower()):
                generated_text = generated_text[len(prefix):].strip()
                # Hapus koma, titik, atau spasi di awal
                generated_text = generated_text.lstrip('.,;: ')
                break
        
        # Capitalize huruf pertama
        if generated_text:
            generated_text = generated_text[0].upper() + generated_text[1:] if len(generated_text) > 1 else generated_text.upper()
        
        # Jika terlalu panjang, potong di titik atau koma terakhir sebelum 30 kata
        words = generated_text.split()
        if len(words) > 30:
            # Ambil 30 kata pertama dan cari titik/koma terakhir
            first_30 = ' '.join(words[:30])
            last_period = first_30.rfind('.')
            last_comma = first_30.rfind(',')
            cut_point = max(last_period, last_comma)
            if cut_point > 0:
                generated_text = first_30[:cut_point + 1]
            else:
                generated_text = first_30
        
        print(f"[SUMMARIZE] Generated summary: {generated_text}")
        
        # Hitung hash dari reviews untuk cache invalidation
        import hashlib
        reviews_hash = hashlib.md5(json.dumps(shop_reviews, sort_keys=True).encode('utf-8')).hexdigest()[:8]
        
        return jsonify({
            'status': 'success',
            'place_id': place_id,
            'shop_name': shop_name,
            'summary': generated_text,
            'reviews_count': len(reviews_for_summary),
            'reviews_hash': reviews_hash,  # Hash untuk cache invalidation
            'timestamp': time.time()
        }), 200
    
    except Exception as e:
        import traceback
        error_message = f"LLM Summarize Error: {str(e)}"
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
