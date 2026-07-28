"""
Shop Votes Utilities
Menyimpan & mengagregasi vote user terhadap coffee shop:
- presence: 'here' (sedang di sini) / 'been' (pernah ke sini) / 'want' (mau ke sini)
- rating: 'love' / 'like' / 'ok' / 'dislike' / 'hate'
- best_for: subset dari BEST_FOR_OPTIONS (disimpan sebagai comma-separated text)
- slider scores: pelayanan, kebersihan, kenyamanan, harga (1-5)
"""

from datetime import datetime
from auth_utils import get_db_connection
from db_backend import dict_from_row

PRESENCE_OPTIONS = ('here', 'been', 'want')
RATING_OPTIONS = ('love', 'like', 'ok', 'dislike', 'hate')
BEST_FOR_OPTIONS = ('belajar', 'kerja', 'nge_game', 'meeting', 'family_time', 'instagrammable')
SLIDER_FIELDS = ('pelayanan', 'kebersihan', 'kenyamanan', 'harga')


def _clean_best_for(values):
    if not values:
        return []
    if isinstance(values, str):
        values = [v.strip() for v in values.split(',')]
    cleaned = []
    for v in values:
        v = str(v or '').strip().lower()
        if v in BEST_FOR_OPTIONS and v not in cleaned:
            cleaned.append(v)
    return cleaned


def _clean_slider(value):
    try:
        v = int(value)
    except (TypeError, ValueError):
        return None
    if v < 1 or v > 5:
        return None
    return v


def _star_to_rating_label(star):
    """Konversi rating bintang (1-5) ke label vote (love/like/ok/dislike/hate).
    Konsisten dengan starToRatingMeta() di frontend ReviewCard.jsx: 5=love, 1=hate."""
    try:
        v = max(1, min(5, int(star)))
    except (TypeError, ValueError):
        return None
    index = 5 - v
    if 0 <= index < len(RATING_OPTIONS):
        return RATING_OPTIONS[index]
    return None


