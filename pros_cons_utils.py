"""
Pros & Cons ("What People Say") Utilities

Arsitektur:
- Konten AI (poin pro/con) dan sistem voting dipisah total. AI hanya
  bertugas mendeteksi topik umum dari review (mis. "wifi lambat"). Vote
  (upvote/downvote) hanya menambah angka di tabel terpisah, TIDAK pernah
  mengubah teks poin AI.
- Pembaruan AI TIDAK dipanggil setiap request. Dipicu (batch/lazy job)
  hanya jika:
    a) Sudah >= PROS_CONS_REFRESH_INTERVAL_DAYS hari sejak pembaruan
       terakhir (default 7 hari), ATAU
    b) Sudah ada >= PROS_CONS_MIN_NEW_REVIEWS review baru sejak
       pembaruan terakhir (default 5).
  Di luar kondisi itu, endpoint GET hanya membaca hasil ekstraksi yang
  sudah tersimpan di database (cepat, konsisten).
- Deduplikasi topik: LLM diminta langsung mengelompokkan review yang
  mirip menjadi satu poin induk (semantic clustering) saat ekstraksi.
- Saat regenerasi, poin lama yang teksnya cocok (dinormalisasi) dengan
  poin baru akan MEMPERTAHANKAN vote count-nya (tidak reset ke 0).
"""

import json
import re
from datetime import datetime, timedelta

from auth_utils import get_db_connection
from db_backend import dict_from_row
from llm_backend import llm_is_available, llm_chat_completions_create, HF_MODEL

PROS_CONS_REFRESH_INTERVAL_DAYS = 7
PROS_CONS_MIN_NEW_REVIEWS = 5
PROS_CONS_MAX_POINTS_PER_TYPE = 10


def _normalize_text(text):
    return re.sub(r'\s+', ' ', str(text or '').strip().lower())


def _get_review_stats(cursor, place_id):
    """Ambil semua teks review (yang cukup panjang) + total review untuk satu coffee shop."""
    rows = cursor.execute(
        '''
        SELECT review_text FROM reviews
        WHERE place_id = ? AND review_text IS NOT NULL AND TRIM(review_text) != ''
        ORDER BY created_at DESC
        ''',
        (place_id,),
    ).fetchall()
    texts = [str(r[0]).strip() for r in rows if str(r[0] or '').strip()]
    total_count = cursor.execute(
        'SELECT COUNT(*) FROM reviews WHERE place_id = ?', (place_id,),
    ).fetchone()[0]
    return texts, total_count


def _extract_json_block(raw):
    raw = (raw or '').strip()
    start = raw.find('{')
    end = raw.rfind('}')
    if start == -1 or end == -1 or end < start:
        raise ValueError('No JSON object found in LLM output')
    return json.loads(raw[start:end + 1])


def _generate_pros_cons_via_llm(shop_name, review_texts):
    """Panggil LLM untuk ekstraksi + deduplikasi topik pro/con dari review. Return (pros, cons) list of str."""
    if not llm_is_available() or not review_texts:
        return [], []

    corpus = "\n".join(f"- {t[:300]}" for t in review_texts[:60])
    prompt = f'''Analisis ulasan pengunjung coffee shop "{shop_name}" berikut ini.

Tugas:
1. Deteksi topik/kalimat umum yang sering disebut pengunjung (mis. "wifi terlalu lambat", "suasana nyaman untuk WFC").
2. Kelompokkan ulasan dengan topik yang mirip menjadi SATU poin induk saja (jangan duplikat topik).
3. Pisahkan menjadi dua daftar: "pros" (hal positif) dan "cons" (hal negatif/kekurangan).
4. Setiap poin harus singkat (maks 8 kata), berbasis Bahasa Indonesia, dan benar-benar didukung oleh isi ulasan.
5. Maksimal {PROS_CONS_MAX_POINTS_PER_TYPE} poin per daftar, urutkan dari yang paling sering disebut.

Ulasan pengunjung:
{corpus}

Jawab HANYA JSON valid dengan format:
{{"pros": ["poin singkat 1", "poin singkat 2"], "cons": ["poin singkat 1", "poin singkat 2"]}}'''

    try:
        raw = llm_chat_completions_create(
            model=HF_MODEL,
            messages=[
                {
                    'role': 'system',
                    'content': 'Anda adalah pengekstrak topik ulasan. Jawab hanya JSON valid, tanpa markdown/teks lain.',
                },
                {'role': 'user', 'content': prompt},
            ],
            max_tokens=500,
            temperature=0.2,
        )
        parsed = _extract_json_block(raw)
        pros = [str(p).strip() for p in (parsed.get('pros') or []) if str(p).strip()]
        cons = [str(c).strip() for c in (parsed.get('cons') or []) if str(c).strip()]
        return pros[:PROS_CONS_MAX_POINTS_PER_TYPE], cons[:PROS_CONS_MAX_POINTS_PER_TYPE]
    except Exception as e:
        print(f"[PROS_CONS] LLM extraction failed: {e}")
        return [], []


