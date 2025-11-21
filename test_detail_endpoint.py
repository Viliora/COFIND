import requests
import json

API_BASE = 'http://localhost:5000'

def test_search_endpoint():
    """Test search endpoint dan ambil place_id pertama"""
    print("=" * 60)
    print("1. Testing Search Endpoint")
    print("=" * 60)
    
    url = f"{API_BASE}/api/search/coffeeshops?lat=-0.026330&lng=109.342506"
    print(f"URL: {url}\n")
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if data.get('status') == 'success' and data.get('data'):
            print(f"✅ Success! Found {len(data['data'])} coffee shops\n")
            
            # Ambil 3 coffee shop pertama
            first_shops = data['data'][:3]
            
            print("First 3 Coffee Shops:")
            print("-" * 60)
            for i, shop in enumerate(first_shops, 1):
                print(f"{i}. Name: {shop.get('name')}")
                print(f"   Place ID: {shop.get('place_id')}")
                print(f"   Rating: {shop.get('rating')} ({shop.get('user_ratings_total')} reviews)")
                print(f"   Photos: {len(shop.get('photos', []))} available")
                print()
            
            return first_shops[0].get('place_id')
        else:
            print(f"❌ Error: {data}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_detail_endpoint(place_id):
    """Test detail endpoint dengan place_id"""
    print("=" * 60)
    print("2. Testing Detail Endpoint")
    print("=" * 60)
    
    url = f"{API_BASE}/api/coffeeshops/detail/{place_id}"
    print(f"URL: {url}\n")
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if data.get('status') == 'success' and data.get('data'):
            detail = data['data']
            print(f"✅ Success! Got detail for: {detail.get('name')}\n")
            
            print("Coffee Shop Details:")
            print("-" * 60)
            print(f"Name: {detail.get('name')}")
            print(f"Address: {detail.get('formatted_address')}")
            print(f"Phone: {detail.get('formatted_phone_number', 'N/A')}")
            print(f"Website: {detail.get('website', 'N/A')}")
            print(f"Rating: {detail.get('rating')} ({detail.get('user_ratings_total')} reviews)")
            print(f"Price Level: {detail.get('price_level', 'N/A')}")
            
            # Opening hours
            if detail.get('opening_hours'):
                print(f"\nOpening Hours:")
                weekday_text = detail['opening_hours'].get('weekday_text', [])
                for day in weekday_text[:3]:  # Show first 3 days
                    print(f"  - {day}")
                if len(weekday_text) > 3:
                    print(f"  ... and {len(weekday_text) - 3} more days")
            
            # Reviews
            reviews = detail.get('reviews', [])
            if reviews:
                print(f"\nRecent Reviews ({len(reviews)}):")
                for i, review in enumerate(reviews[:2], 1):  # Show 2 reviews
                    print(f"  {i}. {review.get('author_name')} - ⭐ {review.get('rating')}")
                    text = review.get('text', '')
                    print(f"     \"{text[:80]}...\"" if len(text) > 80 else f"     \"{text}\"")
                    print()
            
            # Photos
            photos = detail.get('photos', [])
            print(f"\nPhotos: {len(photos)} available")
            
            return True
        else:
            print(f"❌ Error: {data}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("\n🔍 COFIND API - Detail Endpoint Test\n")
    
    # Test 1: Search untuk dapatkan place_id
    place_id = test_search_endpoint()
    
    if place_id:
        print(f"\n➡️  Will test detail endpoint with place_id: {place_id}\n")
        input("Press Enter to continue...")
        
        # Test 2: Detail endpoint
        test_detail_endpoint(place_id)
    else:
        print("\n❌ Cannot test detail endpoint without place_id")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)

if __name__ == '__main__':
    main()

