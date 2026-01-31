"""
Test script untuk mengecek koneksi Hugging Face API dan model Llama
"""
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

HF_API_TOKEN = os.getenv('HF_API_TOKEN')
HF_MODEL = os.getenv('HF_MODEL', "meta-llama/Llama-3.1-8B-Instruct")

print("=" * 70)
print("TESTING HUGGING FACE LLM CONFIGURATION")
print("=" * 70)

# 1. Cek apakah token ada
print("\n1. Checking HF_API_TOKEN...")
if HF_API_TOKEN:
    print(f"   ✅ Token found: {HF_API_TOKEN[:10]}...")
else:
    print("   ❌ Token NOT found in .env file!")
    exit(1)

# 2. Cek model name
print(f"\n2. Model to use: {HF_MODEL}")

# 3. Test Router API dengan berbagai provider
print("\n3. Testing Hugging Face Router API...")

API_URL = "https://router.huggingface.co/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {HF_API_TOKEN}",
    "Content-Type": "application/json"
}

messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Say 'Hello' in one word."}
]

# Test dengan beberapa kombinasi model
model_variants = [
    f"{HF_MODEL}:cerebras",  # Provider Cerebras (recommended)
    f"{HF_MODEL}:nvidia-nim",  # Provider Nvidia
    HF_MODEL,  # Tanpa provider
]

success = False
for model_name in model_variants:
    print(f"\n   Testing model: {model_name}")
    
    payload = {
        "model": model_name,
        "messages": messages,
        "max_tokens": 10,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        
        print(f"   Status Code: {response.status_code}")
        
        if response.ok:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0].get('message', {}).get('content', '')
                print(f"   ✅ SUCCESS! Response: {content}")
                success = True
                break
            else:
                print(f"   ⚠️  Response structure unexpected: {result}")
        else:
            # Print error detail
            try:
                error_detail = response.json()
                print(f"   ❌ Error: {error_detail}")
            except:
                print(f"   ❌ Error: {response.text}")
    
    except Exception as e:
        print(f"   ❌ Exception: {str(e)}")

print("\n" + "=" * 70)
if success:
    print("HASIL: ✅ Konfigurasi LLM BERHASIL!")
    print("\nRekomendasi:")
    print("1. Backend dan API sudah berfungsi dengan baik")
    print("2. Pastikan backend (app.py) sedang berjalan")
    print("3. Coba klik tombol AI Summarize di frontend")
else:
    print("HASIL: ❌ Konfigurasi LLM GAGAL!")
    print("\nKemungkinan masalah:")
    print("1. Token belum di-approve untuk model Llama")
    print("   Solusi: Kunjungi https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct")
    print("           dan klik 'Agree and access repository'")
    print("2. Token tidak memiliki permission")
    print("   Solusi: Generate token baru dengan 'Read' permission di")
    print("           https://huggingface.co/settings/tokens")
    print("3. Model tidak tersedia di router")
    print("   Solusi: Coba model lain seperti 'meta-llama/Llama-3.2-3B-Instruct'")
print("=" * 70)
