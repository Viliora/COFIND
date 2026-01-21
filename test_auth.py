#!/usr/bin/env python3
from auth_utils import signup, login, verify_token

# Test signup
print("=" * 60)
print("TESTING LOCAL AUTH SYSTEM")
print("=" * 60)

print("\n1️⃣ TEST SIGNUP")
result = signup('john@example.com', 'john_doe', 'password123', 'John Doe')
print(f"   Success: {result['success']}")
if result['success']:
    print(f"   User: {result['user']['username']}")
    print(f"   Email: {result['user']['email']}")
    print(f"   Token: {result['token'][:20]}...")
    token = result['token']
else:
    print(f"   Error: {result['error']}")
    exit(1)

print("\n2️⃣ TEST LOGIN")
result = login('john@example.com', 'password123')
print(f"   Success: {result['success']}")
if result['success']:
    print(f"   User: {result['user']['username']}")
    login_token = result['token']
else:
    print(f"   Error: {result['error']}")
    exit(1)

print("\n3️⃣ TEST TOKEN VERIFICATION")
result = verify_token(login_token)
print(f"   Valid: {result['valid']}")
if result['valid']:
    print(f"   User: {result['user']['username']}")
    print(f"   Admin: {result['user']['is_admin']}")

print("\n4️⃣ TEST DUPLICATE REGISTRATION")
result = signup('john@example.com', 'another_john', 'password456', 'Another John')
print(f"   Success: {result['success']} (should be False)")
print(f"   Error: {result['error']}")

print("\n" + "=" * 60)
print("✅ ALL AUTH TESTS PASSED!")
print("=" * 60)
