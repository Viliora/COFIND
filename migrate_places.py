import json
import os
import sys
sys.path.append('.')

from app import app
from supabase import create_client

def migrate_places_to_supabase():
    """Migrate places data from JSON to Supabase"""

    with app.app_context():
        try:
            # Load environment variables
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_ANON_KEY')

            if not supabase_url or not supabase_key:
                print("❌ SUPABASE_URL and SUPABASE_ANON_KEY environment variables required")
                return False

            supabase = create_client(supabase_url, supabase_key)

            # First, try to create the places table using raw SQL
            print("🔧 Creating places table...")
            
            import requests
            
            # Use REST API to execute SQL
            headers = {
                'Authorization': f'Bearer {supabase_key}',
                'Content-Type': 'application/json',
                'apikey': supabase_key
            }
            
            create_sql = """
            CREATE TABLE IF NOT EXISTS places (
              id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
              place_id TEXT UNIQUE NOT NULL,
              name TEXT NOT NULL,
              address TEXT,
              business_status TEXT DEFAULT 'OPERATIONAL',
              location JSONB,
              rating DECIMAL(3,1),
              user_ratings_total INTEGER DEFAULT 0,
              price_level INTEGER,
              map_embed_url TEXT,
              created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
              updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_places_place_id ON places(place_id);
            CREATE INDEX IF NOT EXISTS idx_places_name ON places(name);
            CREATE INDEX IF NOT EXISTS idx_places_location ON places USING GIN(location);
            
            ALTER TABLE places ENABLE ROW LEVEL SECURITY;
            
            DROP POLICY IF EXISTS "Allow read access for all users" ON places;
            CREATE POLICY "Allow read access for all users" ON places FOR SELECT USING (true);
            """
            
            try:
                response = requests.post(
                    f'{supabase_url}/rest/v1/rpc/exec_sql',
                    headers=headers,
                    json={'sql': create_sql}
                )
                
                if response.status_code == 200:
                    print("✅ Places table created successfully")
                else:
                    print(f"⚠️  Table creation response: {response.status_code} - {response.text}")
                    # Continue anyway, table might already exist
            except Exception as e:
                print(f"⚠️  Table creation error: {str(e)}")
                # Continue anyway

            # Load places data from JSON
            places_file = 'frontend-cofind/src/data/places.json'
            with open(places_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            places = data.get('data', [])
            print(f"📊 Found {len(places)} places to migrate")

            # Check existing places
            try:
                existing_result = supabase.table('places').select('place_id').execute()
                existing_place_ids = set()

                if existing_result.data:
                    existing_place_ids = {p['place_id'] for p in existing_result.data}
                    print(f"📋 Found {len(existing_place_ids)} existing places in Supabase")
            except Exception as e:
                print(f"⚠️  Could not check existing places: {str(e)}")
                existing_place_ids = set()

            # Migrate places
            migrated = 0
            skipped = 0

            for place in places:
                place_id = place.get('place_id')

                if place_id in existing_place_ids:
                    print(f"⏭️  Skipping existing place: {place.get('name', 'Unknown')}")
                    skipped += 1
                    continue

                # Prepare data for Supabase
                place_data = {
                    'place_id': place_id,
                    'name': place.get('name', ''),
                    'address': place.get('address'),
                    'business_status': place.get('business_status', 'OPERATIONAL'),
                    'location': place.get('location'),  # This is already a dict with lat/lng
                    'rating': place.get('rating'),
                    'user_ratings_total': place.get('user_ratings_total', 0),
                    'price_level': place.get('price_level'),
                    'map_embed_url': place.get('map_embed_url')
                }

                try:
                    result = supabase.table('places').insert(place_data).execute()
                    print(f"✅ Migrated: {place_data['name']}")
                    migrated += 1
                except Exception as e:
                    print(f"❌ Failed to migrate {place_data['name']}: {str(e)}")

            print("\n📈 Migration Summary:")
            print(f"   ✅ Migrated: {migrated}")
            print(f"   ⏭️  Skipped: {skipped}")
            print(f"   📊 Total: {len(places)}")

            return True

        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    print("🚀 Starting places migration to Supabase...")
    success = migrate_places_to_supabase()
    if success:
        print("🎉 Migration completed successfully!")
    else:
        print("💥 Migration failed!")
        sys.exit(1)