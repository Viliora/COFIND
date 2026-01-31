"""
Script untuk menambahkan kolom latitude dan longitude ke tabel coffee_shops
dan mengupdate data lat/long untuk semua coffee shop
"""

import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'cofind.db')

# Data coffee shops dengan lat/long
COFFEE_SHOPS_DATA = {
    '2818 Coffee Roasters': {'lat': -0.0542551, 'long': 109.3302955},
    '5 CM Coffee and Eatery': {'lat': -0.036481, 'long': 109.3193712},
    'Aming Coffee': {'lat': -0.0311402, 'long': 109.3424925},
    'Aming Coffee Ilham': {'lat': -0.0542376, 'long': 109.3055719},
    'Aming Coffee Podomoro': {'lat': -0.0355222, 'long': 109.3251833},
    'Aming Coffee Siantan': {'lat': -0.0156262, 'long': 109.3624625},
    'CW Coffee Tanjung Raya': {'lat': -0.054291, 'long': 109.3734311},
    'Disela Coffee & Roastery': {'lat': -0.0350962, 'long': 109.3460822},
    'Haruna Cafe': {'lat': -0.0418059, 'long': 109.3128444},
    'Heim Coffee': {'lat': -0.0475305, 'long': 109.3177032},
    'NUTRICULA COFFEE': {'lat': -0.030369, 'long': 109.3344998},
    'Osamu Coffee': {'lat': -0.0459128, 'long': 109.3174164},
    'Rumah Kita Coffee & Eatery': {'lat': -0.0460418, 'long': 109.3277088},
    'Seremoni Coffee': {'lat': -0.0308529, 'long': 109.3338673},
    'Sidedoors Coffee Shop': {'lat': -0.0228826, 'long': 109.3245150},
}

def add_latlong_columns():
    """Tambahkan kolom latitude dan longitude ke tabel coffee_shops"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        # Cek apakah kolom sudah ada
        cursor.execute("PRAGMA table_info(coffee_shops)")
        columns_info = cursor.fetchall()
        columns = [row[1] for row in columns_info]
        
        has_latitude = 'latitude' in columns
        has_longitude = 'longitude' in columns
        
        print(f"[INFO] Columns found: {columns}")
        print(f"[INFO] Has latitude: {has_latitude}")
        print(f"[INFO] Has longitude: {has_longitude}")
        
        # Tambah kolom jika belum ada
        if not has_latitude:
            print("[INFO] Adding latitude column...")
            cursor.execute("ALTER TABLE coffee_shops ADD COLUMN latitude REAL")
            conn.commit()
            print("[INFO] Latitude column added successfully")
        else:
            print("[INFO] Latitude column already exists")
        
        if not has_longitude:
            print("[INFO] Adding longitude column...")
            cursor.execute("ALTER TABLE coffee_shops ADD COLUMN longitude REAL")
            conn.commit()
            print("[INFO] Longitude column added successfully")
        else:
            print("[INFO] Longitude column already exists")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to add columns: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

def update_latlong_data():
    """Update data latitude dan longitude untuk semua coffee shop"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        print("\n[INFO] Updating latitude and longitude for coffee shops...")
        updated_count = 0
        
        for shop_name, coords in COFFEE_SHOPS_DATA.items():
            # Cari coffee shop berdasarkan nama (case-insensitive, partial match)
            cursor.execute("""
                SELECT id, name FROM coffee_shops 
                WHERE name LIKE ? COLLATE NOCASE
            """, (f'%{shop_name}%',))
            
            result = cursor.fetchone()
            if result:
                shop_id, actual_name = result
                cursor.execute("""
                    UPDATE coffee_shops 
                    SET latitude = ?, longitude = ? 
                    WHERE id = ?
                """, (coords['lat'], coords['long'], shop_id))
                print(f"  [OK] Updated: {actual_name} -> Lat: {coords['lat']}, Long: {coords['long']}")
                updated_count += 1
            else:
                print(f"  [NOT FOUND] {shop_name}")
        
        conn.commit()
        print(f"\n[INFO] Updated {updated_count} coffee shops")
        
        # Verifikasi hasil
        print("\n[INFO] Verification - All coffee shops with lat/long:")
        cursor.execute("""
            SELECT name, latitude, longitude 
            FROM coffee_shops 
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            ORDER BY name
        """)
        
        results = cursor.fetchall()
        print(f"\n{'Nama Coffee Shop':<40} {'Latitude':<15} {'Longitude':<15}")
        print("-" * 70)
        for name, lat, long in results:
            print(f"{name:<40} {lat:<15} {long:<15}")
        
        # Cek yang belum ada lat/long
        cursor.execute("""
            SELECT COUNT(*) FROM coffee_shops 
            WHERE latitude IS NULL OR longitude IS NULL
        """)
        missing_count = cursor.fetchone()[0]
        if missing_count > 0:
            print(f"\n[WARNING] {missing_count} coffee shop(s) masih belum ada lat/long")
            cursor.execute("""
                SELECT name FROM coffee_shops 
                WHERE latitude IS NULL OR longitude IS NULL
            """)
            missing = cursor.fetchall()
            for (name,) in missing:
                print(f"  - {name}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to update data: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    print("=" * 70)
    print("Script: Add Latitude & Longitude to Coffee Shops")
    print("=" * 70)
    
    # Step 1: Tambah kolom
    if add_latlong_columns():
        # Step 2: Update data
        update_latlong_data()
        print("\n" + "=" * 70)
        print("[SUCCESS] Script completed!")
        print("=" * 70)
    else:
        print("\n[ERROR] Failed to add columns. Aborting update.")