"""
Lapisan LLM untuk rekomendasi Cofind (summary, personalisasi, grounding).

Fase 3 rerank produksi: cross-encoder (`cross_encoder_rerank.py`), bukan modul ini.

Env:
  COFIND_LLM_PERSONALIZATION        aktifkan konteks selera user (default: true)
  COFIND_LLM_GROUNDING_CHECK        grounding kutipan summary (default: true)
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Callable, Dict, List, Optional, Sequence

from hybrid_retrieval import review_text

try:  # opsional, sama seperti pemakaian di app.py
    import importlib

    _repair_json = importlib.import_module('json_repair').repair_json
except Exception:  # pragma: no cover
    _repair_json = None


# --------------------------------------------------------------------------
# Konfigurasi
# --------------------------------------------------------------------------

def _env_flag(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or '').strip().lower()
    if not raw:
        return default
    return raw in ('1', 'true', 'yes', 'on')


def _env_int(name: str, default: int, *, min_value: int, max_value: int) -> int:
    raw = (os.getenv(name) or '').strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(min_value, min(max_value, value))


def _env_float(name: str, default: float, *, min_value: float, max_value: float) -> float:
    raw = (os.getenv(name) or '').strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(min_value, min(max_value, value))


def personalization_enabled() -> bool:
    return _env_flag('COFIND_LLM_PERSONALIZATION', True)


def grounding_check_enabled() -> bool:
    return _env_flag('COFIND_LLM_GROUNDING_CHECK', True)


# Label vote shop (love/like/…) untuk blok personalisasi prompt LLM.
_RATING_PROMPT_LABELS: Dict[str, str] = {
    'love': 'sangat suka',
    'like': 'suka',
    'ok': 'biasa',
    'dislike': 'kurang suka',
    'hate': 'tidak suka',
}


def pipeline_config() -> Dict[str, object]:
    """Ringkasan flag pipeline untuk telemetry / endpoint status."""
    from cross_encoder_rerank import ce_rerank_enabled, ce_rerank_weight
    from rerank_blend import rerank_candidate_pool

    return {
        'ce_rerank': ce_rerank_enabled(),
        'ce_rerank_weight': ce_rerank_weight(),
        'personalization': personalization_enabled(),
        'grounding_check': grounding_check_enabled(),
        'rerank_candidate_pool': rerank_candidate_pool(),
    }


# --------------------------------------------------------------------------
# Tahap D: grounding — semua klaim tekstual harus bisa dilacak ke review asli
# --------------------------------------------------------------------------

_PUNCT_RE = re.compile(r'[^0-9a-z\u00c0-\u024f\s]')
_ELLIPSIS_RE = re.compile(r'\.\.\.|\u2026')
_QUOTED_SPAN_RE = re.compile(r'"([^"\n]{8,})"|\u201c([^\u201d\n]{8,})\u201d')
_MIN_FRAGMENT_TOKENS = 3


def normalize_for_grounding(text: object) -> str:
    """Lowercase + buang tanda baca supaya perbandingan kutipan tahan beda format."""
    lowered = str(text or '').lower().replace('-', ' ')
    cleaned = _PUNCT_RE.sub(' ', lowered)
    return re.sub(r'\s+', ' ', cleaned).strip()


def shop_corpus_text(reviews: Sequence[dict]) -> str:
    """Gabungan teks review satu toko sebagai basis pengecekan grounding."""
    parts = []
    for review in reviews or []:
        if isinstance(review, dict):
            text = str(review.get('text') or review.get('review_text') or '').strip()
        else:
            text = str(review or '').strip()
        if text:
            parts.append(text)
    return ' '.join(parts)


def text_is_grounded(candidate: object, corpus_text: object, *, min_overlap_ratio: float = 0.7) -> bool:
    """
    True bila `candidate` benar-benar berasal dari `corpus_text`.
    Kutipan yang dipotong ellipsis diperiksa per fragmen; fragmen terlalu pendek
    jatuh ke pengecekan rasio token supaya tidak menolak kutipan pendek yang sah.
    """
    raw = str(candidate or '').strip()
    corpus = normalize_for_grounding(corpus_text)
    if not raw or not corpus:
        return False

    checked = 0
    for fragment in _ELLIPSIS_RE.split(raw):
        normalized = normalize_for_grounding(fragment)
        if len(normalized.split()) < _MIN_FRAGMENT_TOKENS:
            continue
        checked += 1
        if normalized not in corpus:
            return False
    if checked:
        return True

    candidate_tokens = [t for t in normalize_for_grounding(raw).split() if len(t) > 1]
    if not candidate_tokens:
        return False
    corpus_tokens = set(corpus.split())
    hits = sum(1 for token in candidate_tokens if token in corpus_tokens)
    return (hits / len(candidate_tokens)) >= min_overlap_ratio


def extract_quoted_spans(text: object) -> List[str]:
    """Semua potongan di dalam tanda kutip (lurus maupun typografis)."""
    spans = []
    for straight, curly in _QUOTED_SPAN_RE.findall(str(text or '')):
        span = (straight or curly or '').strip()
        if span:
            spans.append(span)
    return spans


def ungrounded_quotes(text: object, corpus_text: object) -> List[str]:
    """Kutipan pada `text` yang tidak bisa ditemukan di korpus review."""
    corpus = normalize_for_grounding(corpus_text)
    if not corpus:
        return extract_quoted_spans(text)
    return [span for span in extract_quoted_spans(text) if not text_is_grounded(span, corpus)]


# --------------------------------------------------------------------------
# Parsing JSON output LLM
# --------------------------------------------------------------------------

def _extract_json_fragment(raw_text: object, *, expected: str) -> str:
    text = str(raw_text or '').strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text).strip()
    pattern = r'\[[\s\S]*\]' if expected == 'array' else r'\{[\s\S]*\}'
    match = re.search(pattern, text)
    return match.group(0).strip() if match else text


def _loads_json(raw_text: object, *, expected: str):
    """Parse JSON output LLM tanpa panggilan LLM tambahan."""
    fragment = _extract_json_fragment(raw_text, expected=expected)
    if not fragment:
        return None
    try:
        return json.loads(fragment)
    except Exception:
        pass
    if _repair_json is not None:
        try:
            return json.loads(str(_repair_json(fragment, skip_json_loads=True)))
        except Exception:
            return None
    return None


# --------------------------------------------------------------------------
# Tahap C: konteks personalisasi dari histori user
# --------------------------------------------------------------------------

def build_user_taste_profile(
    user_id: object,
    *,
    max_reviews: int = 6,
    max_favorites: int = 6,
    max_votes: int = 12,
) -> Dict[str, object]:
    """
    Ringkasan selera user dari data yang sudah dimiliki aplikasi:
    review yang pernah ia tulis, coffee shop favorit, dan penilaian tokonya.
    Dipakai hanya sebagai konteks preferensi, bukan sumber fakta tentang kandidat.
    """
    profile: Dict[str, object] = {
        'enabled': personalization_enabled(),
        'has_history': False,
        'avg_rating_given': None,
        'review_lines': [],
        'favorite_names': [],
        'vote_rating_bits': [],
        'vote_best_for_bits': [],
        'vote_slider_bits': [],
        'vote_shop_lines': [],
    }
    if not profile['enabled']:
        return profile
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return profile

    try:
        from db_backend import get_connection

        conn = get_connection()
        try:
            cursor = conn.cursor()
            review_rows = cursor.execute(
                'SELECT r.rating, r.review_text, c.name '
                'FROM reviews r LEFT JOIN coffee_shops c ON r.place_id = c.place_id '
                'WHERE r.user_id = ? ORDER BY r.created_at DESC LIMIT ?',
                (uid, int(max_reviews)),
            ).fetchall()
            favorite_rows = cursor.execute(
                'SELECT c.name FROM favorites f '
                'LEFT JOIN coffee_shops c ON f.place_id = c.place_id '
                'WHERE f.user_id = ? ORDER BY f.added_at DESC LIMIT ?',
                (uid, int(max_favorites)),
            ).fetchall()
            try:
                vote_rows = cursor.execute(
                    'SELECT sv.rating, sv.best_for, sv.pelayanan, sv.kebersihan, '
                    'sv.kenyamanan, sv.harga, c.name '
                    'FROM shop_votes sv LEFT JOIN coffee_shops c ON sv.place_id = c.place_id '
                    'WHERE sv.user_id = ? '
                    'ORDER BY COALESCE(sv.updated_at, sv.created_at) DESC LIMIT ?',
                    (uid, int(max_votes)),
                ).fetchall()
            except Exception:
                vote_rows = []
        finally:
            conn.close()
    except Exception as err:
        profile['error'] = str(err)[:200]
        return profile

    ratings = []
    review_lines = []
    for row in review_rows or []:
        rating, review_text, shop_name = (list(row) + [None, None, None])[:3]
        try:
            if rating is not None:
                ratings.append(float(rating))
        except (TypeError, ValueError):
            pass
        text = re.sub(r'\s+', ' ', str(review_text or '')).strip()
        if not text:
            continue
        if len(text) > 160:
            text = text[:157].rstrip() + '...'
        rating_label = f'{rating}\u2b50' if rating is not None else 'tanpa rating'
        shop_label = str(shop_name or 'coffee shop lain').strip()
        review_lines.append(f'({rating_label} di {shop_label}) "{text}"')

    favorite_names = []
    for row in favorite_rows or []:
        name = str((list(row) + [None])[0] or '').strip()
        if name and name not in favorite_names:
            favorite_names.append(name)

    rating_counts: Dict[str, int] = {}
    slider_sums: Dict[str, float] = {}
    slider_n: Dict[str, int] = {}
    vote_shop_lines = []
    for row in vote_rows or []:
        rating, _best_for_raw, pelayanan, kebersihan, kenyamanan, harga, shop_name = (
            list(row) + [None] * 7
        )[:7]
        rating_key = str(rating or '').strip().lower()
        if rating_key in _RATING_PROMPT_LABELS:
            rating_counts[rating_key] = rating_counts.get(rating_key, 0) + 1
        for field, val in (
            ('pelayanan', pelayanan),
            ('kebersihan', kebersihan),
            ('kenyamanan', kenyamanan),
            ('harga', harga),
        ):
            try:
                if val is not None:
                    slider_sums[field] = slider_sums.get(field, 0.0) + float(val)
                    slider_n[field] = slider_n.get(field, 0) + 1
            except (TypeError, ValueError):
                pass
        shop_label = str(shop_name or '').strip()
        if shop_label and len(vote_shop_lines) < 3:
            bits = []
            if rating_key in _RATING_PROMPT_LABELS:
                bits.append(_RATING_PROMPT_LABELS[rating_key])
            if bits:
                vote_shop_lines.append(f'{shop_label}: {", ".join(bits)}')

    vote_rating_bits = [
        f'{_RATING_PROMPT_LABELS[key]} ({count})'
        for key, count in sorted(rating_counts.items(), key=lambda item: (-item[1], item[0]))
        if count
    ]
    vote_slider_bits = [
        f'{field} {slider_sums[field] / slider_n[field]:.1f}/5'
        for field in ('pelayanan', 'kebersihan', 'kenyamanan', 'harga')
        if slider_n.get(field)
    ]

    profile['avg_rating_given'] = round(sum(ratings) / len(ratings), 2) if ratings else None
    profile['review_lines'] = review_lines
    profile['favorite_names'] = favorite_names
    profile['vote_rating_bits'] = vote_rating_bits
    profile['vote_best_for_bits'] = []
    profile['vote_slider_bits'] = vote_slider_bits
    profile['vote_shop_lines'] = vote_shop_lines
    profile['has_history'] = bool(
        review_lines or favorite_names or vote_rating_bits or vote_slider_bits
    )
    return profile


def format_user_taste_prompt_block(taste_profile: Optional[Dict[str, object]]) -> str:
    """Blok prompt personalisasi; string kosong bila user belum punya histori."""
    profile = taste_profile or {}
    if not profile.get('enabled') or not profile.get('has_history'):
        return ''

    lines = [
        'Konteks selera user (hanya untuk memahami preferensi; JANGAN dipakai sebagai fakta tentang kandidat):',
    ]
    if profile.get('avg_rating_given') is not None:
        lines.append(f"- Rata-rata rating yang biasa user berikan: {profile['avg_rating_given']}/5")
    vote_rating_bits = profile.get('vote_rating_bits') or []
    if vote_rating_bits:
        lines.append(f"- Penilaian toko yang biasa user pilih: {', '.join(vote_rating_bits[:4])}")
    vote_best_for_bits = profile.get('vote_best_for_bits') or []
    if vote_best_for_bits:
        lines.append(f"- Aktivitas yang user sering tandai cocok: {', '.join(vote_best_for_bits)}")
    vote_slider_bits = profile.get('vote_slider_bits') or []
    if vote_slider_bits:
        lines.append(f"- Pengalaman yang user utamakan: {', '.join(vote_slider_bits)}")
    for line in (profile.get('vote_shop_lines') or [])[:3]:
        lines.append(f'- Penilaian user sebelumnya: {line}')
    for line in (profile.get('review_lines') or [])[:4]:
        lines.append(f'- Ulasan user sebelumnya: {line}')
    favorites = profile.get('favorite_names') or []
    if favorites:
        lines.append(f"- Coffee shop favorit user: {', '.join(favorites[:5])}")
    return '\n'.join(lines)


# --------------------------------------------------------------------------
# Konteks aktivitas (prompt summary / CE query)
# --------------------------------------------------------------------------

def format_activity_context_block(
    activity_pills: Sequence[str],
    *,
    pill_mapping: Optional[Dict[str, dict]] = None,
    pill_labels: Optional[Dict[str, str]] = None,
) -> str:
    """Blok definisi + batasan aktivitas untuk prompt summary."""
    mapping = pill_mapping or {}
    labels = pill_labels or {}
    lines = ['Kebutuhan Aktivitas Pengguna:']
    added = False
    for pill in activity_pills or []:
        spec = mapping.get(pill) or {}
        label = str(spec.get('label') or labels.get(pill) or pill).strip()
        definition = re.sub(r'\s+', ' ', str(spec.get('definition') or '')).strip()
        negative = re.sub(r'\s+', ' ', str(spec.get('negative_scope') or '')).strip()
        if definition:
            lines.append(f'- {label}: {definition}')
            if negative:
                lines.append(f'  Batasan (bukan tujuan): {negative}')
            added = True
        elif label:
            lines.append(f'- {label}')
            added = True
    if not added:
        return ''
    return '\n'.join(lines)


