"""
Review Management Utilities
CRUD operations for coffee shop reviews
"""

import base64
import re
from datetime import datetime
from auth_utils import get_db_connection
from db_backend import dict_from_row
from review_embedding_store import (
    delete_review_embedding,
    schedule_review_embedding_after_write,
)

# Batas ukuran decoded image per foto (selaras dengan frontend review).
MAX_REVIEW_PHOTO_BYTES = 2 * 1024 * 1024


def _review_image_data_byte_len(image_data):
    """Panjang bytes konten gambar dari data URL base64 atau string mentah."""
    if not image_data:
        return 0
    s = str(image_data).strip()
    m = re.match(r'^data:image/[^;]+;base64,(.+)$', s, re.DOTALL | re.IGNORECASE)
    if not m:
        return len(s.encode('utf-8'))
    try:
        return len(base64.b64decode(m.group(1), validate=False))
    except Exception:
        return None


def _validate_review_photos_size(photos):
    """Return error message string jika ada foto melebihi MAX_REVIEW_PHOTO_BYTES."""
    if not photos:
        return None
    for idx, p in enumerate(photos[:1]):
        if not isinstance(p, dict):
            continue
        data = p.get('image_data')
        if not data:
            continue
        n = _review_image_data_byte_len(data)
        if n is None:
            return f'Format gambar tidak valid (foto #{idx + 1}).'
        if n > MAX_REVIEW_PHOTO_BYTES:
            return f'Ukuran gambar maksimal 2 MB per file (foto #{idx + 1}).'
    return None

def _validate_rating(r, allow_none=False):
    if allow_none and r is None:
        return True
    return r is not None and 1 <= r <= 5

