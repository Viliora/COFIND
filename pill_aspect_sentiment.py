"""
Sentimen ulasan terhadap pill (aktivitas / fasilitas) — satu pintu masuk.

Root cause fix: badge, metadata gate, dan kontradiksi klaim profil memakai
aturan yang sama, bukan dict frasa terpisah per insiden.

Prioritas deteksi NEGATIF (cukup salah satu):
  1. Frasa eksplisit pill (PILL_MAPPING.contradiction_phrases + supplement global)
  2. Kata kunci pill + fragmen lemah dalam jendela token (review_weakness)
  3. Penyangkalan "tidak ada …" dekat keyword pill

POSITIF: menyebut keyword pill tanpa sinyal negatif di atas.
NETRAL: tidak menyebut pill.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Literal, Optional, Sequence

from metadata_prior import _phrase_unnegated
from review_weakness import (
    normalize_keyword_phrase,
    review_has_weakness_near_preference_keywords,
    text_matches_any_keyword,
)

PillSentiment = Literal['positive', 'negative', 'neutral']

# Supplement untuk keluhan yang tidak selalu dekat keyword di ulasan
# (mis. "berisik" vs pill suasana_tenang). Prefer tambah contradiction_phrases
# di PILL_MAPPING bila spesifik satu pill.
GLOBAL_CONTRADICTION_PHRASES: Dict[str, tuple] = {
    'kerja': (
        'wifi lemot', 'wifi lambat', 'wifi lelet', 'tidak ada wifi',
        'tidak nyaman kerja', 'tidak cocok kerja', 'tidak kondusif',
        'susah kerja', 'tidak bisa kerja', 'ribut tidak bisa fokus',
        'colokan kurang', 'tidak ada colokan',
    ),
    'belajar': (
        'tidak nyaman belajar', 'tidak cocok belajar', 'tidak kondusif',
        'berisik', 'bising', 'ribut', 'wifi lemot', 'wifi lambat',
        'tidak ada wifi',
    ),
    'wifi_kencang': (
        'wifi lemot', 'wifi lambat', 'wifi lelet', 'wifi putus', 'wifi jelek',
        'wifi error', 'tidak ada wifi', 'internet lemot', 'koneksi lemot',
        'koneksi lambat', 'sinyal lemah', 'wifi tidak kencang', 'wifi tidak lancar',
        'wifi tidak stabil',
    ),
    'banyak_colokan_terminal': (
        'tidak ada colokan', 'colokan kurang', 'susah charge', 'susah ngecas',
        'tidak ada stopkontak',
    ),
    'suasana_tenang': (
        'berisik', 'bising', 'ribut', 'sangat ramai', 'ramai sekali',
        'noisy', 'ribut sekali',
    ),
    'ruangan_ac': (
        'ac rusak', 'ac mati', 'tidak ada ac', 'ruangan panas', 'gerah',
        'pengap',
    ),
    'musholla': (
        'tidak ada musholla', 'tidak ada tempat salat', 'tidak ada ruang salat',
    ),
    'parkir_luas': (
        'tidak ada parkir', 'tanpa parkir',
    ),
    'toilet_bersih': (
        'toilet kotor', 'toilet jorok', 'wc kotor', 'kamar mandi kotor',
        'toilet bau',
    ),
    'area_outdoor': (
        'tidak ada outdoor', 'tidak ada area outdoor', 'tidak ada tempat outdoor',
        'tidak ada outdoor seating', 'tidak ada teras outdoor',
    ),
    'buka_sampai_malam_24_hours': (
        'tidak buka 24 jam', 'tutup cepat', 'jam tutup cepat',
    ),
    'ruang_privat': (
        'tidak ada ruang privat', 'tidak ada private room',
        'tidak ada ruang meeting',
    ),
    'meeting_sosialisasi': (
        'tidak cocok meeting', 'tidak nyaman rapat', 'ribut tidak bisa diskusi',
    ),
    'keluarga': (
        'tidak ramah anak', 'tidak cocok keluarga', 'tidak ramah keluarga',
    ),
}

_DENIAL_PREFIXES = ('tidak ada', 'ga ada', 'gak ada', 'nggak ada', 'enggak ada', 'belum ada', 'tanpa')


def expand_pill_keywords(pill: str, pill_mapping: Dict[str, dict]) -> List[str]:
    mapping = pill_mapping.get(pill) or {}
    out = [str(pill).lower()]
    out.extend(str(kw).lower() for kw in (mapping.get('review_keywords') or []))
    return list(dict.fromkeys(k for k in out if k))


def _explicit_contradiction_phrases(pill: str, pill_mapping: Dict[str, dict]) -> tuple:
    mapping = pill_mapping.get(pill) or {}
    from_mapping = tuple(mapping.get('contradiction_phrases') or ())
    from_global = GLOBAL_CONTRADICTION_PHRASES.get(pill) or ()
    merged = []
    seen = set()
    for phrase in (*from_mapping, *from_global):
        p = str(phrase or '').strip().lower()
        if not p or p in seen:
            continue
        seen.add(p)
        merged.append(p)
    return tuple(merged)


def _explicit_contradiction_hits(text: str, pill: str, pill_mapping: Dict[str, dict]) -> List[str]:
    normalized = normalize_keyword_phrase(text)
    if not normalized:
        return []
    found = []
    for phrase in _explicit_contradiction_phrases(pill, pill_mapping):
        if _phrase_unnegated(normalized, phrase):
            found.append(phrase)
    return found


def _denial_near_pill_keywords(text: str, keywords: Sequence[str]) -> bool:
    normalized = normalize_keyword_phrase(text)
    if not normalized or not keywords:
        return False
    if not text_matches_any_keyword(text, keywords):
        return False
    for prefix in _DENIAL_PREFIXES:
        if prefix in normalized:
            return True
    return False


def review_negates_pill(
    text: str,
    pill: str,
    pill_mapping: Dict[str, dict],
    *,
    preference_keywords: Optional[Iterable[str]] = None,
) -> bool:
    """True jika ulasan menentang klaim/badge pill (keluhan terhadap aspek itu)."""
    body = str(text or '').strip()
    if len(body) < 4:
        return False
    if _explicit_contradiction_hits(body, pill, pill_mapping):
        return True
    keywords = list(preference_keywords or expand_pill_keywords(pill, pill_mapping))
    if review_has_weakness_near_preference_keywords(body, keywords):
        return True
    if _denial_near_pill_keywords(body, keywords):
        return True
    return False


def review_supports_pill(
    text: str,
    pill: str,
    pill_mapping: Dict[str, dict],
    *,
    preference_keywords: Optional[Iterable[str]] = None,
) -> bool:
    keywords = list(preference_keywords or expand_pill_keywords(pill, pill_mapping))
    if not text_matches_any_keyword(text, keywords):
        return False
    return not review_negates_pill(text, pill, pill_mapping, preference_keywords=keywords)


def review_sentiment_for_pill(
    text: str,
    pill: str,
    pill_mapping: Dict[str, dict],
    *,
    preference_keywords: Optional[Iterable[str]] = None,
) -> PillSentiment:
    keywords = list(preference_keywords or expand_pill_keywords(pill, pill_mapping))
    if review_negates_pill(text, pill, pill_mapping, preference_keywords=keywords):
        return 'negative'
    if text_matches_any_keyword(text, keywords):
        return 'positive'
    return 'neutral'


def aggregate_reviews_sentiment(
    reviews: Sequence[object],
    pill: str,
    pill_mapping: Dict[str, dict],
    *,
    extra_texts: Optional[Sequence[str]] = None,
) -> PillSentiment:
    """Gabung beberapa ulasan/kutipan: negatif mengalahkan, lalu positif, lalu netral."""
    keywords = expand_pill_keywords(pill, pill_mapping)
    texts: List[str] = []
    for review in reviews or []:
        if isinstance(review, dict):
            texts.append(str(review.get('text') or review.get('review_text') or ''))
        else:
            texts.append(str(review or ''))
    for chunk in extra_texts or []:
        texts.append(str(chunk or ''))

    seen_negative = False
    seen_positive = False
    for raw in texts:
        text = str(raw or '').strip()
        if len(text) < 6:
            continue
        sent = review_sentiment_for_pill(text, pill, pill_mapping, preference_keywords=keywords)
        if sent == 'negative':
            seen_negative = True
            break
        if sent == 'positive':
            seen_positive = True
    if seen_negative:
        return 'negative'
    if seen_positive:
        return 'positive'
    return 'neutral'


def review_contradicts_metadata_claim(
    text: str,
    pill: str,
    pill_mapping: Dict[str, dict],
) -> bool:
    """Alias untuk metadata gate / kutipan kontradiksi."""
    return review_negates_pill(text, pill, pill_mapping)
