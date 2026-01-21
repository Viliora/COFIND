import requests
import json

API_BASE = 'http://localhost:5000'

print("🧪 Testing Signup Endpoint\n")

payload = {
    'email': 'test_user@cofind.app',
    'username': 'test_user_123',
    'password': 'password123',
    'full_name': 'Test User'
}

print(f"📤 POST {API_BASE}/api/auth/signup")
print(f"📋 Payload: {json.dumps(payload, indent=2)}\n")

try:
    response = requests.post(
        f'{API_BASE}/api/auth/signup',
        json=payload,
        headers={'Content-Type': 'application/json'}
    )
    
    print(f"📥 Status: {response.status_code}")
    print(f"📦 Response:\n")
    print(json.dumps(response.json(), indent=2))
    
    if response.status_code == 201:
        print("\n✅ Signup successful!")
        token = response.json().get('token')
        print(f"\n🔑 Token: {token[:30]}...")
        
        # Test verify
        print("\n" + "="*50)
        print("🧪 Testing Verify Endpoint\n")
        
        verify_response = requests.post(
            f'{API_BASE}/api/auth/verify',
            json={'token': token},
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"📥 Status: {verify_response.status_code}")
        print(f"📦 Response:\n")
        print(json.dumps(verify_response.json(), indent=2))
        
        if verify_response.status_code == 200:
            print("\n✅ Token verification successful!")
    else:
        print("\n❌ Signup failed!")
        
except Exception as e:
    print(f"❌ Error: {e}")
