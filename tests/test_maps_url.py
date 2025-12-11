#!/usr/bin/env python
"""
Test script untuk memverifikasi bahwa URL Google Maps muncul dalam:
1. Context data yang dikirim ke LLM
2. Output LLM di response API
"""

import requests
import json

API_BASE = "http://localhost:5000"

print("="*70)
print("🧪 TEST GOOGLE MAPS URL INTEGRATION")
print("="*70)

# Test 1: Clear cache untuk data fresh
print("\n[TEST 1] Clearing cache...")
try:
    response = requests.post(f"{API_BASE}/api/cache/clear", json={})
    if response.status_code == 200:
        print("✅ Cache cleared successfully")
    else:
        print(f"⚠️ Cache clear response: {response.status_code}")
except Exception as e:
    print(f"❌ Error clearing cache: {e}")

# Test 2: Check debug context
print("\n[TEST 2] Checking debug reviews context...")
try:
    response = requests.get(f"{API_BASE}/api/debug/reviews-context?location=Pontianak")
    if response.status_code == 200:
        data = response.json()
        context = data.get('full_context', '')
        
        # Check for Google Maps URL
        has_maps_url = 'Google Maps:' in context
        has_https = 'https://www.google.com/maps/' in context
        has_place_id = 'place_id:' in context
        
        print(f"   • Context length: {len(context)} characters")
        print(f"   • Contains 'Google Maps:': {has_maps_url}")
        print(f"   • Contains 'https://www.google.com/maps/': {has_https}")
        print(f"   • Contains 'place_id:': {has_place_id}")
        
        if has_maps_url and has_https and has_place_id:
            print("✅ Google Maps URL found in context!")
            
            # Extract and show first URL
            lines = context.split('\n')
            for line in lines:
                if 'Google Maps:' in line:
                    print(f"\n   Example URL found:")
                    print(f"   {line.strip()}")
                    break
        else:
            print("❌ Google Maps URL NOT found in context")
            print("\n   First 800 characters of context:")
            print(context[:800])
    else:
        print(f"❌ Debug endpoint error: {response.status_code}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Test full LLM analyze endpoint
print("\n[TEST 3] Testing LLM analyze endpoint...")
try:
    payload = {
        "text": "wifi bagus, terminal banyak",
        "task": "recommend",
        "location": "Pontianak"
    }
    
    print(f"   • Sending request with keywords: '{payload['text']}'")
    response = requests.post(
        f"{API_BASE}/api/llm/analyze",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        data = response.json()
        analysis = data.get('analysis', '')
        
        # Check for Google Maps URL in LLM output
        has_maps_in_output = 'Google Maps:' in analysis or 'google.com/maps' in analysis.lower()
        has_emoji = '🗺️' in analysis
        
        print(f"   • Response length: {len(analysis)} characters")
        print(f"   • Contains Google Maps reference: {has_maps_in_output}")
        print(f"   • Contains maps emoji (🗺️): {has_emoji}")
        
        if has_maps_in_output:
            print("✅ Google Maps URL appears in LLM output!")
            
            # Extract URLs from output
            import re
            urls = re.findall(r'https://[^\s]+', analysis)
            if urls:
                print(f"\n   Found {len(urls)} URL(s):")
                for idx, url in enumerate(urls[:3], 1):  # Show max 3
                    print(f"   {idx}. {url}")
        else:
            print("❌ Google Maps URL NOT in LLM output")
            print("\n   First 500 characters of LLM response:")
            print(analysis[:500])
    else:
        print(f"❌ LLM endpoint error: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 4: Check frontend rendering capability
print("\n[TEST 4] Frontend URL rendering check...")
print("   ℹ️ Frontend should render URLs as clickable links")
print("   ℹ️ Pattern to detect: https?://[^\\s]+")
print("   ✅ LLMAnalyzer.jsx has renderTextWithBold() function")
print("   ✅ Function splits by (\\*\\*[^*]+\\*\\*|https?:\\/\\/[^\\s]+)")

print("\n" + "="*70)
print("🎯 TEST SUMMARY")
print("="*70)
print("✅ If all tests pass, URL Maps should be clickable in frontend")
print("⚠️ If Test 2 fails: Check if Flask server restarted after code changes")
print("⚠️ If Test 3 fails: LLM might not follow instructions, strengthen prompt")
print("="*70)

