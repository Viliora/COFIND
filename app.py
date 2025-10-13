# app.py (Kode Perbaikan)

from flask import Flask, jsonify

# 1. DEFINISIKAN APLIKASI FLASK DULU!
app = Flask(__name__) # <--- BARIS INI HARUS DI SINI

# Data Coffee Shop Fiktif (UGC = User-Generated Content)
# app.py (Pastikan array ini diisi, minimal dua objek)
COFFEE_SHOPS = [
    {
        "id": 1,
        "nama": "Kopi Khatulistiwa",
        "alamat": "Jl. Gajah Mada No. 10",
        "rating": 4.5,
        "reviews": ["Kopi robusta di sini kuat banget!", "Tempatnya cozy, cocok buat skripsi."],
        "tags_llm": ["strong_coffee", "cozy_ambience", "study_friendly"]
    },
    {
        "id": 2,
        "nama": "Warung Kopi Aming",
        "alamat": "Jl. Adisucipto No. 5",
        "rating": 4.7,
        "reviews": ["Pelayanannya cepat dan murah.", "Selalu ramai, kopinya legendaris."],
        "tags_llm": ["legendary", "crowded", "fast_service"]
    }
]
# ... (Simpan dan restart server Flask Anda!)

# 2. SEKARANG KITA BISA MENGGUNAKAN @app.route

# Endpoint API Pertama: Mendapatkan Semua Coffee Shops
@app.route('/api/coffeeshops', methods=['GET'])
def get_coffeeshops():
    return jsonify(COFFEE_SHOPS)

# Endpoint API Kedua: Mendapatkan Detail Coffee Shop berdasarkan ID
@app.route('/api/coffeeshops/<int:shop_id>', methods=['GET'])
def get_coffeeshop_detail(shop_id):
    shop = next((s for s in COFFEE_SHOPS if s["id"] == shop_id), None)
    
    if shop:
        return jsonify(shop)
    else:
        return jsonify({"message": f"Coffee Shop dengan ID {shop_id} tidak ditemukan."}), 404


# 3. Jalankan server (Ini harus tetap di bagian paling bawah)
if __name__ == '__main__':
    app.run(debug=True)