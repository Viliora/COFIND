"""
Script untuk mengakses database reviews (Supabase/PostgreSQL atau SQLite lokal).
Cara menggunakan:
    python access_reviews_db.py
"""
from db_backend import get_connection, dict_from_row


def _fetchall_dicts(cursor):
    rows = cursor.fetchall()
    return [dict_from_row(cursor, r) for r in rows] if rows else []


def _fetchone_dict(cursor):
    row = cursor.fetchone()
    return dict_from_row(cursor, row) if row else None


def show_all_reviews():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.id, r.user_id, r.shop_id, r.place_id, r.rating, r.review_text,
               r.created_at, r.updated_at, u.username, c.name as shop_name
        FROM reviews r
        LEFT JOIN users u ON r.user_id = u.id
        LEFT JOIN coffee_shops c ON r.shop_id = c.id
        ORDER BY r.created_at DESC
    """)
    reviews = _fetchall_dicts(cursor)
    conn.close()

    print(f"\n{'='*80}")
    print(f"TOTAL REVIEWS: {len(reviews)}")
    print(f"{'='*80}\n")

    for review in reviews:
        print(f"ID: {review['id']}")
        print(f"User: {review.get('username') or 'Unknown'} (ID: {review['user_id']})")
        print(f"Shop: {review.get('shop_name') or 'Unknown'} (Place ID: {review['place_id']})")
        print(f"Rating: {review['rating']}⭐")
        print(f"Review: {review['review_text']}")
        print(f"Created: {review['created_at']}")
        print(f"Updated: {review['updated_at']}")
        print(f"{'-'*80}\n")


def show_reviews_by_place_id(place_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM coffee_shops WHERE place_id = ?", (place_id,))
    shop = _fetchone_dict(cursor)
    shop_name = shop["name"] if shop else "Unknown"

    cursor.execute("""
        SELECT r.id, r.user_id, r.rating, r.review_text,
               r.created_at, r.updated_at, u.username
        FROM reviews r
        LEFT JOIN users u ON r.user_id = u.id
        WHERE r.place_id = ?
        ORDER BY r.created_at DESC
    """, (place_id,))
    reviews = _fetchall_dicts(cursor)
    conn.close()

    print(f"\n{'='*80}")
    print(f"REVIEWS untuk: {shop_name} (Place ID: {place_id})")
    print(f"Total: {len(reviews)} reviews")
    print(f"{'='*80}\n")

    if not reviews:
        print("Belum ada review untuk coffee shop ini.\n")
    else:
        for review in reviews:
            print(f"User: {review.get('username') or 'Unknown'}")
            print(f"Rating: {review['rating']}⭐")
            print(f"Review: {review['review_text']}")
            print(f"Created: {review['created_at']}")
            print(f"{'-'*80}\n")


def show_reviews_by_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT username, email FROM users WHERE id = ?", (user_id,))
    user = _fetchone_dict(cursor)
    username = user["username"] if user else "Unknown"

    cursor.execute("""
        SELECT r.id, r.shop_id, r.place_id, r.rating, r.review_text,
               r.created_at, r.updated_at, c.name as shop_name
        FROM reviews r
        LEFT JOIN coffee_shops c ON r.shop_id = c.id
        WHERE r.user_id = ?
        ORDER BY r.created_at DESC
    """, (user_id,))
    reviews = _fetchall_dicts(cursor)
    conn.close()

    print(f"\n{'='*80}")
    print(f"REVIEWS dari User: {username} (ID: {user_id})")
    print(f"Total: {len(reviews)} reviews")
    print(f"{'='*80}\n")

    if not reviews:
        print("User ini belum membuat review.\n")
    else:
        for review in reviews:
            print(f"Shop: {review.get('shop_name') or 'Unknown'} (Place ID: {review['place_id']})")
            print(f"Rating: {review['rating']}⭐")
            print(f"Review: {review['review_text']}")
            print(f"Created: {review['created_at']}")
            print(f"{'-'*80}\n")


def search_reviews(keyword):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.id, r.user_id, r.place_id, r.rating, r.review_text,
               r.created_at, u.username, c.name as shop_name
        FROM reviews r
        LEFT JOIN users u ON r.user_id = u.id
        LEFT JOIN coffee_shops c ON r.shop_id = c.id
        WHERE r.review_text LIKE ?
        ORDER BY r.created_at DESC
    """, (f"%{keyword}%",))
    reviews = _fetchall_dicts(cursor)
    conn.close()

    print(f"\n{'='*80}")
    print(f"PENCARIAN REVIEWS: '{keyword}'")
    print(f"Total: {len(reviews)} reviews ditemukan")
    print(f"{'='*80}\n")

    if not reviews:
        print(f"Tidak ada review yang mengandung keyword '{keyword}'.\n")
    else:
        for review in reviews:
            print(f"Shop: {review.get('shop_name') or 'Unknown'}")
            print(f"User: {review.get('username') or 'Unknown'}")
            print(f"Rating: {review['rating']}⭐")
            print(f"Review: {review['review_text']}")
            print(f"Created: {review['created_at']}")
            print(f"{'-'*80}\n")


def show_statistics():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM reviews")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT AVG(rating) FROM reviews")
    avg_rating = cursor.fetchone()[0]
    avg_rating = round(float(avg_rating), 2) if avg_rating else 0

    cursor.execute("""
        SELECT rating, COUNT(*) as count
        FROM reviews
        GROUP BY rating
        ORDER BY rating DESC
    """)
    rating_counts = _fetchall_dicts(cursor)

    cursor.execute("""
        SELECT c.name, c.place_id, COUNT(r.id) as review_count, AVG(r.rating) as avg_rating
        FROM coffee_shops c
        LEFT JOIN reviews r ON c.place_id = r.place_id
        GROUP BY c.place_id, c.name
        HAVING COUNT(r.id) > 0
        ORDER BY COUNT(r.id) DESC
        LIMIT 10
    """)
    top_shops = _fetchall_dicts(cursor)
    conn.close()

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
        print(f"  {i}. {shop['name']} - {shop['review_count']} reviews (Avg: {round(float(shop['avg_rating']), 2)}⭐)")

    print()


def main():
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

    if choice == "1":
        show_all_reviews()
    elif choice == "2":
        place_id = input("Masukkan Place ID: ").strip()
        show_reviews_by_place_id(place_id)
    elif choice == "3":
        user_id = input("Masukkan User ID: ").strip()
        try:
            show_reviews_by_user(int(user_id))
        except ValueError:
            print("User ID harus berupa angka!")
    elif choice == "4":
        keyword = input("Masukkan keyword untuk dicari: ").strip()
        search_reviews(keyword)
    elif choice == "5":
        show_statistics()
    elif choice == "6":
        print("Keluar...")
        return
    else:
        print("Pilihan tidak valid!")

    input("\nTekan Enter untuk melanjutkan...")
    main()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nKeluar...")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