def migrate_review_ratings_to_votes():
    """
    Migrasi satu-kali: konversi rating bintang (1-5) pada review yang sudah ada
    menjadi rating vote (love/like/ok/dislike/hate) di tabel shop_votes, untuk
    user yang belum memiliki rating vote pada shop tersebut. Ini memastikan
    rating yang user berikan lewat review lama tetap muncul sebagai pilihan
    mereka di Shop Vote Modal / ShopVotesSummary.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        review_rows = cursor.execute(
            '''
            SELECT user_id, place_id, rating
            FROM reviews
            WHERE rating IS NOT NULL AND user_id IS NOT NULL AND place_id IS NOT NULL
            '''
        ).fetchall()

        now = datetime.utcnow().isoformat()
        updated = 0
        for review_row in review_rows:
            # PENTING: jangan pakai dict_from_row(cursor, ...) di sini karena
            # cursor.description akan berubah setiap kali cursor dipakai untuk
            # query lain di dalam loop (SELECT/UPDATE/INSERT di bawah), sehingga
            # pemetaan kolom jadi salah untuk baris kedua dan seterusnya. Ambil
            # nilai berdasarkan urutan kolom SELECT di atas (user_id, place_id, rating).
            if isinstance(review_row, dict):
                user_id = review_row.get('user_id')
                place_id = (review_row.get('place_id') or '').strip()
                star = review_row.get('rating')
            else:
                user_id = review_row[0]
                place_id = (review_row[1] or '').strip()
                star = review_row[2]
            if not user_id or not place_id or star is None:
                continue
            label = _star_to_rating_label(star)
            if label is None:
                continue

            existing = cursor.execute(
                'SELECT id, rating FROM shop_votes WHERE user_id = ? AND place_id = ?',
                (user_id, place_id),
            ).fetchone()

            if existing:
                existing_rating = existing[1] if not isinstance(existing, dict) else existing.get('rating')
                if existing_rating is None:
                    cursor.execute(
                        'UPDATE shop_votes SET rating = ?, updated_at = ? WHERE id = ?',
                        (label, now, existing[0] if not isinstance(existing, dict) else existing.get('id')),
                    )
                    updated += 1
            else:
                cursor.execute(
                    '''
                    INSERT INTO shop_votes (user_id, place_id, rating, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    (user_id, place_id, label, now, now),
                )
                updated += 1

        conn.commit()
        return updated
    except Exception:
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def get_user_vote(user_id, place_id):
    """Ambil vote user untuk satu coffee shop. Return None jika belum vote."""
    conn = None
    try:
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return None
        trimmed_pid = (place_id or '').strip()
        if not trimmed_pid:
            return None

        conn = get_db_connection()
        cursor = conn.cursor()
        row = cursor.execute(
            '''
            SELECT id, user_id, place_id, presence, rating, best_for,
                   pelayanan, kebersihan, kenyamanan, harga, created_at, updated_at
            FROM shop_votes
            WHERE user_id = ? AND place_id = ?
            ''',
            (user_id, trimmed_pid),
        ).fetchone()
        if not row:
            return None
        rd = dict_from_row(cursor, row)
        rd['best_for'] = _clean_best_for(rd.get('best_for'))
        return rd
    except Exception:
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def upsert_vote(user_id, place_id, presence=None, rating=None, best_for=None,
                 pelayanan=None, kebersihan=None, kenyamanan=None, harga=None):
    """Buat atau perbarui vote user untuk satu coffee shop."""
    conn = None
    try:
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return {'success': False, 'error': 'Invalid user_id'}

        trimmed_pid = (place_id or '').strip()
        if not trimmed_pid:
            return {'success': False, 'error': 'place_id required'}

        if presence is not None and presence not in PRESENCE_OPTIONS:
            return {'success': False, 'error': 'Invalid presence value'}
        if rating is not None and rating not in RATING_OPTIONS:
            return {'success': False, 'error': 'Invalid rating value'}

        best_for_clean = _clean_best_for(best_for)
        best_for_text = ','.join(best_for_clean)

        pelayanan_v = _clean_slider(pelayanan) if pelayanan is not None else None
        kebersihan_v = _clean_slider(kebersihan) if kebersihan is not None else None
        kenyamanan_v = _clean_slider(kenyamanan) if kenyamanan is not None else None
        harga_v = _clean_slider(harga) if harga is not None else None

        conn = get_db_connection()
        cursor = conn.cursor()

        shop = cursor.execute(
            'SELECT place_id FROM coffee_shops WHERE place_id = ? OR TRIM(place_id) = ?',
            (trimmed_pid, trimmed_pid),
        ).fetchone()
        if not shop:
            return {'success': False, 'error': 'Coffee shop not found'}
        canonical_place_id = shop[0]

        existing = cursor.execute(
            'SELECT id FROM shop_votes WHERE user_id = ? AND place_id = ?',
            (user_id, canonical_place_id),
        ).fetchone()

        now = datetime.utcnow().isoformat()

        if existing:
            cursor.execute(
                '''
                UPDATE shop_votes
                SET presence = ?, rating = ?, best_for = ?,
                    pelayanan = ?, kebersihan = ?, kenyamanan = ?, harga = ?,
                    updated_at = ?
                WHERE user_id = ? AND place_id = ?
                ''',
                (presence, rating, best_for_text, pelayanan_v, kebersihan_v,
                 kenyamanan_v, harga_v, now, user_id, canonical_place_id),
            )
        else:
            cursor.execute(
                '''
                INSERT INTO shop_votes
                    (user_id, place_id, presence, rating, best_for,
                     pelayanan, kebersihan, kenyamanan, harga, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (user_id, canonical_place_id, presence, rating, best_for_text,
                 pelayanan_v, kebersihan_v, kenyamanan_v, harga_v, now, now),
            )

        conn.commit()
        return {'success': True}
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return {'success': False, 'error': str(e)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def get_vote_summary(place_id):
    """
    Agregasi vote untuk satu coffee shop:
    - presence_counts: {here, been, want}
    - rating_counts: {love, like, ok, dislike, hate}
    - best_for_counts: {belajar, kerja, nge_game, meeting, family_time, instagrammable}
    - slider_averages: {pelayanan, kebersihan, kenyamanan, harga} (float, None jika tidak ada data)
    - slider_distributions: {field: {'1': n, '2': n, '3': n, '4': n, '5': n}}
    - total_votes
    """
    conn = None
    try:
        trimmed_pid = (place_id or '').strip()
        if not trimmed_pid:
            return {'success': False, 'error': 'place_id required'}

        conn = get_db_connection()
        cursor = conn.cursor()

        rows = cursor.execute(
            '''
            SELECT presence, rating, best_for, pelayanan, kebersihan, kenyamanan, harga
            FROM shop_votes
            WHERE place_id = ? OR TRIM(place_id) = ?
            ''',
            (trimmed_pid, trimmed_pid),
        ).fetchall()

        presence_counts = {k: 0 for k in PRESENCE_OPTIONS}
        rating_counts = {k: 0 for k in RATING_OPTIONS}
        best_for_counts = {k: 0 for k in BEST_FOR_OPTIONS}
        slider_sums = {k: 0 for k in SLIDER_FIELDS}
        slider_counts = {k: 0 for k in SLIDER_FIELDS}
        slider_distributions = {k: {str(v): 0 for v in range(1, 6)} for k in SLIDER_FIELDS}

        total_votes = 0
        for row in rows:
            rd = dict_from_row(cursor, row)
            total_votes += 1

            presence = rd.get('presence')
            if presence in presence_counts:
                presence_counts[presence] += 1

            rating = rd.get('rating')
            if rating in rating_counts:
                rating_counts[rating] += 1

            for tag in _clean_best_for(rd.get('best_for')):
                best_for_counts[tag] += 1

            for field in SLIDER_FIELDS:
                val = rd.get(field)
                if val is not None:
                    slider_sums[field] += val
                    slider_counts[field] += 1
                    val_key = str(val)
                    if val_key in slider_distributions[field]:
                        slider_distributions[field][val_key] += 1

        # Akumulasi rating dari review (bintang 1-5) yang dikonversi ke label
        # love/like/ok/dislike/hate, agar konsisten dengan tampilan pada ReviewCard.
        review_rows = cursor.execute(
            '''
            SELECT rating
            FROM reviews
            WHERE (place_id = ? OR TRIM(place_id) = ?) AND rating IS NOT NULL
            ''',
            (trimmed_pid, trimmed_pid),
        ).fetchall()
        for review_row in review_rows:
            star = review_row[0]
            label = _star_to_rating_label(star)
            if label in rating_counts:
                rating_counts[label] += 1

        slider_averages = {}
        for field in SLIDER_FIELDS:
            if slider_counts[field] > 0:
                slider_averages[field] = round(slider_sums[field] / slider_counts[field], 1)
            else:
                slider_averages[field] = None

        return {
            'success': True,
            'total_votes': total_votes,
            'presence_counts': presence_counts,
            'rating_counts': rating_counts,
            'best_for_counts': best_for_counts,
            'slider_averages': slider_averages,
            'slider_distributions': slider_distributions,
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
