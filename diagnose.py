import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()

token = os.getenv('HF_API_TOKEN')
model = "meta-llama/Llama-3.1-8B-Instruct:cerebras"

print("=" * 60)
print("DIAGNOSTIC TEST: Hugging Face API Connection")
print("=" * 60)

# 1. Check token
print("\n[1/4] Checking HF_API_TOKEN...")
if not token:
    print("ERROR: HF_API_TOKEN not found in .env!")
    exit(1)
print(f"OK: Token found (starts with: {token[:15]}...)")

# 2. Test API call
print("\n[2/4] Testing API call to Hugging Face Router...")
print(f"Model: {model}")

url = "https://router.huggingface.co/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

payload = {
    "model": model,
    "messages": [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Say hello in 2 words"}
    ],
    "max_tokens": 20
}

try:
    print("Sending request...")
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    
    print(f"\n[3/4] Response Status: {response.status_code}")
    
    if response.ok:
        result = response.json()
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        print(f"\n[4/4] SUCCESS!")
        print(f"Response: {content}")
        print("\n" + "=" * 60)
        print("DIAGNOSIS: API connection works! ✅")
        print("=" * 60)
    else:
        print(f"\n[4/4] FAILED!")
        print(f"Status Code: {response.status_code}")
        try:
            error_detail = response.json()
            print(f"Error Detail: {json.dumps(error_detail, indent=2)}")
        except:
            print(f"Error Text: {response.text}")
        
        print("\n" + "=" * 60)
        print("DIAGNOSIS: API call failed! ❌")
        print("=" * 60)
        
        # Provide solutions
        if response.status_code == 401 or response.status_code == 403:
            print("\nPOSSIBLE CAUSE: Token or model access issue")
            print("\nSOLUTIONS:")
            print("1. Visit: https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct")
            print("   Click 'Agree and access repository'")
            print("2. Generate new token at: https://huggingface.co/settings/tokens")
            print("   Use 'Read' permission")
            print("3. Try alternative model: mistralai/Mistral-7B-Instruct-v0.3")
        elif response.status_code == 502:
            print("\nPOSSIBLE CAUSE: Model not available or router issue")
            print("\nSOLUTIONS:")
            print("1. Model might not be available on router")
            print("2. Try without provider suffix: meta-llama/Llama-3.1-8B-Instruct")
            print("3. Use Groq instead (much faster!)")
            print("4. Use Mistral model (no gating required)")
        
except Exception as e:
    print(f"\n[4/4] EXCEPTION!")
    print(f"Error: {str(e)}")
    print("\n" + "=" * 60)
    print("DIAGNOSIS: Connection error! ❌")
    print("=" * 60)
