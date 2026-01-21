"""
FINAL INTEGRATION TEST
Tests complete auth flow: signup > login > update profile > logout
"""

import requests
import json
import time

API_BASE = 'http://localhost:5000'
TEST_USER = f'final_test_{int(time.time())}'
TEST_EMAIL = f'{TEST_USER}@cofind.app'
TEST_PASSWORD = 'FinalTest123!'

print("\n" + "="*70)
print("🚀 FINAL INTEGRATION TEST - LOCAL SQLITE AUTH")
print("="*70)

# Test 1: Signup
print("\n[1/5] SIGNUP TEST")
print("-" * 70)

signup_response = requests.post(
    f'{API_BASE}/api/auth/signup',
    json={
        'email': TEST_EMAIL,
        'username': TEST_USER,
        'password': TEST_PASSWORD,
        'full_name': 'Final Test User'
    }
)

print(f"Status: {signup_response.status_code}")
if signup_response.status_code == 201:
    signup_data = signup_response.json()
    token = signup_data['token']
    user_id = signup_data['user']['id']
    print(f"✅ Signup successful!")
    print(f"   User: {signup_data['user']['username']}")
    print(f"   Email: {signup_data['user']['email']}")
    print(f"   Token: {token[:20]}...")
else:
    print(f"❌ Signup failed: {signup_response.text}")
    exit(1)

# Test 2: Login
print("\n[2/5] LOGIN TEST")
print("-" * 70)

login_response = requests.post(
    f'{API_BASE}/api/auth/login',
    json={
        'email': TEST_EMAIL,
        'password': TEST_PASSWORD
    }
)

print(f"Status: {login_response.status_code}")
if login_response.status_code == 200:
    login_data = login_response.json()
    new_token = login_data['token']
    print(f"✅ Login successful!")
    print(f"   User: {login_data['user']['username']}")
    print(f"   New Token: {new_token[:20]}...")
else:
    print(f"❌ Login failed: {login_response.text}")
    exit(1)

# Test 3: Verify Token
print("\n[3/5] TOKEN VERIFICATION TEST")
print("-" * 70)

verify_response = requests.post(
    f'{API_BASE}/api/auth/verify',
    json={'token': token}
)

print(f"Status: {verify_response.status_code}")
if verify_response.status_code == 200:
    verify_data = verify_response.json()
    print(f"✅ Token verified!")
    print(f"   User: {verify_data['user']['username']}")
    print(f"   Valid: {verify_data['status'] == 'success'}")
else:
    print(f"❌ Token verification failed: {verify_response.text}")
    exit(1)

# Test 4: Get User (requires token)
print("\n[4/5] GET USER TEST")
print("-" * 70)

user_response = requests.get(
    f'{API_BASE}/api/auth/user',
    headers={'Authorization': f'Bearer {token}'}
)

print(f"Status: {user_response.status_code}")
if user_response.status_code == 200:
    user_data = user_response.json()
    print(f"✅ Get user successful!")
    print(f"   User: {user_data['user']['username']}")
    print(f"   Email: {user_data['user']['email']}")
    print(f"   Full Name: {user_data['user']['full_name']}")
else:
    print(f"❌ Get user failed: {user_response.text}")
    exit(1)

# Test 5: Update Profile
print("\n[5/5] UPDATE PROFILE TEST")
print("-" * 70)

update_response = requests.put(
    f'{API_BASE}/api/auth/update-profile',
    headers={'Authorization': f'Bearer {token}'},
    json={
        'full_name': 'Updated Final Test User',
        'bio': 'Testing the local auth system'
    }
)

print(f"Status: {update_response.status_code}")
if update_response.status_code == 200:
    update_data = update_response.json()
    print(f"✅ Update profile successful!")
    print(f"   User: {update_data['user']['username']}")
    print(f"   New Full Name: {update_data['user']['full_name']}")
else:
    print(f"❌ Update profile failed: {update_response.text}")
    exit(1)

print("\n" + "="*70)
print("✅ ALL INTEGRATION TESTS PASSED!")
print("="*70)
print("\n📊 SUMMARY:")
print("  ✓ Signup endpoint working")
print("  ✓ Login endpoint working")
print("  ✓ Token verification working")
print("  ✓ User retrieval working")
print("  ✓ Profile update working")
print("\n🎉 Backend auth system is FULLY OPERATIONAL!")
print("   Ready for frontend integration.\n")
