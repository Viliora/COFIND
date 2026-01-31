"""
Script untuk mengakses database reviews
Cara menggunakan:
    python access_reviews_db.py
"""

import sqlite3
import os
from datetime import datetime

# Path ke database
DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'cofind.db')

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn

def show_all_reviews():
    """Menampilkan semua reviews"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    reviews = cursor.execute('''
        SELECT r.id, r.user_id, r.shop_id, r.place_id, r.rating, r.review_text, 
               r.created_at, r.updated_at, u.username, c.name as shop_name
        FROM reviews r
        LEFT JOIN users u ON r.user_id = u.id
        LEFT JOIN coffee_shops c ON r.shop_id = c.id
        ORDER BY r.created_at DESC
    ''').fetchall()
    
    print(f"\n{'='*80}")
    print(f"TOTAL REVIEWS: {len(reviews)}")
    print(f"{'='*80}\n")
    
    for review in reviews:
        print(f"ID: {review['id']}")
        print(f"User: {review['username'] or 'Unknown'} (ID: {review['user_id']})")
        print(f"Shop: {review['shop_name'] or 'Unknown'} (Place ID: {review['place_id']})")
        print(f"Rating: {review['rating']}⭐")
        print(f"Review: {review['review_text']}")
        print(f"Created: {review['created_at']}")
        print(f"Updated: {review['updated_at']}")
        print(f"{'-'*80}\n")
    
    conn.close()

def show_reviews_by_place_id(place_id):
    """Menampilkan reviews untuk coffee shop tertentu berdasarkan place_id"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get shop info
    shop = cursor.execute(
        'SELECT name FROM coffee_shops WHERE place_id = ?',
        (place_id,)
    ).fetchone()
    
    shop_name = shop['name'] if shop else 'Unknown'
    
    reviews = cursor.execute('''
        SELECT r.id, r.user_id, r.rating, r.review_text, 
               r.created_at, r.updated_at, u.username
        FROM reviews r
        LEFT JOIN users u ON r.user_id = u.id
        WHERE r.place_id = ?
        ORDER BY r.created_at DESC
    ''', (place_id,)).fetchall()
    
    print(f"\n{'='*80}")
    print(f"REVIEWS untuk: {shop_name} (Place ID: {place_id})")
    print(f"Total: {len(reviews)} reviews")
    print(f"{'='*80}\n")
    
    if not reviews:
        print("Belum ada review untuk coffee shop ini.\n")
    else:
        for review in reviews:
            print(f"User: {review['username'] or 'Unknown'}")
            print(f"Rating: {review['rating']}⭐")
            print(f"Review: {review['review_text']}")
            print(f"Created: {review['created_at']}")
            print(f"{'-'*80}\n")
    
    conn.close()

