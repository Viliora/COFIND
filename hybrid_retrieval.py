"""
Fase 2 — Hybrid Retrieval untuk rekomendasi Cofind.

Pencarian kandidat: BM25 (sparse, kata persis) + embedding (dense, makna),
lalu sedikit bobot kualitas toko (rating / Overall Experience).

PILL_MAPPING dipakai sebagai TEKS QUERY, bukan gerbang lolos/gugur:
  - BM25: label pill + review_keywords (nama fasilitas, istilah spesifik)
  - Dense: kalimat intent dari label pill ("cocok untuk kerja, wifi kencang")
Review yang memparafrase preferensi tetap bisa unggul lewat cosine similarity.

Env:
  COFIND_HYBRID_BM25_WEIGHT        default 0.45
  COFIND_HYBRID_DENSE_WEIGHT       default 0.45
  COFIND_HYBRID_QUALITY_WEIGHT     default 0.10
  COFIND_RETRIEVAL_TOP_K           default 7
  COFIND_DENSE_MAX_REVIEWS         ulasan per toko untuk max-pool dense (default: 20)
  COFIND_PROMPT_REVIEW_SCAN        ulasan yang di-scan saat pilih kutipan LLM (default: 60)
  COFIND_ACTIVITY_DENSE_MIN        ambang cosine gerbang aktivitas (default: 0.50)
  COFIND_LLM_MIN_FIT               fit_score minimum agar toko dipilih (default: 5.0)
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Sequence, Tuple

from bm25_utils import (
    build_bm25_index,
    build_query_tokens,
    normalize_bm25_scores,
    score_shops_bm25,
)
from logging_config import get_logger
from semantic_match import score_documents

logger = get_logger('recommend')

_TOKEN_RE = re.compile(r'[a-z0-9]+', re.IGNORECASE)
_MIN_REVIEW_CHARS = 15
_LEXICAL_WEIGHT = 0.3
_DENSE_WEIGHT = 0.7
# Token generik hasil pecahan frasa "nongkrong game" / "main game" / "push rank".
# Kalau ikut gerbang aktivitas, ulasan "enak nongkrong" ikut lolos.
_ACTIVITY_STOP_TOKENS_BY_PILL = {
    'bermain game': frozenset({
        'nongkrong', 'main', 'bareng', 'gas', 'push', 'rank', 'bermain', 'mobile',
    }),
}


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


def bm25_weight() -> float:
    return _env_float('COFIND_HYBRID_BM25_WEIGHT', 0.45, min_value=0.0, max_value=1.0)


def dense_weight() -> float:
    return _env_float('COFIND_HYBRID_DENSE_WEIGHT', 0.45, min_value=0.0, max_value=1.0)


def quality_weight() -> float:
    return _env_float('COFIND_HYBRID_QUALITY_WEIGHT', 0.10, min_value=0.0, max_value=1.0)


def retrieval_top_k() -> int:
    return _env_int('COFIND_RETRIEVAL_TOP_K', 7, min_value=3, max_value=20)


def dense_max_reviews() -> int:
    return _env_int('COFIND_DENSE_MAX_REVIEWS', 20, min_value=5, max_value=80)


def prompt_review_scan() -> int:
    return _env_int('COFIND_PROMPT_REVIEW_SCAN', 60, min_value=10, max_value=200)


def prompt_review_limit() -> int:
    return _env_int('COFIND_PROMPT_REVIEW_LIMIT', 8, min_value=3, max_value=20)


def activity_dense_min() -> float:
    return _env_float('COFIND_ACTIVITY_DENSE_MIN', 0.50, min_value=0.2, max_value=0.9)


def min_fit_score() -> float:
    return _env_float('COFIND_LLM_MIN_FIT', 5.0, min_value=0.0, max_value=10.0)


def tokenize_simple(value: str) -> List[str]:
    """Token alnum lowercase, tanpa kamus slang / stemming."""
    return [t.lower() for t in _TOKEN_RE.findall(str(value or '')) if len(t) > 1]


def minmax_normalize(raw_by_place: Dict[str, float]) -> Dict[str, float]:
    return normalize_bm25_scores(raw_by_place)


def review_text(review: object) -> str:
    if isinstance(review, dict):
        return str(review.get('text') or review.get('review_text') or '').strip()
    return str(review or '').strip()


def lexical_review_score(text: str, query_tokens: Sequence[str]) -> float:
    """Porsi token query yang muncul di ulasan (0..1), termasuk imbuhan ringan."""
    q = [t for t in (query_tokens or []) if t]
    if not q:
        return 0.0
    tokens = set(tokenize_simple(text))
    if not tokens:
        return 0.0
    unique_q = list(dict.fromkeys(q))

    def hit(query_tok: str) -> bool:
        if query_tok in tokens:
            return True
        if len(query_tok) < 4:
            return False
        for review_tok in tokens:
            if len(review_tok) < 4:
                continue
            if (
                review_tok.startswith(query_tok)
                or query_tok.startswith(review_tok)
                or review_tok.endswith(query_tok)
            ):
                return True
        return False

    hits = sum(1 for tok in unique_q if hit(tok))
    return hits / max(1, len(unique_q))


def _usable_reviews(reviews: Sequence[object]) -> List[object]:
    out = []
    seen = set()
    for review in reviews or []:
        text = review_text(review)
        if len(text) < _MIN_REVIEW_CHARS:
            continue
        key = text.lower()[:160]
        if key in seen:
            continue
        seen.add(key)
        out.append(review)
    return out


def _select_reviews_for_embedding(
    reviews: Sequence[object],
    query_tokens: Sequence[str],
    *,
    limit: int,
    primary_tokens: Optional[Sequence[str]] = None,
) -> List[object]:
    """
    Pilih ulasan yang akan di-encode. Utamakan overlap token aktivitas
    (`primary_tokens`), lalu query lengkap, lalu ulasan terbaru.
    """
    usable = _usable_reviews(reviews)
    if len(usable) <= limit:
        return usable

    def rank_key(row: object) -> tuple:
        text = review_text(row)
        primary = lexical_review_score(text, primary_tokens or [])
        full = lexical_review_score(text, query_tokens)
        return (primary, full)

    ranked = sorted(usable, key=rank_key, reverse=True)
    chosen = []
    seen = set()
    for row in ranked:
        if len(chosen) >= limit:
            break
        primary, full = rank_key(row)
        if primary <= 0 and full <= 0:
            break
        chosen.append(row)
        seen.add(id(row))
    for row in usable:
        if len(chosen) >= limit:
            break
        if id(row) in seen:
            continue
        chosen.append(row)
    return chosen[:limit]


def rank_reviews_for_query(
    reviews: Sequence[object],
    *,
    query_text: str,
    query_tokens: Sequence[str],
    limit: Optional[int] = None,
    scan_limit: Optional[int] = None,
    activity_tokens: Optional[Sequence[str]] = None,
    activity_query_text: str = '',
    attribute_tokens: Optional[Sequence[str]] = None,
) -> List[object]:
    """
    Urutkan ulasan menurut relevansi. Sinyal aktivitas (nge-game, kerja, …)
    lebih berat daripada fasilitas tambahan, supaya kutipan game mengalahkan
    ulasan 'wifi lancar' yang tidak membahas aktivitas.
    """
    take = limit if limit is not None else prompt_review_limit()
    scan = scan_limit if scan_limit is not None else prompt_review_scan()
    usable = _usable_reviews(reviews)
    if not usable:
        return []
    act_tokens = list(activity_tokens or [])
    attr_tokens = list(attribute_tokens or [])
    pool = _select_reviews_for_embedding(
        usable,
        query_tokens,
        limit=scan,
        primary_tokens=act_tokens,
    )
    texts = [review_text(row) for row in pool]
    full_cosines, telemetry = score_documents(query_text, texts)
    if telemetry.get('skipped'):
        logger.debug(f"rank_reviews_for_query dense dilewati: {telemetry.get('skipped')}")
        full_cosines = [0.0] * len(pool)
    act_cosines = full_cosines
    if activity_query_text and activity_query_text != query_text:
        act_cosines, act_tel = score_documents(activity_query_text, texts)
        if act_tel.get('skipped'):
            act_cosines = full_cosines

    scored = []
    for idx, row in enumerate(pool):
        text = texts[idx]
        act_lex = lexical_review_score(text, act_tokens) if act_tokens else 0.0
        attr_lex = lexical_review_score(text, attr_tokens) if attr_tokens else 0.0
        full_lex = lexical_review_score(text, query_tokens)
        act_dense = max(0.0, float(act_cosines[idx]) if idx < len(act_cosines) else 0.0)
        full_dense = max(0.0, float(full_cosines[idx]) if idx < len(full_cosines) else 0.0)
        if act_tokens:
            combined = (
                0.45 * act_dense
                + 0.30 * act_lex
                + 0.15 * full_dense
                + 0.10 * attr_lex
            )
            if act_lex > 0:
                combined += 0.20
        else:
            combined = _DENSE_WEIGHT * full_dense + _LEXICAL_WEIGHT * full_lex
        scored.append((combined, act_lex, act_dense, row))
    scored.sort(key=lambda item: (-item[0], -item[1], -item[2]))
    return [row for _, _, _, row in scored[:take]]


def build_sparse_query_tokens(
    pills: Sequence[str],
    *,
    pill_labels: Dict[str, str],
    pill_mapping: Dict[str, dict],
) -> List[str]:
    """Token BM25: id pill + label + review_keywords dari mapping (query, bukan filter)."""

    def keywords(pill: str) -> List[str]:
        mapping = pill_mapping.get(pill) or {}
        out = [pill_labels.get(pill, pill)]
        out.extend(mapping.get('review_keywords') or [])
        return out

    return build_query_tokens(pills, keywords, tokenize_fn=tokenize_simple)


def build_dense_query_text(
    pills: Sequence[str],
    *,
    pill_labels: Dict[str, str],
) -> str:
    """Kalimat intent pendek agar embedding tidak kena keyword stuffing."""
    labels = [str(pill_labels.get(p, p) or p).strip() for p in pills or [] if p]
    if not labels:
        return ''
    return 'Cari coffee shop yang cocok untuk: ' + ', '.join(labels)


def score_shops_dense(
    profiles: Sequence[dict],
    query_text: str,
    *,
    query_tokens: Optional[Sequence[str]] = None,
    primary_tokens: Optional[Sequence[str]] = None,
) -> Tuple[Dict[str, float], Dict[str, object]]:
    """
    Skor dense per toko = cosine tertinggi di antara ulasannya (max-pool).
    Paling banyak `dense_max_reviews` ulasan per toko yang di-encode.
    `primary_tokens` (biasanya token aktivitas) diutamakan saat memilih ulasan.
    """
    cap = dense_max_reviews()
    owners: List[str] = []
    documents: List[str] = []
    reviews_per_shop: Dict[str, int] = {}
    primary = list(primary_tokens) if primary_tokens is not None else list(query_tokens or [])

    for profile in profiles or []:
        pid = str(profile.get('place_id') or '').strip()
        if not pid:
            continue
        selected = _select_reviews_for_embedding(
            profile.get('reviews') or [],
            query_tokens or [],
            limit=cap,
            primary_tokens=primary,
        )
        if not selected:
            reviews_per_shop[pid] = 0
            continue
        reviews_per_shop[pid] = len(selected)
        for row in selected:
            owners.append(pid)
            documents.append(review_text(row))

    telemetry: Dict[str, object] = {
        'shops': len(reviews_per_shop),
        'reviews_embedded': len(documents),
        'max_reviews_per_shop': cap,
        'pool': 'max',
    }
    if not documents:
        telemetry['skipped'] = 'no_reviews'
        return {pid: 0.0 for pid in reviews_per_shop}, telemetry

    raw_list, doc_telemetry = score_documents(query_text, documents)
    telemetry.update(doc_telemetry)

    best: Dict[str, float] = {pid: 0.0 for pid in reviews_per_shop}
    for idx, pid in enumerate(owners):
        score = float(raw_list[idx]) if idx < len(raw_list) else 0.0
        if score > best.get(pid, 0.0):
            best[pid] = score
    return best, telemetry


def activity_signal_tokens(
    tokens: Sequence[str],
    activity_pills: Optional[Sequence[str]] = None,
) -> List[str]:
    """Buang token generik agar gerbang/kutipan aktivitas tidak tertipu 'nongkrong'."""
    stops = set()
    for pill in activity_pills or []:
        stops |= _ACTIVITY_STOP_TOKENS_BY_PILL.get(pill, frozenset())
    return [t for t in tokens if t and t not in stops]


def activity_phrases(
    activity_pills: Sequence[str],
    *,
    pill_labels: Dict[str, str],
    pill_mapping: Dict[str, dict],
) -> List[str]:
    """Frasa multi-kata untuk gerbang (mobile legends, push rank, nge-game)."""
    phrases = []
    seen = set()
    for pill in activity_pills or []:
        mapping = pill_mapping.get(pill) or {}
        candidates = [str(pill_labels.get(pill, pill) or '')]
        candidates.extend(str(kw) for kw in (mapping.get('review_keywords') or []))
        for raw in candidates:
            phrase = ' '.join(str(raw or '').lower().split())
            if len(phrase) < 6:
                continue
            if 'nongkrong' in phrase:
                continue
            if pill == 'bermain game' and not any(
                marker in phrase
                for marker in ('game', 'mabar', 'legends', 'valorant', 'pubg', 'turnamen', 'rank')
            ):
                continue
            if ' ' not in phrase and '-' not in phrase:
                continue
            if phrase in seen:
                continue
            seen.add(phrase)
            phrases.append(phrase)
    return phrases


def shop_has_activity_signal(
    reviews: Sequence[object],
    activity_tokens: Sequence[str],
    phrases: Optional[Sequence[str]] = None,
) -> bool:
    if shop_activity_lexical_max(reviews, activity_tokens) > 0:
        return True
    needles = [p for p in (phrases or []) if p]
    if not needles:
        return False
    for row in _usable_reviews(reviews):
        text = review_text(row).lower()
        if any(p in text for p in needles):
            return True
    return False


def shop_activity_lexical_max(reviews: Sequence[object], activity_tokens: Sequence[str]) -> float:
    """Skor leksikal aktivitas tertinggi di seluruh ulasan toko (tanpa embedding)."""
    best = 0.0
    for row in _usable_reviews(reviews):
        best = max(best, lexical_review_score(review_text(row), activity_tokens))
        if best >= 1.0:
            break
    return best


def text_matches_tokens(text: str, tokens: Sequence[str]) -> bool:
    return lexical_review_score(text, tokens) > 0


def compute_pill_coverage(
    texts: Sequence[str],
    pills: Sequence[str],
    *,
    pill_labels: Dict[str, str],
    pill_mapping: Dict[str, dict],
) -> Tuple[List[str], List[str]]:
    """Pill yang disebut di kumpulan teks vs yang belum."""
    covered = []
    uncovered = []
    for pill in pills or []:
        tokens = build_sparse_query_tokens(
            [pill], pill_labels=pill_labels, pill_mapping=pill_mapping,
        )
        if any(text_matches_tokens(str(text or ''), tokens) for text in texts):
            covered.append(pill)
        else:
            uncovered.append(pill)
    return covered, uncovered


def _blend_weights(has_bm25: bool, has_dense: bool, has_quality: bool) -> Dict[str, float]:
    """Normalisasi bobot ke komponen yang benar-benar ada."""
    parts = {
        'bm25': bm25_weight() if has_bm25 else 0.0,
        'dense': dense_weight() if has_dense else 0.0,
        'quality': quality_weight() if has_quality else 0.0,
    }
    total = sum(parts.values())
    if total <= 0:
        return {'bm25': 0.0, 'dense': 0.0, 'quality': 0.0}
    return {key: value / total for key, value in parts.items()}


def _activity_attribute_weights(has_attribute: bool, has_quality: bool) -> Dict[str, float]:
    """Aktivitas ~65%, fasilitas tambahan ~25%, kualitas ~10% (dinormalisasi)."""
    parts = {
        'activity': 0.65,
        'attribute': 0.25 if has_attribute else 0.0,
        'quality': 0.10 if has_quality else 0.0,
    }
    total = sum(parts.values())
    if total <= 0:
        return {'activity': 1.0, 'attribute': 0.0, 'quality': 0.0}
    return {key: value / total for key, value in parts.items()}


def retrieve_top_k(
    profiles: Sequence[dict],
    pills: Sequence[str],
    *,
    pill_labels: Dict[str, str],
    pill_mapping: Dict[str, dict],
    quality_by_place: Optional[Dict[str, Optional[float]]] = None,
    top_k: Optional[int] = None,
    activity_pills: Optional[Sequence[str]] = None,
    attribute_pills: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    """
    Hybrid search dengan gerbang aktivitas.

    Toko masuk top-k hanya jika ada sinyal aktivitas (ulasan menyebut token
    aktivitas, atau BM25 aktivitas > 0). Fasilitas tambahan hanya penguat skor,
    bukan pengganti bukti nge-game / kerja / dll.

    Return: candidates, query tokens/teks, token aktivitas, telemetry.
    """
    limit = top_k if top_k is not None else retrieval_top_k()
    quality_by_place = quality_by_place or {}
    if activity_pills is None:
        activity_list = list(pills or [])
        attribute_list = list(attribute_pills or [])
    else:
        activity_list = list(activity_pills or [])
        attribute_list = list(attribute_pills or [])

    telemetry: Dict[str, object] = {
        'profiles': len(profiles or []),
        'top_k': limit,
        'bm25_shops': 0,
        'dense': {},
        'kept_with_signal': 0,
        'activity_gated': 0,
        'activity_gate_on': bool(activity_list),
    }

    query_tokens = build_sparse_query_tokens(
        pills, pill_labels=pill_labels, pill_mapping=pill_mapping,
    )
    activity_tokens = activity_signal_tokens(
        build_sparse_query_tokens(
            activity_list, pill_labels=pill_labels, pill_mapping=pill_mapping,
        ) if activity_list else [],
        activity_list,
    )
    activity_phrase_list = activity_phrases(
        activity_list, pill_labels=pill_labels, pill_mapping=pill_mapping,
    ) if activity_list else []
    attribute_tokens = build_sparse_query_tokens(
        attribute_list, pill_labels=pill_labels, pill_mapping=pill_mapping,
    ) if attribute_list else []
    query_text = build_dense_query_text(pills, pill_labels=pill_labels)
    activity_query_text = (
        build_dense_query_text(activity_list, pill_labels=pill_labels)
        if activity_list else query_text
    )
    telemetry['query_tokens'] = len(query_tokens)
    telemetry['activity_tokens'] = len(activity_tokens)
    telemetry['dense_query'] = activity_query_text

    activity_bm25_raw: Dict[str, float] = {}
    attribute_bm25_raw: Dict[str, float] = {}
    try:
        place_ids, bm25_model, _corpus = build_bm25_index(
            profiles, tokenize_fn=tokenize_simple,
        )
        telemetry['bm25_shops'] = len(place_ids)
        if activity_tokens:
            activity_bm25_raw = score_shops_bm25(place_ids, bm25_model, activity_tokens)
        if attribute_tokens:
            attribute_bm25_raw = score_shops_bm25(place_ids, bm25_model, attribute_tokens)
        if not activity_tokens and query_tokens:
            activity_bm25_raw = score_shops_bm25(place_ids, bm25_model, query_tokens)
    except Exception as err:
        logger.warning(f"BM25 retrieval gagal: {err}")
        telemetry['bm25_error'] = str(err)[:200]

    dense_raw, dense_telemetry = score_shops_dense(
        profiles,
        activity_query_text,
        query_tokens=query_tokens,
        primary_tokens=activity_tokens or query_tokens,
    )
    telemetry['dense'] = dense_telemetry

    # Gerbang dulu, MinMax hanya di antara toko yang lolos supaya wifi-only
    # tidak menaikkan skala dan menyusup ke ranking.
    gated_rows = []
    for profile in profiles or []:
        pid = str(profile.get('place_id') or '').strip()
        if not pid:
            continue
        reviews = profile.get('reviews') or []
        act_lex = shop_activity_lexical_max(reviews, activity_tokens) if activity_tokens else 0.0
        act_bm25 = float(activity_bm25_raw.get(pid) or 0.0)
        act_dense = float(dense_raw.get(pid) or 0.0)
        if activity_list:
            # Bukti aktivitas: kata/frasa di ulasan mana pun (bukan BM25/dense
            # semata). Token generik seperti "nongkrong" tidak dihitung.
            if not shop_has_activity_signal(reviews, activity_tokens, activity_phrase_list):
                continue
        else:
            if act_bm25 + act_dense <= 1e-9:
                continue
        quality_raw = quality_by_place.get(pid)
        try:
            quality_s = None if quality_raw is None else float(quality_raw)
        except (TypeError, ValueError):
            quality_s = None
        gated_rows.append({
            'place_id': pid,
            'name': profile.get('name') or '',
            'profile': profile,
            'act_lex': act_lex,
            'act_bm25_raw': act_bm25,
            'act_dense_raw': act_dense,
            'attr_bm25_raw': float(attribute_bm25_raw.get(pid) or 0.0),
            'quality_s': quality_s,
        })

    telemetry['activity_gated'] = len(gated_rows)
    act_bm25_norm = minmax_normalize(
        {row['place_id']: row['act_bm25_raw'] for row in gated_rows}
    ) if gated_rows else {}
    act_dense_norm = minmax_normalize(
        {row['place_id']: row['act_dense_raw'] for row in gated_rows}
    ) if gated_rows else {}
    act_lex_norm = minmax_normalize(
        {row['place_id']: row['act_lex'] for row in gated_rows}
    ) if gated_rows else {}
    attr_bm25_norm = minmax_normalize(
        {row['place_id']: row['attr_bm25_raw'] for row in gated_rows}
    ) if gated_rows else {}

    has_attr = any(row['attr_bm25_raw'] > 0 for row in gated_rows)
    scored = []
    for row in gated_rows:
        pid = row['place_id']
        act_combo = (
            0.40 * float(act_bm25_norm.get(pid) or 0.0)
            + 0.35 * float(act_dense_norm.get(pid) or 0.0)
            + 0.25 * float(act_lex_norm.get(pid) or 0.0)
        )
        attr_s = float(attr_bm25_norm.get(pid) or 0.0)
        quality_s = row['quality_s']
        weights = _activity_attribute_weights(has_attr, quality_s is not None)
        total = act_combo * weights['activity'] + attr_s * weights['attribute']
        if quality_s is not None:
            total += quality_s * weights['quality']
        scored.append({
            'place_id': pid,
            'name': row['name'],
            'score': round(total, 4),
            'profile': row['profile'],
            'score_detail': {
                'bm25_raw': round(row['act_bm25_raw'], 4),
                'bm25_score': round(float(act_bm25_norm.get(pid) or 0.0), 4),
                'dense_raw': round(row['act_dense_raw'], 4),
                'dense_score': round(float(act_dense_norm.get(pid) or 0.0), 4),
                'activity_lex': round(row['act_lex'], 4),
                'attribute_bm25': round(row['attr_bm25_raw'], 4),
                'quality_score': None if quality_s is None else round(quality_s, 4),
                'score_weights': weights,
                'total_score': round(total, 4),
                'covered_pills': [],
                'uncovered_pills': list(pills or []),
            },
        })

    scored.sort(key=lambda item: -item['score'])
    telemetry['kept_with_signal'] = len(scored)
    telemetry['weights'] = _activity_attribute_weights(has_attr, True)
    return {
        'candidates': scored[:limit],
        'query_tokens': query_tokens,
        'query_text': query_text,
        'activity_tokens': activity_tokens,
        'attribute_tokens': attribute_tokens,
        'activity_query_text': activity_query_text,
        'telemetry': telemetry,
    }
