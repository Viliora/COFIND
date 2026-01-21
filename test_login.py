import requests
import json

API_BASE = 'http://localhost:5000'

print("🧪 Testing Login Endpoint\n")

payload = {
    'email': 'test_user@cofind.app',
    'password': 'password123'
}

print(f"📤 POST {API_BASE}/api/auth/login")
print(f"📋 Payload: {json.dumps(payload, indent=2)}\n")

try:
    response = requests.post(
        f'{API_BASE}/api/auth/login',
        json=payload,
        headers={'Content-Type': 'application/json'}
    )
    
    print(f"📥 Status: {response.status_code}")
    print(f"📦 Response:\n")
    print(json.dumps(response.json(), indent=2))
    
    if response.status_code == 200:
        print("\n✅ Login successful!")
        token = response.json().get('token')
        user = response.json().get('user')
        print(f"\n👤 User: {user['username']} ({user['email']})")
        print(f"🔑 Token: {token[:30]}...")
    else:
        print("\n❌ Login failed!")
        
except Exception as e:
    print(f"❌ Error: {e}")