def _get_meta(cursor, place_id):
    row = cursor.execute(
        'SELECT place_id, last_generated_at, review_count_at_last_generation FROM shop_pros_cons_meta WHERE place_id = ?',
        (place_id,),
    ).fetchone()
    if not row:
        return None
    return dict_from_row(cursor, row)


def _should_refresh(meta, current_review_count):
    if not meta:
        return current_review_count > 0
    last_generated_at = meta.get('last_generated_at')
    last_count = meta.get('review_count_at_last_generation') or 0

    if current_review_count - last_count >= PROS_CONS_MIN_NEW_REVIEWS:
        return True

    if not last_generated_at:
        return True
    try:
        if isinstance(last_generated_at, str):
            parsed_dt = datetime.fromisoformat(last_generated_at.replace('Z', '+00:00'))
        else:
            parsed_dt = last_generated_at
        if parsed_dt.tzinfo is not None:
            parsed_dt = parsed_dt.replace(tzinfo=None)
        if datetime.utcnow() - parsed_dt >= timedelta(days=PROS_CONS_REFRESH_INTERVAL_DAYS):
            return True
    except Exception:
        return True
    return False


def _replace_points(cursor, place_id, point_type, new_texts):
    existing_rows = cursor.execute(
        'SELECT id, text FROM shop_pros_cons WHERE place_id = ? AND point_type = ?',
        (place_id, point_type),
    ).fetchall()
    existing_by_norm = {_normalize_text(r[1]): r[0] for r in existing_rows}

    kept_ids = []
    now = datetime.utcnow().isoformat()
    for text in new_texts:
        norm = _normalize_text(text)
        existing_id = existing_by_norm.get(norm)
        if existing_id:
            kept_ids.append(existing_id)
            continue
        cursor.execute(
            'INSERT INTO shop_pros_cons (place_id, point_type, text, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
            (place_id, point_type, text, now, now),
        )
        kept_ids.append(cursor.lastrowid if hasattr(cursor, 'lastrowid') else None)

    stale_ids = [rid for norm, rid in existing_by_norm.items() if norm not in {_normalize_text(t) for t in new_texts}]
    if stale_ids:
        placeholders = ','.join('?' * len(stale_ids))
        cursor.execute(f'DELETE FROM shop_pros_cons WHERE id IN ({placeholders})', stale_ids)


