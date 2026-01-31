"""
Script Python untuk rename kolom user_ratings_total menjadi total_reviews
dan update data total_reviews
"""

import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'cofind.db')

# Data coffee shops yang akan diupdate
COFFEE_SHOPS_DATA = {
    '2818 Coffee Roasters': 78,
    '5 CM Coffee and Eatery': 744,
    'Aming Coffee Ilham': 1371,
    'Aming Coffee Podomoro': 3024,
    'Aming Coffee Siantan': 522,
    'CW Coffee Tanjung Raya': 379,
    'Disela Coffee & Roastery': 77,
    'Haruna Cafe': 618,
    'Heim Coffee': 129,
    'NUTRICULA COFFEE': 178,
    'Osamu Coffee': 40,
    'Seremoni Coffee': 80,
}

def rename_column_and_update():
    """Rename kolom dan update data"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        # Cek apakah kolom user_ratings_total ada
        cursor.execute("PRAGMA table_info(coffee_shops)")
        columns_info = cursor.fetchall()
        columns = [row[1] for row in columns_info]
        
        has_user_ratings_total = 'user_ratings_total' in columns
        has_total_reviews = 'total_reviews' in columns
        
        print(f"[INFO] Columns found: {columns}")
        print(f"[INFO] Has user_ratings_total: {has_user_ratings_total}")
        print(f"[INFO] Has total_reviews: {has_total_reviews}")
        
        # Jika kolom total_reviews belum ada, buat kolom baru atau rename
        if not has_total_reviews:
            if has_user_ratings_total:
                # Rename kolom user_ratings_total menjadi total_reviews
                print("[INFO] Renaming column user_ratings_total to total_reviews...")
                
                # SQLite tidak support ALTER TABLE RENAME COLUMN, jadi kita perlu:
                # 1. Buat tabel baru dengan struktur yang sesuai
                # 2. Copy data
                # 3. Drop tabel lama
                # 4. Rename tabel baru
                
                conn.execute("BEGIN TRANSACTION")
                
                # Buat tabel baru dengan semua kolom yang ada (kecuali user_ratings_total diganti total_reviews)
                # Build CREATE TABLE statement dinamis berdasarkan kolom yang ada
                create_columns = []
                insert_columns = []
                select_columns = []
                
                for col_info in columns_info:
                    col_name = col_info[1]
                    col_type = col_info[2]
                    col_notnull = col_info[3]
                    col_default = col_info[4]
                    col_pk = col_info[5]
                    
                    if col_name == 'user_ratings_total':
                        # Ganti dengan total_reviews
                        create_columns.append("total_reviews INTEGER DEFAULT 0")
                        insert_columns.append("total_reviews")
                        select_columns.append("COALESCE(user_ratings_total, 0) as total_reviews")
                    elif col_name == 'id' and col_pk:
                        create_columns.append("id INTEGER PRIMARY KEY AUTOINCREMENT")
                        insert_columns.append("id")
                        select_columns.append("id")
                    else:
                        # Kolom biasa
                        notnull_str = " NOT NULL" if col_notnull else ""
                        default_str = f" DEFAULT {col_default}" if col_default else ""
                        create_columns.append(f"{col_name} {col_type}{notnull_str}{default_str}")
                        insert_columns.append(col_name)
                        select_columns.append(col_name)
                
                create_sql = f"CREATE TABLE coffee_shops_new ({', '.join(create_columns)})"
                cursor.execute(create_sql)
                
                # Copy data dari tabel lama
                select_sql = f"""
                    INSERT INTO coffee_shops_new ({', '.join(insert_columns)})
                    SELECT {', '.join(select_columns)}
                    FROM coffee_shops
                """
                
                cursor.execute(select_sql)
                
                # Drop tabel lama
                cursor.execute("DROP TABLE coffee_shops")
                
                # Rename tabel baru
                cursor.execute("ALTER TABLE coffee_shops_new RENAME TO coffee_shops")
                
                conn.commit()
                print("[INFO] Column renamed successfully!")
            else:
                # Tambah kolom baru jika tidak ada keduanya
                print("[INFO] Adding new column total_reviews...")
                cursor.execute("ALTER TABLE coffee_shops ADD COLUMN total_reviews INTEGER DEFAULT 0")
                conn.commit()
        else:
            print("[INFO] Column total_reviews already exists!")
        
        # Update data total_reviews
        print("\n[INFO] Updating total_reviews for coffee shops...")
        updated_count = 0
        
        for shop_name, total_reviews in COFFEE_SHOPS_DATA.items():
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
                    SET total_reviews = ? 
                    WHERE id = ?
                """, (total_reviews, shop_id))
                print(f"  ✓ Updated: {actual_name} -> {total_reviews} reviews")
                updated_count += 1
            else:
                print(f"  ✗ Not found: {shop_name}")
        
        conn.commit()
        print(f"\n[INFO] Updated {updated_count} coffee shops")
        
        # Verifikasi hasil
        print("\n[INFO] Verification - All coffee shops with total_reviews:")
        cursor.execute("""
            SELECT name, total_reviews, rating 
            FROM coffee_shops 
            ORDER BY name
        """)
        
        results = cursor.fetchall()
        print(f"\n{'Nama Coffee Shop':<40} {'Total Reviews':<15} {'Rating':<10}")
        print("-" * 65)
        for name, total_reviews, rating in results:
            print(f"{name:<40} {total_reviews or 0:<15} {rating or 'N/A':<10}")
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == '__main__':
    print("=" * 70)
    print("RENAME COLUMN & UPDATE TOTAL_REVIEWS")
    print("=" * 70)
    print()
    
    response = input("Apakah Anda yakin ingin melanjutkan? (yes/no): ").strip().lower()
    if response == 'yes':
        rename_column_and_update()
    else:
        print("Dibatalkan.")
