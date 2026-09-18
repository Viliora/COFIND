"""
Prior metadata fasilitas + penalti kontradiksi ulasan.

Metadata resmi (Google / owner / tab fasilitas) hanya penguat lemah: bisa jadi
self-claim. Skor tertinggi tetap dari ulasan relevan. Jika ulasan menentang
klaim itu, prior dibatalkan dan skor dipotong, lalu kutipan masuk caveat.

Env:
  COFIND_METADATA_GATE              default true
  COFIND_METADATA_PRIOR_WEIGHT      default 0.08 (plafon penguat)
  COFIND_METADATA_PENALTY_WEIGHT    default 0.18 (bisa melebihi prior)
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence

from slang_normalize import normalize_text_with_slang

_PARKING_HARD = frozenset({
    'sulit', 'agak_sulit', 'sangat_sulit', 'sempit', 'sulit parkir',
})
_PARKING_EASY = frozenset({
    'mudah', 'lega', 'luas', 'banyak', 'mudah parkir',
})
_NEGATION_PREFIXES = frozenset({
    'tidak', 'bukan', 'jangan', 'belum', 'tanpa', 'ga', 'gak', 'nggak', 'enggak',
})

# Frasa (setelah normalisasi slang) yang menentang klaim pill.
# "tidak berisik" tidak masuk karena dicek unnegated.
_CONTRADICTION_PHRASES: Dict[str, tuple] = {
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
        'parkir susah', 'parkir sempit', 'parkir sulit', 'sulit parkir',
        'parkiran sempit', 'susah parkir',
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


def _env_flag(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or '').strip().lower()
    if not raw:
        return default
    return raw in ('1', 'true', 'yes', 'on')


def _env_float(name: str, default: float, *, min_value: float, max_value: float) -> float:
    raw = (os.getenv(name) or '').strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(min_value, min(max_value, value))


def metadata_gate_enabled() -> bool:
    return _env_flag('COFIND_METADATA_GATE', True)


def metadata_prior_weight() -> float:
    return _env_float('COFIND_METADATA_PRIOR_WEIGHT', 0.08, min_value=0.0, max_value=0.2)


def metadata_penalty_weight() -> float:
    return _env_float('COFIND_METADATA_PENALTY_WEIGHT', 0.18, min_value=0.0, max_value=0.5)


def review_text(review: object) -> str:
    if isinstance(review, dict):
        return str(review.get('text') or review.get('review_text') or '').strip()
    return str(review or '').strip()


def _group_has_key(facilities: dict, group: str, key: str) -> bool:
    bucket = (facilities or {}).get(group)
    wanted = str(key or '').strip()
    if not wanted:
        return False
    if isinstance(bucket, dict):
        return bucket.get(wanted) is True
    if isinstance(bucket, list):
        lowered = {str(item).strip().lower() for item in bucket}
        return wanted.lower() in lowered or wanted.replace('_', ' ').lower() in lowered
    return False


def _parking_difficulty(facilities: dict) -> str:
    parking = (facilities or {}).get('parking') or {}
    if not isinstance(parking, dict):
        return ''
    return str(parking.get('parking_difficulty') or '').strip().lower()


def pill_metadata_claimed(facilities: dict, pill: str, mapping: dict) -> List[dict]:
    """Field fasilitas resmi yang mendukung pill ini (klaim profil)."""
    fields = (mapping or {}).get('facility_fields') or {}
    hits = []
    for group, keys in fields.items():
        for key in keys or []:
            if _group_has_key(facilities, group, key):
                hits.append({'pill': pill, 'group': group, 'key': key})
    if pill == 'parkir_luas':
        difficulty = _parking_difficulty(facilities)
        if difficulty in _PARKING_EASY:
            hits.append({
                'pill': pill,
                'group': 'parking',
                'key': f'parking_difficulty:{difficulty}',
            })
        elif difficulty in _PARKING_HARD:
            # Klaim "parkir luas" dari flag lain dibatalkan oleh kesulitan parkir resmi.
            hits = [row for row in hits if row.get('group') != 'parking']
    return hits


def _phrase_unnegated(normalized: str, phrase: str) -> bool:
    """True jika frasa ada dan tidak dinegasi kata 'tidak/bukan' tepat sebelumnya."""
    needle = normalize_text_with_slang(phrase)
    if not needle:
        return False
    idx = normalized.find(needle)
    if idx < 0:
        return False
    prefix = normalized[:idx].split()
    if prefix and prefix[-1] in _NEGATION_PREFIXES:
        return False
    return True


def _contradiction_hits_for_text(text: str, pill: str) -> List[str]:
    normalized = normalize_text_with_slang(text)
    if not normalized:
        return []
    found = []
    for phrase in _CONTRADICTION_PHRASES.get(pill) or ():
        if _phrase_unnegated(normalized, phrase):
            found.append(phrase)
    return found


def collect_contradiction_quotes(
    reviews: Sequence[object],
    claimed_pills: Sequence[str],
    *,
    pill_labels: Optional[Dict[str, str]] = None,
    limit_per_pill: int = 2,
) -> List[dict]:
    pill_labels = pill_labels or {}
    quotes: List[dict] = []
    seen = set()
    for pill in claimed_pills:
        kept = 0
        for review in reviews or []:
            text = review_text(review)
            if len(text) < 6:
                continue
            hits = _contradiction_hits_for_text(text, pill)
            if not hits:
                continue
            key = normalize_text_with_slang(text)[:120]
            marker = f'{pill}:{key}'
            if marker in seen:
                continue
            seen.add(marker)
            quotes.append({
                'pill': pill,
                'pill_label': pill_labels.get(pill, pill),
                'quote': text,
                'reason': f'ulasan menentang klaim profil ({", ".join(hits[:2])})',
                'sentiment': 'caveat',
                'source': 'metadata_contradiction',
                'matched_terms': hits[:4],
                'rating': review.get('rating') if isinstance(review, dict) else None,
                'username': (
                    (review.get('username') or review.get('full_name'))
                    if isinstance(review, dict) else None
                ),
            })
            kept += 1
            if kept >= limit_per_pill:
                break
    return quotes


def evaluate_metadata_gate(
    profile: dict,
    pills: Sequence[str],
    *,
    pill_mapping: Dict[str, dict],
    pill_labels: Optional[Dict[str, str]] = None,
    attribute_pills: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    """Hitung klaim metadata fasilitas vs kontradiksi ulasan. Tidak mengubah skor."""
    empty = {
        'enabled': metadata_gate_enabled(),
        'claimed_pills': [],
        'claimed_fields': [],
        'matched_attribute_pills': [],
        'matched_attribute_labels': [],
        'prior': 0.0,
        'contradicted_pills': [],
        'contradiction': 0.0,
        'quotes': [],
    }
    if not metadata_gate_enabled():
        return empty

    facilities = (
        (profile or {}).get('facilities_raw')
        or (profile or {}).get('facilities')
        or {}
    )
    if not isinstance(facilities, dict):
        facilities = {}

    # Prior & label hanya dari fasilitas lapis 2 yang user pilih.
    # Pill aktivitas tetap dinilai dari ulasan, bukan dari klaim profil.
    if attribute_pills is None:
        score_pills = list(pills or [])
    else:
        score_pills = [str(p) for p in attribute_pills if p]

    claimed_fields: List[dict] = []
    claimed_pills: List[str] = []
    eligible = 0
    for pill in score_pills:
        mapping = pill_mapping.get(pill) or {}
        if not mapping.get('facility_fields'):
            continue
        eligible += 1
        hits = pill_metadata_claimed(facilities, pill, mapping)
        if hits:
            claimed_pills.append(pill)
            claimed_fields.extend(hits)

    prior = (len(claimed_pills) / eligible) if eligible else 0.0
    quotes = collect_contradiction_quotes(
        (profile or {}).get('reviews') or [],
        claimed_pills,
        pill_labels=pill_labels,
    )
    contradicted = list(dict.fromkeys(str(row.get('pill')) for row in quotes if row.get('pill')))
    # 1 ulasan menentang = 0.6; 2+ = 1.0. Jangan biarkan satu keluhan menghapus semua.
    contradiction = 0.0
    if contradicted:
        n = min(2, len(quotes))
        contradiction = 0.6 if n == 1 else 1.0
        if claimed_pills:
            contradiction *= len(contradicted) / max(1, len(claimed_pills))
            contradiction = min(1.0, contradiction)

    contradicted_set = set(contradicted)
    labels = pill_labels or {}
    matched_attribute_pills = [p for p in claimed_pills if p not in contradicted_set]
    matched_attribute_labels = [labels.get(p, p) for p in matched_attribute_pills]

    return {
        'enabled': True,
        'claimed_pills': claimed_pills,
        'claimed_fields': claimed_fields,
        'matched_attribute_pills': matched_attribute_pills,
        'matched_attribute_labels': matched_attribute_labels,
        'prior': round(prior, 4),
        'contradicted_pills': contradicted,
        'contradiction': round(contradiction, 4),
        'quotes': quotes,
    }


def fuse_metadata_score(
    base_score: float,
    gate: Dict[str, object],
    *,
    review_signal: float,
) -> Dict[str, float]:
    """
    Skor akhir = retrieval + prior lemah - penalti kontradiksi.

    Prior hanya aktif jika ada sinyal ulasan (review_signal > 0), jadi klaim
    owner tidak bisa mengangkat toko tanpa bukti review. Kontradiksi memotong
    prior dulu, lalu menambah penalti yang boleh lebih besar dari prior.
    """
    prior = float(gate.get('prior') or 0.0)
    contradiction = float(gate.get('contradiction') or 0.0)
    signal = max(0.0, min(1.0, float(review_signal or 0.0)))
    effective_prior = prior * (1.0 - contradiction)
    prior_boost = metadata_prior_weight() * effective_prior * signal
    penalty = metadata_penalty_weight() * contradiction
    fused = max(0.0, float(base_score or 0.0) + prior_boost - penalty)
    return {
        'prior_boost': round(prior_boost, 4),
        'penalty': round(penalty, 4),
        'fused_score': round(fused, 4),
    }
