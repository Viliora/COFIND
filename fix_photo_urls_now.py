#!/usr/bin/env python3
"""
Quick script to update all coffee shop photo URLs in Supabase database.
Uses Supabase getPublicUrl() generated URLs.

Usage:
    python fix_photo_urls_now.py
"""

from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv('VITE_SUPABASE_URL')
SUPABASE_KEY = os.getenv('VITE_SUPABASE_ANON_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY not found in .env")
    print("Make sure frontend-cofind/.env is configured")
    exit(1)

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def generate_photo_url(place_id):
    """Generate correct photo URL using project-specific domain"""
    if not place_id:
        return None
    
    # Extract project ref from SUPABASE_URL
    # Example: https://cpnzglvpqyugtacodwtr.supabase.co
    if 'supabase.co' not in SUPABASE_URL:
        return None
    
    project_ref = SUPABASE_URL.split('https://')[1].split('.supabase.co')[0]
    filename = f"{place_id}.webp"
    
    return f"https://{project_ref}.supabase.co/storage/v1/object/public/coffee_shops/{filename}"

def main():
    print("🔄 [FIX PHOTO URLS] Starting bulk update...\n")
    
    try:
        # Fetch all places
        response = supabase.table('places').select('place_id, name').execute()
        places = response.data
        
        if not places:
            print("❌ No places found in database")
            return
        
        print(f"📍 Found {len(places)} places to update\n")
        
        updated = 0
        failed = 0
        
        # Update each place
        for place in places:
            try:
                place_id = place.get('place_id')
                name = place.get('name', 'Unknown')
                
                # Generate correct URL
                photo_url = generate_photo_url(place_id)
                
                if not photo_url:
                    print(f"⚠️  Skipped: {name} ({place_id}) - Could not generate URL")
                    failed += 1
                    continue
                
                # Update in database
                update_response = supabase.table('places').update({
                    'photo_url': photo_url
                }).eq('place_id', place_id).execute()
                
                if update_response.data:
                    print(f"✅ Updated: {name} ({place_id})")
                    print(f"   URL: {photo_url}\n")
                    updated += 1
                else:
                    print(f"❌ Failed: {name} ({place_id})")
                    failed += 1
                    
            except Exception as e:
                print(f"❌ Error updating {place_id}: {str(e)}")
                failed += 1
        
        print("\n" + "="*60)
        print(f"✅ Update Complete!")
        print(f"   Updated: {updated}/{len(places)}")
        print(f"   Failed:  {failed}/{len(places)}")
        print("="*60)
        
        if updated > 0:
            print("\n🎉 Success! Photos should now load correctly.")
            print("   📌 Refresh your browser to see the changes")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        exit(1)

if __name__ == '__main__':
    main()
