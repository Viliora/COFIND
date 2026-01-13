#!/usr/bin/env python
"""
Script untuk update photo_url di semua coffee shops dengan template URL Supabase
"""
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_ANON_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: SUPABASE_URL atau SUPABASE_SERVICE_ROLE_KEY/SUPABASE_ANON_KEY tidak ditemukan di .env")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Template URL untuk Supabase Storage
PHOTO_URL_TEMPLATE = "https://cpnzglvpqyugtacodwtr.supabase.co/storage/v1/object/public/coffee_shops/{place_id}.webp"

def update_photo_urls():
    """Update semua places dengan photo_url template"""
    try:
        # Get all places
        print("📥 Fetching all places...")
        response = supabase.table('places').select('place_id, name, photo_url').execute()
        places = response.data
        
        if not places:
            print("❌ Tidak ada coffee shops ditemukan")
            return
        
        print(f"📊 Found {len(places)} places")
        
        # Track updates
        updated = 0
        skipped = 0
        
        for place in places:
            place_id = place.get('place_id')
            name = place.get('name', 'Unknown')
            current_photo_url = place.get('photo_url')
            
            # Generate new photo URL
            new_photo_url = PHOTO_URL_TEMPLATE.replace('{place_id}', place_id)
            
            # Check if already updated
            if current_photo_url and (current_photo_url.startswith('https://storage.supabase.co') or 
                                      current_photo_url.startswith('https://cpnzglvpqyugtacodwtr.supabase.co')):
                print(f"⏭️  Skipped: {name} (already has Supabase URL)")
                skipped += 1
                continue
            
            # Update photo_url
            print(f"📤 Updating: {name} ({place_id})")
            update_response = supabase.table('places').update({
                'photo_url': new_photo_url
            }).eq('place_id', place_id).execute()
            
            if update_response.data:
                print(f"   ✅ Updated successfully")
                updated += 1
            else:
                print(f"   ❌ Update failed")
        
        print(f"\n📊 Summary:")
        print(f"   ✅ Updated: {updated}")
        print(f"   ⏭️  Skipped: {skipped}")
        print(f"   📝 Total: {len(places)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    update_photo_urls()
