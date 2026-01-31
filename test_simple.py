"""
Simple test untuk Hugging Face API
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv('HF_API_TOKEN')
model = "meta-llama/Llama-3.1-8B-Instruct:cerebras"

print("Testing Hugging Face Router API...")
print(f"Token: {token[:15] if token else 'NOT FOUND'}...")
print(f"Model: {model}")

url = "https://router.huggingface.co/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

payload = {
    "model": model,
    "messages": [
        {"role": "system", "content": "You are helpful assistant."},
        {"role": "user", "content": "Say hello"}
    ],
    "max_tokens": 20
}

try:
    print("\nSending request...")
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    print(f"Status: {response.status_code}")
    
    if response.ok:
        result = response.json()
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        print(f"SUCCESS: {content}")
    else:
        print(f"ERROR: {response.text}")
except Exception as e:
    print(f"EXCEPTION: {e}")