def create_review(user_id, place_id, rating, text='', photos=None):
    """Create a new review with optional photos."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if not _validate_rating(rating):
            return {'success': False, 'error': 'Rating must be between 1 and 5'}
        
        shop = cursor.execute(
            'SELECT id FROM coffee_shops WHERE place_id = ?',
            (place_id,)
        ).fetchone()
        if not shop:
            return {'success': False, 'error': 'Coffee shop not found'}
        shop_id = shop[0]

        photo_err = _validate_review_photos_size(photos)
        if photo_err:
            conn.close()
            return {'success': False, 'error': photo_err}

        cursor.execute('''
            INSERT INTO reviews (
                user_id, shop_id, place_id, rating, review_text,
                created_at, updated_at, review_source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            shop_id,
            place_id,
            rating,
            text or '',
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat(),
            'cofind',
        ))
        review_id = cursor.lastrowid
        
        photos = photos or []
        for i, p in enumerate(photos[:1]):  # maksimal 1 foto per review
            caption = (p.get('caption') or '').strip() if isinstance(p, dict) else ''
            image_data = p.get('image_data') if isinstance(p, dict) else None
            cursor.execute(
                'INSERT INTO review_photos (review_id, caption, image_data) VALUES (?, ?, ?)',
                (review_id, caption or None, image_data)
            )
        
        conn.commit()
        row = cursor.execute(
            'SELECT id, user_id, shop_id, place_id, rating, review_text, created_at, updated_at FROM reviews WHERE id = ?',
            (review_id,)
        ).fetchone()
        photos_out = cursor.execute(
            'SELECT id, caption, image_data FROM review_photos WHERE review_id = ? ORDER BY id',
            (review_id,)
        ).fetchall()
        conn.close()

        schedule_review_embedding_after_write(review_id, text or '')

        return {
            'success': True,
            'review': {
                'id': row[0],
                'user_id': row[1],
                'shop_id': row[2],
                'place_id': row[3],
                'rating': row[4],
                'text': row[5],
                'created_at': row[6],
                'updated_at': row[7],
                'photos': [{'id': p[0], 'caption': p[1], 'image_data': p[2]} for p in photos_out]
            }
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_review(review_id):
    """Get a single review with photos."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        review = cursor.execute(
            'SELECT id, user_id, shop_id, place_id, rating, review_text, created_at, updated_at FROM reviews WHERE id = ?',
            (review_id,)
        ).fetchone()
        if not review:
            conn.close()
            return {'success': False, 'error': 'Review not found'}
        photos = cursor.execute(
            'SELECT id, caption, image_data FROM review_photos WHERE review_id = ? ORDER BY id',
            (review_id,)
        ).fetchall()
        conn.close()
        return {
            'success': True,
            'review': {
                'id': review[0],
                'user_id': review[1],
                'shop_id': review[2],
                'place_id': review[3],
                'rating': review[4],
                'text': review[5],
                'created_at': review[6],
                'updated_at': review[7],
                'photos': [{'id': p[0], 'caption': p[1], 'image_data': p[2]} for p in photos]
            }
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

REVIEW_SOURCE_COFIND = 'cofind'
REVIEW_SOURCE_GOOGLE_PLACES = 'google_places'
# Semua sumber ini ikut pipeline rekomendasi (keyword, semantic, LLM, pros/cons).
PIPELINE_REVIEW_SOURCES = (REVIEW_SOURCE_COFIND, REVIEW_SOURCE_GOOGLE_PLACES)

_REVIEW_SELECT_SQL = '''
    SELECT r.id, r.user_id, r.shop_id, r.place_id, r.rating, r.review_text,
           r.created_at, r.updated_at, r.review_source, r.author_display_name,
           r.relative_time,
           COALESCE(u.username, r.author_display_name) AS display_name
    FROM reviews r
    LEFT JOIN users u ON r.user_id = u.id
'''


def _pipeline_review_source_sql(alias: str = 'r') -> str:
    """Predicate SQL: ulasan yang boleh masuk corpus pipeline rekomendasi."""
    allowed = "', '".join(PIPELINE_REVIEW_SOURCES)
    return (
        f"COALESCE({alias}.review_source, '{REVIEW_SOURCE_COFIND}') "
        f"IN ('{allowed}')"
    )


def _cofind_community_review_source_sql(alias: str = 'r') -> str:
    """Predicate SQL: hanya ulasan komunitas Cofind (stat user, edit/hapus, aside)."""
    return f"COALESCE({alias}.review_source, '{REVIEW_SOURCE_COFIND}') = '{REVIEW_SOURCE_COFIND}'"


def _numeric_rating_to_vote_key(rating):
    """Map rating bintang 1–5 ke kunci badge yang sama dengan vote shop (love/like/…)."""
    try:
        n = int(rating)
    except (TypeError, ValueError):
        return None
    if n >= 5:
        return 'love'
    if n >= 4:
        return 'like'
    if n >= 3:
        return 'ok'
    if n >= 2:
        return 'dislike'
    if n >= 1:
        return 'hate'
    return None


def _author_display_review_counts(cursor, author_names):
    names = [str(n).strip() for n in (author_names or []) if str(n).strip()]
    if not names:
        return {}
    placeholders = ','.join('?' * len(names))
    rows = cursor.execute(
        f'''
        SELECT author_display_name, COUNT(*)
        FROM reviews
        WHERE review_source = 'google_places'
          AND author_display_name IN ({placeholders})
        GROUP BY author_display_name
        ''',
        names,
    ).fetchall()
    return {row[0]: int(row[1]) for row in rows}


def _review_row_to_api_dict(
    review,
    *,
    display_name=None,
    photos=None,
    user_total_reviews=0,
    like_count=0,
    user_has_liked=False,
):
    row = review if isinstance(review, dict) else {}
    if not row and review is not None and not isinstance(review, dict):
        review_id, uid, shop_id, place_id, rating, text, created_at, updated_at, review_source, author_name, relative_time, name = (
            list(review) + [None] * 12
        )[:12]
        row = {
            'id': review_id,
            'user_id': uid,
            'shop_id': shop_id,
            'place_id': place_id,
            'rating': rating,
            'review_text': text,
            'created_at': created_at,
            'updated_at': updated_at,
            'review_source': review_source or 'cofind',
            'author_display_name': author_name,
            'relative_time': relative_time,
            'display_name': name,
        }

    review_id = row.get('id')
    uid = row.get('user_id')
    shop_id = row.get('shop_id')
    place_id = row.get('place_id')
    rating = row.get('rating')
    text = row.get('review_text') or row.get('text')
    created_at = row.get('created_at')
    updated_at = row.get('updated_at')
    review_source = row.get('review_source') or 'cofind'
    relative_time = row.get('relative_time')
    author_display = str(row.get('author_display_name') or '').strip()
    name = str(
        display_name
        or row.get('display_name')
        or row.get('username')
        or row.get('full_name')
        or author_display
        or ''
    ).strip()
    if not name and review_source == 'google_places':
        name = author_display
    name = name or 'Anonim'
    rating_vote_key = _numeric_rating_to_vote_key(rating)
    return {
        'id': review_id,
        'user_id': uid,
        'shop_id': shop_id,
        'place_id': place_id,
        'rating': rating,
        'text': text or '',
        'created_at': created_at,
        'updated_at': updated_at,
        'review_source': review_source,
        'author_display_name': author_display or None,
        'relative_time': relative_time,
        'username': name,
        'full_name': name,
        'profiles': {
            'full_name': name,
            'username': name,
            'avatar_url': None,
        },
        'rating_vote_key': rating_vote_key,
        'photos': photos if photos is not None else [],
        'user_total_reviews': user_total_reviews,
        'like_count': like_count,
        'user_has_liked': user_has_liked,
    }


def _row_dict_from_columns(columns, row):
    cols = columns or []
    if isinstance(row, dict):
        return row
    return {cols[i]: row[i] for i in range(min(len(cols), len(row)))}


def normalize_reviews_for_api(reviews):
    """Pastikan field tampilan (nama penulis) konsisten untuk frontend ReviewCard."""
    normalized = []
    for raw in reviews or []:
        item = dict(raw) if isinstance(raw, dict) else {}
        source = str(item.get('review_source') or '').strip() or 'cofind'
        author = str(item.get('author_display_name') or '').strip()
        uid = item.get('user_id')

        if source == 'google_places' or (uid is None and author):
            source = 'google_places'
            name = author or str(item.get('username') or item.get('full_name') or '').strip() or 'Anonim'
            item['review_source'] = source
            item['author_display_name'] = author or name
            item['username'] = name
            item['full_name'] = name
            item['profiles'] = {
                'full_name': name,
                'username': name,
                'avatar_url': (item.get('profiles') or {}).get('avatar_url'),
            }
        normalized.append(item)
    return normalized


def get_reviews_for_shop(place_id, limit=50, current_user_id=None):
    """Get reviews for a coffee shop. Optionally include like_count and user_has_liked when current_user_id is set.
    limit=None: ambil semua baris (tanpa LIMIT), untuk pipeline rekomendasi / analisis LLM menyeluruh."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        base_sql = _REVIEW_SELECT_SQL + '''
            WHERE r.place_id = ?
            ORDER BY r.created_at DESC
        '''
        reviews = cursor.execute(base_sql, (place_id,)).fetchall()
        review_columns = [d[0] for d in (cursor.description or [])]
        if limit is not None:
            reviews = reviews[: int(limit)]

        user_ids = list({r[1] for r in reviews if r[1]})
        user_total_reviews = {}
        if user_ids:
            placeholders = ','.join('?' * len(user_ids))
            counts = cursor.execute(
                f'''
                SELECT user_id, COUNT(*) FROM reviews
                WHERE user_id IN ({placeholders}) AND COALESCE(review_source, 'cofind') = 'cofind'
                GROUP BY user_id
                ''',
                user_ids
            ).fetchall()
            user_total_reviews = {row[0]: row[1] for row in counts}
        review_ids = [r[0] for r in reviews]
        like_counts = {}
        user_liked = {}
        if review_ids:
            placeholders = ','.join('?' * len(review_ids))
            like_rows = cursor.execute(
                f'SELECT review_id, COUNT(*) FROM review_likes WHERE review_id IN ({placeholders}) GROUP BY review_id',
                review_ids
            ).fetchall()
            like_counts = {row[0]: row[1] for row in like_rows}
            if current_user_id:
                liked_rows = cursor.execute(
                    'SELECT review_id FROM review_likes WHERE user_id = ? AND review_id IN (' + placeholders + ')',
                    [current_user_id] + review_ids
                ).fetchall()
                user_liked = {row[0]: True for row in liked_rows}
        review_list = []
        for review in reviews:
            row_dict = _row_dict_from_columns(review_columns, review)
            review_id = review[0]
            uid = review[1]
            photos = cursor.execute(
                'SELECT id, caption, image_data FROM review_photos WHERE review_id = ? ORDER BY id',
                (review_id,)
            ).fetchall()
            review_list.append(_review_row_to_api_dict(
                row_dict,
                photos=[{'id': p[0], 'caption': p[1], 'image_data': p[2]} for p in photos],
                user_total_reviews=user_total_reviews.get(uid, 0) if uid else 0,
                like_count=like_counts.get(review_id, 0),
                user_has_liked=user_liked.get(review_id, False),
            ))
        google_authors = [
            item.get('author_display_name')
            for item in review_list
            if item.get('review_source') == 'google_places' and item.get('author_display_name')
        ]
        author_counts = _author_display_review_counts(cursor, google_authors)
        for item in review_list:
            if item.get('review_source') == 'google_places' and item.get('author_display_name'):
                item['user_total_reviews'] = author_counts.get(
                    item['author_display_name'], item.get('user_total_reviews') or 0
                )
        conn.close()

        return {'success': True, 'reviews': normalize_reviews_for_api(review_list)}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_reviews_for_recommendation_batch(place_ids):
    """
    Ambil review lean untuk pipeline rekomendasi (tanpa foto/like).
    Termasuk ulasan Cofind dan Google Places (sama seperti corpus sebelum merge ke satu tabel).
    Return: {'success': True, 'by_place': {place_id: [review_dict, ...]}}
    """
    place_ids = [str(pid).strip() for pid in (place_ids or []) if str(pid).strip()]
    if not place_ids:
        return {'success': True, 'by_place': {}}
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(place_ids))
        source_filter = _pipeline_review_source_sql('r')
        rows = cursor.execute(
            f'''
            {_REVIEW_SELECT_SQL}
            WHERE r.place_id IN ({placeholders})
              AND {source_filter}
            ORDER BY r.created_at DESC
            ''',
            place_ids,
        ).fetchall()
        review_columns = [d[0] for d in (cursor.description or [])]
        conn.close()

        by_place = {pid: [] for pid in place_ids}
        for review in rows:
            pid = review[3]
            if pid not in by_place:
                by_place[pid] = []
            row_dict = _row_dict_from_columns(review_columns, review)
            by_place[pid].append(_review_row_to_api_dict(row_dict))
        return {'success': True, 'by_place': by_place}
    except Exception as e:
        return {'success': False, 'error': str(e), 'by_place': {}}


def get_latest_reviews(limit=10):
    """Ambil ulasan terbaru tanpa filter umur, untuk aside publik."""
    try:
        limit = min(max(int(limit), 1), 20)
    except (TypeError, ValueError):
        limit = 10

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cofind_only = _cofind_community_review_source_sql('r')
        rows = cursor.execute(
            f'''
            SELECT r.id, r.place_id, r.created_at,
                   u.username,
                   c.name AS shop_name,
                   c.address
            FROM reviews r
            LEFT JOIN users u ON u.id = r.user_id
            LEFT JOIN coffee_shops c ON c.place_id = r.place_id
            WHERE {cofind_only}
            ORDER BY r.created_at DESC
            LIMIT ?
            ''',
            (limit,),
        ).fetchall()
        items = []
        for row in rows:
            rd = dict_from_row(cursor, row) or {}
            items.append({
                'id': rd.get('id'),
                'place_id': rd.get('place_id'),
                'shop_name': rd.get('shop_name') or 'Coffee shop',
                'address': rd.get('address') or '',
                'username': rd.get('username') or 'Anonim',
                'created_at': rd.get('created_at'),
            })
        return {'success': True, 'items': items}
    except Exception as e:
        return {'success': False, 'error': str(e), 'items': []}
    finally:
        if conn is not None:
            conn.close()


def get_user_review_stats(user_id):
    """Get total review count and average rating for a user."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        row = cursor.execute(
            '''
            SELECT COUNT(*), AVG(rating) FROM reviews
            WHERE user_id = ? AND COALESCE(review_source, 'cofind') = 'cofind'
            ''',
            (user_id,)
        ).fetchone()
        conn.close()
        return {
            'success': True,
            'review_count': row[0] or 0,
            'average_rating': round(row[1], 2) if row[1] is not None else 0
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_user_reviews(user_id, limit=50):
    """Get all reviews by a user with shop name and optional photos."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        reviews = cursor.execute('''
            SELECT r.id, r.user_id, r.shop_id, r.place_id, r.rating, r.review_text,
                   r.created_at, r.updated_at, c.name AS shop_name
            FROM reviews r
            LEFT JOIN coffee_shops c ON r.place_id = c.place_id
            WHERE r.user_id = ? AND COALESCE(r.review_source, 'cofind') = 'cofind'
            ORDER BY r.created_at DESC
            LIMIT ?
        ''', (user_id, limit)).fetchall()
        review_list = []
        for review in reviews:
            review_id = review[0]
            photos = cursor.execute(
                'SELECT id, caption, image_data FROM review_photos WHERE review_id = ? ORDER BY id',
                (review_id,)
            ).fetchall()
            like_count = cursor.execute(
                'SELECT COUNT(*) FROM review_likes WHERE review_id = ?', (review_id,)
            ).fetchone()[0]
            review_list.append({
                'id': review_id,
                'user_id': review[1],
                'shop_id': review[2],
                'place_id': review[3],
                'rating': review[4],
                'text': review[5],
                'created_at': review[6],
                'updated_at': review[7],
                'shop_name': review[8],
                'photos': [{'id': p[0], 'caption': p[1], 'image_data': p[2]} for p in photos],
                'like_count': like_count
            })
        conn.close()
        return {'success': True, 'reviews': review_list}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def update_review(review_id, user_id, rating=None, text=None, photos=None):
    """Update a review (rating, text, photos)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        review = cursor.execute(
            'SELECT id, user_id, shop_id, place_id, rating, review_text, review_source FROM reviews WHERE id = ?',
            (review_id,)
        ).fetchone()
        if not review:
            conn.close()
            return {'success': False, 'error': 'Review not found'}
        if (review[6] if len(review) > 6 else 'cofind') != 'cofind' or review[1] is None:
            conn.close()
            return {'success': False, 'error': 'Review cannot be edited'}
        if review[1] != user_id:
            conn.close()
            return {'success': False, 'error': 'Unauthorized'}
        new_rating = rating if rating is not None else review[4]
        new_text = text if text is not None else review[5]
        if rating is not None and not _validate_rating(rating):
            conn.close()
            return {'success': False, 'error': 'Rating must be between 1 and 5'}
        if photos is not None:
            photo_err = _validate_review_photos_size(photos)
            if photo_err:
                conn.close()
                return {'success': False, 'error': photo_err}
        cursor.execute('''
            UPDATE reviews
            SET rating = ?, review_text = ?, updated_at = ?
            WHERE id = ?
        ''', (
            new_rating,
            new_text,
            datetime.utcnow().isoformat(),
            review_id,
        ))
        if photos is not None:
            cursor.execute('DELETE FROM review_photos WHERE review_id = ?', (review_id,))
            for p in (photos or [])[:1]:
                caption = (p.get('caption') or '').strip() if isinstance(p, dict) else ''
                image_data = p.get('image_data') if isinstance(p, dict) else None
                if image_data:
                    cursor.execute(
                        'INSERT INTO review_photos (review_id, caption, image_data) VALUES (?, ?, ?)',
                        (review_id, caption or None, image_data)
                    )
        conn.commit()
        conn.close()

        schedule_review_embedding_after_write(review_id, new_text or '')

        result = get_review(review_id)
        return result
    except Exception as e:
        return {'success': False, 'error': str(e)}

def delete_review(review_id, user_id):
    """Delete a review"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check review exists and user owns it
        review = cursor.execute(
            'SELECT id, user_id, review_source FROM reviews WHERE id = ?',
            (review_id,)
        ).fetchone()
        
        if not review:
            return {'success': False, 'error': 'Review not found'}
        
        if (review[2] if len(review) > 2 else 'cofind') != 'cofind' or review[1] is None:
            return {'success': False, 'error': 'Review cannot be deleted'}
        if review[1] != user_id:
            return {'success': False, 'error': 'Unauthorized'}
        
        delete_review_embedding(review_id)
        # Delete review
        cursor.execute('DELETE FROM reviews WHERE id = ?', (review_id,))
        conn.commit()
        conn.close()
        
        return {'success': True, 'message': 'Review deleted'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_average_rating(place_id):
    """Agregat rating untuk halaman shop (Cofind + Google Places, selaras dengan pipeline)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        source_filter = _pipeline_review_source_sql('reviews')
        result = cursor.execute(
            f'SELECT AVG(rating), COUNT(*) FROM reviews WHERE place_id = ? AND {source_filter}',
            (place_id,),
        ).fetchone()
        
        conn.close()
        
        avg_rating = result[0] or 0
        review_count = result[1] or 0
        
        return {
            'success': True,
            'average_rating': round(avg_rating, 2),
            'review_count': review_count
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def toggle_review_like(user_id, review_id):
    """Toggle like on a review. Returns { success, liked, like_count }."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM reviews WHERE id = ?', (review_id,))
        if not cursor.fetchone():
            conn.close()
            return {'success': False, 'error': 'Review not found'}
        cursor.execute('SELECT 1 FROM review_likes WHERE user_id = ? AND review_id = ?', (user_id, review_id))
        exists = cursor.fetchone()
        if exists:
            cursor.execute('DELETE FROM review_likes WHERE user_id = ? AND review_id = ?', (user_id, review_id))
            liked = False
        else:
            cursor.execute('INSERT INTO review_likes (user_id, review_id) VALUES (?, ?)', (user_id, review_id))
            liked = True
        count = cursor.execute('SELECT COUNT(*) FROM review_likes WHERE review_id = ?', (review_id,)).fetchone()[0]
        conn.commit()
        conn.close()
        return {'success': True, 'liked': liked, 'like_count': count}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def create_review_report(review_id, reported_by_user_id, report_reason=None, report_text=None):
    """
    Simpan laporan review ke tabel review_reports.
    Returns { success, report_id } atau { success: False, error, code }.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id, user_id FROM reviews WHERE id = ?', (review_id,))
        review_row = cursor.fetchone()
        if not review_row:
            conn.close()
            return {'success': False, 'error': 'Review tidak ditemukan', 'code': 'NOT_FOUND'}

        owner_id = review_row[1]
        if owner_id is not None and int(owner_id) == int(reported_by_user_id):
            conn.close()
            return {'success': False, 'error': 'Anda tidak dapat melaporkan ulasan sendiri', 'code': 'OWN_REVIEW'}

        cursor.execute(
            '''
            SELECT id FROM review_reports
            WHERE review_id = ? AND reported_by_user_id = ?
              AND LOWER(COALESCE(status, 'pending')) IN ('pending', 'reviewed')
            LIMIT 1
            ''',
            (review_id, reported_by_user_id),
        )
        if cursor.fetchone():
            conn.close()
            return {
                'success': False,
                'error': 'Anda sudah melaporkan ulasan ini sebelumnya',
                'code': 'ALREADY_REPORTED',
            }

        reason = (report_reason or '').strip() or 'Ulasan tidak pantas'
        detail = (report_text or '').strip() or None

        cursor.execute(
            '''
            INSERT INTO review_reports (
                review_id, reported_by_user_id, report_reason, report_text, status, created_at
            ) VALUES (?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
            ''',
            (review_id, reported_by_user_id, reason, detail),
        )
        report_id = cursor.lastrowid
        if report_id is None:
            row = cursor.execute(
                '''
                SELECT id FROM review_reports
                WHERE review_id = ? AND reported_by_user_id = ?
                ORDER BY id DESC LIMIT 1
                ''',
                (review_id, reported_by_user_id),
            ).fetchone()
            report_id = row[0] if row else None

        conn.commit()
        conn.close()
        return {'success': True, 'report_id': report_id}
    except Exception as e:
        return {'success': False, 'error': str(e), 'code': 'ERROR'}
