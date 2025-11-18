from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv
import time  # Tambahkan untuk penundaan
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

# Helper function untuk fetch coffee shops dari Google Places API sebagai context untuk LLM
def _fetch_coffeeshops_context(location_str, limit=5):
    """
    Fetch coffee shops dari Google Places API dan format sebagai context untuk LLM.
    Ini memastikan LLM memberikan rekomendasi berdasarkan data REAL, bukan hallucination.
    """
    try:
        print(f"[PLACES] Fetching coffee shops for location: {location_str}")
        
        # Text Search untuk mendapat coffee shops di lokasi
        base_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            'query': f'coffee shop {location_str}',
            'language': 'id',
            'key': GOOGLE_PLACES_API_KEY
        }
        
        response = requests.get(base_url, params=params)
        data = response.json()
        
        if data.get('status') != 'OK' or not data.get('results'):
            print(f"[PLACES] No results found for location: {location_str}")
            return "Tidak ada data coffee shop yang ditemukan untuk lokasi ini."
        
        # Format coffee shops menjadi context string untuk LLM
        context_lines = [f"Total {len(data['results'])} coffee shop ditemukan di {location_str}:\n"]
        
        for i, shop in enumerate(data['results'][:limit], 1):
            name = shop.get('name', 'Unknown')
            rating = shop.get('rating', 'N/A')
            address = shop.get('formatted_address', 'No address')
            
            context_lines.append(f"{i}. {name}")
            context_lines.append(f"   Rating: {rating}/5.0")
            context_lines.append(f"   Alamat: {address}")
            context_lines.append("")
        
        context = "\n".join(context_lines)
        print(f"[PLACES] Context prepared: {len(context)} characters")
        return context
        
    except Exception as e:
        print(f"[PLACES] Error fetching context: {str(e)}")
        return f"Error mengambil data: {str(e)}"

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
        
        # Step 1: Fetch coffee shops dari Google Places API untuk memberikan context
        print(f"[LLM] Fetching coffee shops from Places API for location: {location}")
        places_context = _fetch_coffeeshops_context(location)
        
        # Step 2: Build system prompt dengan context dari real data
        system_prompt = f"""Anda adalah asisten coffee shop recommendation yang ahli dan berpengetahuan.

DATA COFFEE SHOP YANG TERSEDIA:
{places_context}

Gunakan data coffee shop di atas untuk memberikan rekomendasi dan analisis yang AKURAT dan SPESIFIK.
Jangan buat coffee shop yang tidak ada dalam data.
Berikan alasan detail mengapa coffee shop cocok dengan preferensi user."""

        # Step 3: Build user prompt berdasarkan task
        if task == 'summarize':
            user_content = f"Ringkaskan preferensi coffee shop ini dalam 2-3 kalimat:\n{user_text}"
        elif task == 'recommend':
            user_content = f"""Preferensi coffee shop saya:
{user_text}

Berikan 2-3 rekomendasi coffee shop dari data yang ada dengan alasan spesifik mengapa cocok."""
        else:  # analyze (default)
            user_content = f"""Analisis preferensi coffee shop dari text berikut:
{user_text}

Apa yang paling diinginkan user? Berikan insight mendalam."""
        
        # Step 4: Call Hugging Face Inference API dengan context
        print(f"[LLM] Calling HF API with task: {task}")
        print(f"[LLM] Model: {HF_MODEL}")
        
        response = hf_client.chat.completions.create(
            model=HF_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            max_tokens=256,
            temperature=0.6,
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
