"""
Update addresses in coffee_shops table based on place_id
"""
import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'cofind.db')

# Data alamat baru
addresses_data = [
    {
        "place_id": "ChIJDcJgropZHS4RKuh8s52jy9U",
        "address": "Gg. Purnama Agung 3, Parit Tokaya, Kota Pontianak"
    },
    {
        "place_id": "ChIJ9RWUkaZZHS4RYeuZOYAMQ-4",
        "address": "Jl. Putri Candramidi, Sungai Bangkong, Kota Pontianak"
    },
    {
        "place_id": "ChIJ6fOdOEBZHS4RcV3VfZzhYx0",
        "address": "Jl. Ilham No.1, Sungai Bangkong, Kota Pontianak"
    },
    {
        "place_id": "ChIJPa6swGtZHS4RrbIlRvgBgok",
        "address": "Jl. Uray Bawadi No.81, Sungai Bangkong, Kota Pontianak"
    },
    {
        "place_id": "ChIJhx6zl0BZHS4RGNla_oPoIJ0",
        "address": "Jl. Danau Sentarum, Sungai Bangkong, Kota Pontianak"
    },
    {
        "place_id": "ChIJC3_RpddZHS4RMiDp7-6TemY",
        "address": "Jl. Karya Bhakti No.17A, Akcaya, Kota Pontianak"
    },
    {
        "place_id": "ChIJpVctpWBZHS4RdUbSlT-pSl8",
        "address": "Jl. Tj. Raya II, Parit Mayor, Kota Pontianak"
    },
    {
        "place_id": "ChIJBVWfsoFZHS4Rakb44yanMjs",
        "address": "Jl. Dr. Sutomo Gg. Karya 2A No.14, Sungai Bangkong, Kota Pontianak"
    },
    {
        "place_id": "ChIJ71m2hZZZHS4RrOgKJYP_7zw",
        "address": "Jl. Beringin No.27, Darat Sekip, Kota Pontianak"
    },
    {
        "place_id": "ChIJE8-LfABZHS4R_MsSOwiHNL8",
        "address": "Jl. Beringin No.38 A, Darat Sekip, Kota Pontianak"
    },
    {
        "place_id": "ChIJIRuUuwNZHS4RrhnXINPqQQ4",
        "address": "Jl. Prof. DR. Hamka No.1 A, Sungai Jawi, Kota Pontianak"
    },
    {
        "place_id": "ChIJyRLXBlJYHS4RWNj0yvAvSAQ",
        "address": "Jl. H. Abbas 1 No.157, Benua Melayu Darat, Kota Pontianak"
    },
    {
        "place_id": "ChIJ4U6K9hdZHS4RKE7QPIKbn4Y",
        "address": "Jl. Dr. Sutomo Gg. Karya 1 No.4, RT.1/RW.18, KELURAHAN SUNGAI BANGKONG, Kota Pontianak"
    },
    {
        "place_id": "ChIJG-xwV2ZZHS4R0WyGi5bbvoM",
        "address": "Jl. Tanjung Pura Gg. Kelantan No.1-2, tanjung pura, Kota Pontianak"
    },
    {
        "place_id": "ChIJKX36yixZHS4ROQfX-hNWhj0",
        "address": "X9M6+PXW Samping Plan & B, Jl. Gst. Situt Mahmud, Siantan, Siantan Hulu, Kota Pontianak"
    }
]

def update_addresses():
    """Update addresses in database"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        updated_count = 0
        not_found = []
        
        for item in addresses_data:
            place_id = item['place_id']
            new_address = item['address']
            
            # Check if place_id exists
            cursor.execute('SELECT name FROM coffee_shops WHERE place_id = ?', (place_id,))
            result = cursor.fetchone()
            
            if result:
                shop_name = result[0]
                # Update address
                cursor.execute(
                    'UPDATE coffee_shops SET address = ? WHERE place_id = ?',
                    (new_address, place_id)
                )
                print(f'[OK] Updated: {shop_name}')
                print(f'     Place ID: {place_id}')
                print(f'     New Address: {new_address}')
                updated_count += 1
            else:
                print(f'[WARN] Place ID not found: {place_id}')
                not_found.append(place_id)
        
        conn.commit()
        conn.close()
        
        print(f'\n=== Summary ===')
        print(f'Total updated: {updated_count}')
        print(f'Not found: {len(not_found)}')
        
        if not_found:
            print(f'\nPlace IDs not found in database:')
            for pid in not_found:
                print(f'  - {pid}')
        
        return updated_count
        
    except Exception as e:
        print(f'[ERROR] Failed to update addresses: {e}')
        return 0

if __name__ == '__main__':
    print('Updating coffee shop addresses...\n')
    count = update_addresses()
    print(f'\n{count} addresses updated successfully!')
