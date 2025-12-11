#!/usr/bin/env python
"""
Simple test server untuk verify Flask + React integration works
TANPA HF Inference API dependency (menggunakan mock response)
"""
import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import time

app = Flask(__name__)
CORS(app)

print("=" * 60)
print("COFIND Test Server (Mock LLM - No HF API)")
print("=" * 60)

@app.route('/')
def home():
    return jsonify({"status": "ok", "message": "COFIND API Test Server Running"})

@app.route('/api/llm/analyze', methods=['POST'])
def llm_analyze():
    """Mock endpoint untuk testing tanpa HF API"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data provided'}), 400
            
        user_text = data.get('text', '').strip()
        task = data.get('task', 'analyze').lower()
        
        if not user_text:
            return jsonify({'status': 'error', 'message': 'Text cannot be empty'}), 400
        
        # Mock responses berdasarkan task
        mock_responses = {
            'analyze': f"Preferensi user: Kenyamanan, WiFi bagus, Menu kopi specialty. User mencari coffee shop modern untuk produktivitas.",
            'summarize': f"User mencari coffee shop yang nyaman dengan WiFi bagus dan menu kopi specialty untuk bekerja.",
            'recommend': f"Rekomendasi: 1) Ngopi Kopi - Cozy, Fast WiFi, Specialty ⭐⭐⭐⭐⭐\n2) The Brewing Lab - Modern, Premium WiFi ⭐⭐⭐⭐\n3) Bean There - Peaceful, Good WiFi ⭐⭐⭐⭐"
        }
        
        response_text = mock_responses.get(task, mock_responses['analyze'])
        
        return jsonify({
            'status': 'success',
            'task': task,
            'input': user_text,
            'analysis': response_text,
            'timestamp': time.time()
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/llm/chat', methods=['POST'])
def llm_chat():
    """Mock endpoint untuk chat testing"""
    data = request.get_json()
    user_message = data.get('message', '').strip()
    
    # Simpel mock chat
    mock_replies = {
        'default': f"""Terima kasih atas pertanyaan Anda! Berdasarkan preferensi Anda akan mencari coffee shop dengan:
- Suasana yang nyaman dan tenang
- WiFi yang cepat dan stabil
- Pilihan kopi specialty yang berkualitas

Saya merekomendasikan untuk mencoba coffee shop yang fokus pada specialty coffee dengan coworking space yang baik."""
    }
    
    return jsonify({
        'status': 'success',
        'message': user_message,
        'reply': mock_replies['default'],
        'timestamp': time.time()
    })

if __name__ == '__main__':
    print(f"\n✅ Server starting...")
    print(f"📍 Running on http://127.0.0.1:5000")
    print(f"📍 Running on http://0.0.0.0:5000")
    print(f"\n🧪 Test endpoints:")
    print(f"   POST http://127.0.0.1:5000/api/llm/analyze")
    print(f"   POST http://127.0.0.1:5000/api/llm/chat")
    print(f"\n Press CTRL+C to stop\n")
    app.run(host='0.0.0.0', port=5000, debug=False)
