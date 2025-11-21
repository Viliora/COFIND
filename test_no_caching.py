#!/usr/bin/env python3
"""
Test script to verify API caching has been removed
"""

import requests
import time
import sys

API_BASE = "http://localhost:5000"

def test_api_no_cache():
    """Test that API returns fresh data without caching"""
    print("=" * 60)
    print("Testing API without caching")
    print("=" * 60)
    
    # Test 1: Check /api/test endpoint
    print("\n1. Testing /api/test endpoint...")
    try:
        response = requests.get(f"{API_BASE}/api/test")
        data = response.json()
        
        print(f"   Status: {response.status_code}")
        print(f"   Response: {data}")
        
        # Check that cache-related fields are NOT present
        if 'cache_ttl_minutes' in data or 'cached_locations' in data:
            print("   ❌ FAIL: Cache fields still present in response")
            return False
        else:
            print("   ✅ PASS: No cache fields in response")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False
    
    # Test 2: Check that /api/cache endpoints are removed
    print("\n2. Testing /api/cache/status endpoint (should not exist)...")
    try:
        response = requests.get(f"{API_BASE}/api/cache/status")
        if response.status_code == 404:
            print("   ✅ PASS: Cache status endpoint removed")
        else:
            print(f"   ❌ FAIL: Cache endpoint still exists (status: {response.status_code})")
            return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False
    
    # Test 3: Multiple requests should fetch fresh data
    print("\n3. Testing multiple requests for fresh data...")
    try:
        url = f"{API_BASE}/api/search/coffeeshops?lat=-0.026330&lng=109.342506"
        
        print("   Making first request...")
        response1 = requests.get(url)
        data1 = response1.json()
        time1 = time.time()
        
        time.sleep(1)  # Wait 1 second
        
        print("   Making second request...")
        response2 = requests.get(url)
        data2 = response2.json()
        time2 = time.time()
        
        print(f"   First request: {response1.status_code}, {len(data1.get('data', []))} shops")
        print(f"   Second request: {response2.status_code}, {len(data2.get('data', []))} shops")
        print(f"   Time between requests: {time2 - time1:.2f}s")
        
        # Both should succeed and return data
        if response1.status_code == 200 and response2.status_code == 200:
            print("   ✅ PASS: Both requests returned fresh data")
        else:
            print("   ❌ FAIL: One or both requests failed")
            return False
            
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False
    
    # Test 4: Check debug endpoint
    print("\n4. Testing /api/debug/reviews-context endpoint...")
    try:
        response = requests.get(f"{API_BASE}/api/debug/reviews-context?location=Pontianak&max_shops=3")
        data = response.json()
        
        print(f"   Status: {response.status_code}")
        print(f"   Context length: {data.get('context_length', 0)} characters")
        
        if response.status_code == 200 and data.get('status') == 'success':
            print("   ✅ PASS: Debug endpoint works without caching")
        else:
            print("   ❌ FAIL: Debug endpoint error")
            return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - Caching successfully removed!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    print("Make sure the backend server is running on http://localhost:5000")
    print("Press Enter to continue or Ctrl+C to cancel...")
    try:
        input()
    except KeyboardInterrupt:
        print("\nTest cancelled")
        sys.exit(0)
    
    success = test_api_no_cache()
    sys.exit(0 if success else 1)