def maybe_refresh_pros_cons(place_id, shop_name):
    """Jalankan batch job ekstraksi AI HANYA jika kondisi trigger (waktu/kuota) terpenuhi."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        review_texts, total_count = _get_review_stats(cursor, place_id)
        meta = _get_meta(cursor, place_id)

        if not _should_refresh(meta, total_count):
            return

        pros, cons = _generate_pros_cons_via_llm(shop_name or place_id, review_texts)
        if not pros and not cons:
            return

        _replace_points(cursor, place_id, 'pro', pros)
        _replace_points(cursor, place_id, 'con', cons)

        now = datetime.utcnow().isoformat()
        if meta:
            cursor.execute(
                'UPDATE shop_pros_cons_meta SET last_generated_at = ?, review_count_at_last_generation = ? WHERE place_id = ?',
                (now, total_count, place_id),
            )
        else:
            cursor.execute(
                'INSERT INTO shop_pros_cons_meta (place_id, last_generated_at, review_count_at_last_generation) VALUES (?, ?, ?)',
                (place_id, now, total_count),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[PROS_CONS] maybe_refresh_pros_cons failed for {place_id}: {e}")
    finally:
        conn.close()


def get_pros_cons(place_id, user_id=None):
    """Ambil poin pro/con + jumlah vote (+ vote user jika user_id diberikan), diurutkan upvote terbanyak."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        rows = cursor.execute(
            'SELECT id, point_type, text FROM shop_pros_cons WHERE place_id = ? ORDER BY id ASC',
            (place_id,),
        ).fetchall()
        point_ids = [r[0] for r in rows]

        upvotes = {}
        downvotes = {}
        user_votes = {}
        if point_ids:
            placeholders = ','.join('?' * len(point_ids))
            vote_rows = cursor.execute(
                f'SELECT point_id, vote_type, COUNT(*) FROM shop_pros_cons_votes '
                f'WHERE point_id IN ({placeholders}) GROUP BY point_id, vote_type',
                point_ids,
            ).fetchall()
            for pid, vtype, count in vote_rows:
                if vtype == 'up':
                    upvotes[pid] = count
                elif vtype == 'down':
                    downvotes[pid] = count

            if user_id:
                my_vote_rows = cursor.execute(
                    f'SELECT point_id, vote_type FROM shop_pros_cons_votes '
                    f'WHERE user_id = ? AND point_id IN ({placeholders})',
                    [user_id] + point_ids,
                ).fetchall()
                user_votes = {pid: vtype for pid, vtype in my_vote_rows}

        pros, cons = [], []
        for pid, ptype, text in rows:
            item = {
                'id': pid,
                'text': text,
                'upvotes': upvotes.get(pid, 0),
                'downvotes': downvotes.get(pid, 0),
                'user_vote': user_votes.get(pid),
            }
            (pros if ptype == 'pro' else cons).append(item)

        pros.sort(key=lambda x: -x['upvotes'])
        cons.sort(key=lambda x: -x['upvotes'])

        meta = _get_meta(cursor, place_id)
        return {
            'success': True,
            'pros': pros,
            'cons': cons,
            'last_generated_at': meta.get('last_generated_at') if meta else None,
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def get_top_voted_pros_batch(place_ids, limit=3):
    """Poin keunggulan (pro) dengan net vote > 0, per toko. Return {place_id: [item, ...]}."""
    ids = [str(pid).strip() for pid in (place_ids or []) if str(pid).strip()]
    if not ids:
        return {}
    unique_ids = list(dict.fromkeys(ids))
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(unique_ids))
        rows = cursor.execute(
            f'''
            SELECT id, place_id, text
            FROM shop_pros_cons
            WHERE place_id IN ({placeholders}) AND point_type = 'pro'
            ORDER BY id ASC
            ''',
            unique_ids,
        ).fetchall()
        if not rows:
            return {pid: [] for pid in unique_ids}

        point_ids = [r[0] for r in rows]
        upvotes, downvotes = {}, {}
        vote_placeholders = ','.join('?' * len(point_ids))
        vote_rows = cursor.execute(
            f'''
            SELECT point_id, vote_type, COUNT(*)
            FROM shop_pros_cons_votes
            WHERE point_id IN ({vote_placeholders})
            GROUP BY point_id, vote_type
            ''',
            point_ids,
        ).fetchall()
        for pid, vtype, count in vote_rows:
            if vtype == 'up':
                upvotes[pid] = count
            elif vtype == 'down':
                downvotes[pid] = count

        by_place = {pid: [] for pid in unique_ids}
        for point_id, place_id, text in rows:
            pid = str(place_id or '').strip()
            up = int(upvotes.get(point_id, 0) or 0)
            down = int(downvotes.get(point_id, 0) or 0)
            net = up - down
            if net <= 0:
                continue
            cleaned = str(text or '').strip()
            if not cleaned:
                continue
            if pid not in by_place:
                by_place[pid] = []
            by_place[pid].append({
                'text': cleaned,
                'upvotes': up,
                'downvotes': down,
                'net': net,
            })
        for pid, items in by_place.items():
            items.sort(key=lambda x: (-int(x.get('net') or 0), -int(x.get('upvotes') or 0)))
            by_place[pid] = items[: max(1, int(limit))]
        return by_place
    except Exception as e:
        print(f'[PROS_CONS] get_top_voted_pros_batch failed: {e}')
        return {pid: [] for pid in unique_ids}
    finally:
        conn.close()


def toggle_pros_cons_vote(user_id, point_id, vote_type):
    """Upvote/downvote satu poin. Klik ulang pada vote yang sama -> batalkan vote.
    Klik vote berbeda -> ganti vote. Return { success, upvotes, downvotes, user_vote }."""
    if vote_type not in ('up', 'down'):
        return {'success': False, 'error': 'Invalid vote_type'}

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        point = cursor.execute('SELECT id, place_id FROM shop_pros_cons WHERE id = ?', (point_id,)).fetchone()
        if not point:
            return {'success': False, 'error': 'Point not found'}

        existing = cursor.execute(
            'SELECT vote_type FROM shop_pros_cons_votes WHERE user_id = ? AND point_id = ?',
            (user_id, point_id),
        ).fetchone()

        if existing and existing[0] == vote_type:
            cursor.execute(
                'DELETE FROM shop_pros_cons_votes WHERE user_id = ? AND point_id = ?',
                (user_id, point_id),
            )
            new_user_vote = None
        elif existing:
            cursor.execute(
                'UPDATE shop_pros_cons_votes SET vote_type = ? WHERE user_id = ? AND point_id = ?',
                (vote_type, user_id, point_id),
            )
            new_user_vote = vote_type
        else:
            cursor.execute(
                'INSERT INTO shop_pros_cons_votes (point_id, user_id, vote_type) VALUES (?, ?, ?)',
                (point_id, user_id, vote_type),
            )
            new_user_vote = vote_type

        upvotes = cursor.execute(
            "SELECT COUNT(*) FROM shop_pros_cons_votes WHERE point_id = ? AND vote_type = 'up'",
            (point_id,),
        ).fetchone()[0]
        downvotes = cursor.execute(
            "SELECT COUNT(*) FROM shop_pros_cons_votes WHERE point_id = ? AND vote_type = 'down'",
            (point_id,),
        ).fetchone()[0]

        conn.commit()
        return {
            'success': True,
            'upvotes': upvotes,
            'downvotes': downvotes,
            'user_vote': new_user_vote,
        }
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()