def show_reviews_by_user(user_id):
    """Menampilkan semua reviews dari user tertentu"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user info
    user = cursor.execute(
        'SELECT username, email FROM users WHERE id = ?',
        (user_id,)
    ).fetchone()
    
    username = user['username'] if user else 'Unknown'
    
    reviews = cursor.execute('''
        SELECT r.id, r.shop_id, r.place_id, r.rating, r.review_text, 
               r.created_at, r.updated_at, c.name as shop_name
        FROM reviews r
        LEFT JOIN coffee_shops c ON r.shop_id = c.id
        WHERE r.user_id = ?
        ORDER BY r.created_at DESC
    ''', (user_id,)).fetchall()
    
    print(f"\n{'='*80}")
    print(f"REVIEWS dari User: {username} (ID: {user_id})")
    print(f"Total: {len(reviews)} reviews")
    print(f"{'='*80}\n")
    
    if not reviews:
        print("User ini belum membuat review.\n")
    else:
        for review in reviews:
            print(f"Shop: {review['shop_name'] or 'Unknown'} (Place ID: {review['place_id']})")
            print(f"Rating: {review['rating']}⭐")
            print(f"Review: {review['review_text']}")
            print(f"Created: {review['created_at']}")
            print(f"{'-'*80}\n")
    
    conn.close()

def search_reviews(keyword):
    """Mencari reviews yang mengandung keyword tertentu"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    reviews = cursor.execute('''
        SELECT r.id, r.user_id, r.place_id, r.rating, r.review_text, 
               r.created_at, u.username, c.name as shop_name
        FROM reviews r
        LEFT JOIN users u ON r.user_id = u.id
        LEFT JOIN coffee_shops c ON r.shop_id = c.id
        WHERE r.review_text LIKE ?
        ORDER BY r.created_at DESC
    ''', (f'%{keyword}%',)).fetchall()
    
    print(f"\n{'='*80}")
    print(f"PENCARIAN REVIEWS: '{keyword}'")
    print(f"Total: {len(reviews)} reviews ditemukan")
    print(f"{'='*80}\n")
    
    if not reviews:
        print(f"Tidak ada review yang mengandung keyword '{keyword}'.\n")
    else:
        for review in reviews:
            print(f"Shop: {review['shop_name'] or 'Unknown'}")
            print(f"User: {review['username'] or 'Unknown'}")
            print(f"Rating: {review['rating']}⭐")
            print(f"Review: {review['review_text']}")
            print(f"Created: {review['created_at']}")
            print(f"{'-'*80}\n")
    
    conn.close()

def show_statistics():
    """Menampilkan statistik reviews"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Total reviews
    total = cursor.execute('SELECT COUNT(*) FROM reviews').fetchone()[0]
    
    # Average rating
    avg_rating = cursor.execute('SELECT AVG(rating) FROM reviews').fetchone()[0]
    avg_rating = round(avg_rating, 2) if avg_rating else 0
    
    # Reviews per rating
    rating_counts = cursor.execute('''
        SELECT rating, COUNT(*) as count
        FROM reviews
        GROUP BY rating
        ORDER BY rating DESC
    ''').fetchall()
    
    # Top reviewed shops
    top_shops = cursor.execute('''
        SELECT c.name, c.place_id, COUNT(r.id) as review_count, AVG(r.rating) as avg_rating
        FROM coffee_shops c
        LEFT JOIN reviews r ON c.place_id = r.place_id
        GROUP BY c.place_id
        HAVING review_count > 0
        ORDER BY review_count DESC
        LIMIT 10
    ''').fetchall()
    
    print(f"\n{'='*80}")
    print("STATISTIK REVIEWS")
    print(f"{'='*80}\n")
    print(f"Total Reviews: {total}")
    print(f"Average Rating: {avg_rating}⭐\n")
    
    print("Distribusi Rating:")
    for row in rating_counts:
        print(f"  {row['rating']}⭐: {row['count']} reviews")
    
    print(f"\nTop 10 Coffee Shops dengan Review Terbanyak:")
    for i, shop in enumerate(top_shops, 1):
        print(f"  {i}. {shop['name']} - {shop['review_count']} reviews (Avg: {round(shop['avg_rating'], 2)}⭐)")
    
    print()
    conn.close()

def main():
    """Main menu"""
    print("\n" + "="*80)
    print("DATABASE REVIEWS ACCESS TOOL")
    print("="*80)
    print("\nPilih opsi:")
    print("1. Tampilkan semua reviews")
    print("2. Tampilkan reviews berdasarkan Place ID")
    print("3. Tampilkan reviews berdasarkan User ID")
    print("4. Cari reviews (keyword)")
    print("5. Tampilkan statistik")
    print("6. Keluar")
    
    choice = input("\nMasukkan pilihan (1-6): ").strip()
    
    if choice == '1':
        show_all_reviews()
    elif choice == '2':
        place_id = input("Masukkan Place ID: ").strip()
        show_reviews_by_place_id(place_id)
    elif choice == '3':
        user_id = input("Masukkan User ID: ").strip()
        try:
            show_reviews_by_user(int(user_id))
        except ValueError:
            print("User ID harus berupa angka!")
    elif choice == '4':
        keyword = input("Masukkan keyword untuk dicari: ").strip()
        search_reviews(keyword)
    elif choice == '5':
        show_statistics()
    elif choice == '6':
        print("Keluar...")
        return
    else:
        print("Pilihan tidak valid!")
    
    # Ask to continue
    input("\nTekan Enter untuk melanjutkan...")
    main()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nKeluar...")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
