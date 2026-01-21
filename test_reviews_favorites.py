"""
Test Reviews & Favorites API Endpoints
"""

import requests
import json

API_BASE = 'http://localhost:5000'

# Use existing test user
USER_ID = 2
PLACE_ID = 'ChIJPa6swGtZHS4RrbIlRvgBgok'

print("\n" + "="*70)
print("🧪 TESTING REVIEWS & FAVORITES API")
print("="*70)

# Test 1: Create Review
print("\n[1/6] CREATE REVIEW")
print("-" * 70)

review_payload = {
    'user_id': USER_ID,
    'place_id': PLACE_ID,
    'rating': 5,
    'text': 'Amazing coffee and great atmosphere!'
}

review_response = requests.post(
    f'{API_BASE}/api/reviews',
    json=review_payload
)

print(f"Status: {review_response.status_code}")
if review_response.status_code == 201:
    review_data = review_response.json()
    review_id = review_data['review']['id']
    print(f"✅ Review created! ID: {review_id}")
    print(f"   Rating: {review_data['review']['rating']}/5")
else:
    print(f"❌ Failed: {review_response.text}")
    review_id = None

# Test 2: Get Shop Reviews
print("\n[2/6] GET SHOP REVIEWS")
print("-" * 70)

shop_reviews_response = requests.get(
    f'{API_BASE}/api/coffeeshops/{PLACE_ID}/reviews'
)

print(f"Status: {shop_reviews_response.status_code}")
if shop_reviews_response.status_code == 200:
    shop_reviews = shop_reviews_response.json()
    print(f"✅ Got reviews!")
    print(f"   Total reviews: {shop_reviews['review_count']}")
    print(f"   Average rating: {shop_reviews['average_rating']}/5")
else:
    print(f"❌ Failed: {shop_reviews_response.text}")

# Test 3: Get User Reviews
print("\n[3/6] GET USER REVIEWS")
print("-" * 70)

user_reviews_response = requests.get(
    f'{API_BASE}/api/users/{USER_ID}/reviews'
)

print(f"Status: {user_reviews_response.status_code}")
if user_reviews_response.status_code == 200:
    user_reviews = user_reviews_response.json()
    print(f"✅ Got user reviews!")
    print(f"   User has {len(user_reviews['reviews'])} review(s)")
else:
    print(f"❌ Failed: {user_reviews_response.text}")

# Test 4: Update Review
if review_id:
    print("\n[4/6] UPDATE REVIEW")
    print("-" * 70)
    
    update_payload = {
        'user_id': USER_ID,
        'rating': 4,
        'text': 'Updated: Still amazing!'
    }
    
    update_response = requests.put(
        f'{API_BASE}/api/reviews/{review_id}',
        json=update_payload
    )
    
    print(f"Status: {update_response.status_code}")
    if update_response.status_code == 200:
        update_data = update_response.json()
        print(f"✅ Review updated!")
        print(f"   New rating: {update_data['review']['rating']}/5")
        print(f"   New text: {update_data['review']['text']}")
    else:
        print(f"❌ Failed: {update_response.text}")
else:
    print("\n[4/6] UPDATE REVIEW - SKIPPED (no review_id)")

# Test 5: Add Favorite
print("\n[5/6] ADD FAVORITE")
print("-" * 70)

favorite_payload = {
    'user_id': USER_ID,
    'place_id': PLACE_ID
}

favorite_response = requests.post(
    f'{API_BASE}/api/favorites',
    json=favorite_payload
)

print(f"Status: {favorite_response.status_code}")
if favorite_response.status_code == 201:
    favorite_data = favorite_response.json()
    print(f"✅ Added to favorites!")
    print(f"   Message: {favorite_data['message']}")
else:
    print(f"❌ Failed: {favorite_response.text}")

# Test 6: Get User Favorites
print("\n[6/6] GET USER FAVORITES")
print("-" * 70)

favorites_response = requests.get(
    f'{API_BASE}/api/users/{USER_ID}/favorites'
)

print(f"Status: {favorites_response.status_code}")
if favorites_response.status_code == 200:
    favorites_data = favorites_response.json()
    print(f"✅ Got favorites!")
    print(f"   User has {len(favorites_data['favorites'])} favorite(s)")
else:
    print(f"❌ Failed: {favorites_response.text}")

print("\n" + "="*70)
print("✅ REVIEWS & FAVORITES API TEST COMPLETE")
print("="*70)
