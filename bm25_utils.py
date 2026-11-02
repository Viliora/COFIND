"""
BM25 scoring untuk rekomendasi berbasis review.

Unit dokumen:
  - shop: satu dokumen = gabungan semua ulasan toko (legacy)
  - review: satu dokumen = satu ulasan; skor toko = agregasi (max atau jumlah top-N)
"""

from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from rank_bm25 import BM25Okapi
except Exception:  # pragma: no cover
    BM25Okapi = None


def build_query_tokens(
    pills: Sequence[str],
    pill_keyword_fn: Callable[[str], Sequence[str]],
    search_keywords: Optional[Sequence[str]] = None,
    tokenize_fn: Optional[Callable[[str], List[str]]] = None,
) -> List[str]:
    """Gabung keyword pill + search_keywords jadi token query unik (urutan stabil)."""
    tokenize_fn = tokenize_fn or (lambda s: [t for t in str(s or '').lower().split() if len(t) > 1])
    seen = set()
    tokens: List[str] = []

    def _add_phrase(phrase: str):
        for tok in tokenize_fn(phrase):
            if tok and tok not in seen:
                seen.add(tok)
                tokens.append(tok)

    for pill in pills or []:
        _add_phrase(str(pill or ''))
        for kw in pill_keyword_fn(pill) or []:
            _add_phrase(str(kw or ''))

    for kw in search_keywords or []:
        _add_phrase(str(kw or ''))

    return tokens


def review_row_text(review: dict) -> str:
    return str(
        review.get('text') or review.get('review_text') or '',
    ).strip()


def shop_document_text(reviews: Iterable[dict]) -> str:
    parts = []
    for review in reviews or []:
        text = review_row_text(review)
        if text:
            parts.append(text)
    return ' '.join(parts)


def build_bm25_index(
    profiles: Sequence[dict],
    tokenize_fn: Callable[[str], List[str]],
) -> Tuple[List[str], object, List[List[str]]]:
    """
    Return (place_ids, bm25_model, tokenized_corpus).
    Shop tanpa token tetap masuk dengan placeholder agar indeks selaras.
    """
    if BM25Okapi is None:
        raise RuntimeError('rank_bm25 belum terpasang. Jalankan: pip install rank_bm25')

    place_ids: List[str] = []
    corpus: List[List[str]] = []
    for profile in profiles or []:
        pid = str(profile.get('place_id') or '').strip()
        if not pid:
            continue
        doc_text = shop_document_text(profile.get('reviews') or [])
        tokens = tokenize_fn(doc_text)
        if not tokens:
            tokens = ['__empty__']
        place_ids.append(pid)
        corpus.append(tokens)

    if not corpus:
        return [], None, []

    return place_ids, BM25Okapi(corpus), corpus


def _review_id(review: dict) -> Optional[int]:
    rid = review.get('id') if isinstance(review, dict) else None
    try:
        return int(rid) if rid is not None else None
    except (TypeError, ValueError):
        return None


def build_bm25_review_index(
    profiles: Sequence[dict],
    tokenize_fn: Callable[[str], List[str]],
    *,
    expansion_by_review_id: Optional[Dict[int, str]] = None,
) -> Tuple[List[str], object, List[List[str]]]:
    """
    Satu entri korpus per ulasan. doc_place_ids[i] = place_id ulasan ke-i.

    `expansion_by_review_id` (document expansion / doc2query): teks prediksi query
    per review_id yang ditempel ke token ulasan sebelum diindeks.
    """
    if BM25Okapi is None:
        raise RuntimeError('rank_bm25 belum terpasang. Jalankan: pip install rank_bm25')

    expansions = expansion_by_review_id or {}
    doc_place_ids: List[str] = []
    corpus: List[List[str]] = []
    for profile in profiles or []:
        pid = str(profile.get('place_id') or '').strip()
        if not pid:
            continue
        for review in profile.get('reviews') or []:
            tokens = tokenize_fn(review_row_text(review))
            if not tokens:
                continue
            rid = _review_id(review)
            if rid is not None and expansions.get(rid):
                tokens = tokens + tokenize_fn(expansions[rid])
            doc_place_ids.append(pid)
            corpus.append(tokens)

    if not corpus:
        return [], None, []

    return doc_place_ids, BM25Okapi(corpus), corpus


def _scores_as_list(raw_scores) -> List[float]:
    if hasattr(raw_scores, 'tolist'):
        return raw_scores.tolist()
    return list(raw_scores)


def aggregate_review_bm25_scores(
    doc_place_ids: Sequence[str],
    raw_scores: Sequence[float],
    *,
    mode: str = 'max',
    top_n: int = 3,
) -> Dict[str, float]:
    """Gabung skor BM25 per-ulasan ke skor per toko."""
    by_shop: Dict[str, List[float]] = {}
    for pid, score in zip(doc_place_ids or [], raw_scores or []):
        key = str(pid or '').strip()
        if not key:
            continue
        by_shop.setdefault(key, []).append(float(score))

    out: Dict[str, float] = {}
    top_n = max(1, int(top_n))
    aggregate = (mode or 'max').strip().lower()
    for pid, scores in by_shop.items():
        ordered = sorted(scores, reverse=True)
        if aggregate in ('sum_top', 'sum', 'topn'):
            out[pid] = float(sum(ordered[:top_n]))
        else:
            out[pid] = ordered[0] if ordered else 0.0
    return out


def score_shops_bm25_review_level(
    profiles: Sequence[dict],
    query_tokens: Sequence[str],
    tokenize_fn: Callable[[str], List[str]],
    *,
    aggregate: str = 'max',
    top_n: int = 3,
    expansion_tokens: Optional[Sequence[str]] = None,
    expansion_weight: float = 0.5,
    expansion_by_review_id: Optional[Dict[int, str]] = None,
) -> Tuple[Dict[str, float], Dict[str, object]]:
    """
    BM25 per ulasan → agregasi ke skor toko (entity ranking).

    Default env ``COFIND_BM25_REVIEW_AGGREGATE=sum_top``: jumlah N ulasan teratas
    per toko. Mode ``max`` = skor ulasan tertinggi saja. Dense lane memakai max
    cosine (lihat hybrid_retrieval.score_shops_dense).

    Query expansion: skor(review) = BM25(query) + expansion_weight * BM25(expansion),
    sehingga sinonim/slang hasil LLM tidak mengalahkan token asli user.
    """
    all_pids = [
        str(p.get('place_id') or '').strip()
        for p in (profiles or [])
        if str(p.get('place_id') or '').strip()
    ]
    doc_pids, model, _ = build_bm25_review_index(
        profiles, tokenize_fn, expansion_by_review_id=expansion_by_review_id,
    )
    q = [t for t in (query_tokens or []) if t]
    q_set = set(q)
    exp = [t for t in dict.fromkeys(expansion_tokens or []) if t and t not in q_set]
    meta: Dict[str, object] = {
        'unit': 'review',
        'review_docs': len(doc_pids),
        'aggregate': aggregate,
        'top_n': top_n,
        'query_expansion_terms': len(exp),
        'doc_expansion_docs': len(expansion_by_review_id or {}),
    }
    if not model or not doc_pids:
        return {pid: 0.0 for pid in all_pids}, meta

    if not q:
        return {pid: 0.0 for pid in all_pids}, meta

    raw_list = _scores_as_list(model.get_scores(list(q)))
    weight = max(0.0, float(expansion_weight))
    if exp and weight > 0:
        exp_list = _scores_as_list(model.get_scores(exp))
        raw_list = [base + weight * extra for base, extra in zip(raw_list, exp_list)]
    agg = aggregate_review_bm25_scores(
        doc_pids, raw_list, mode=aggregate, top_n=top_n,
    )
    for pid in all_pids:
        agg.setdefault(pid, 0.0)
    return agg, meta


def score_shops_bm25(
    place_ids: Sequence[str],
    bm25_model,
    query_tokens: Sequence[str],
) -> Dict[str, float]:
    """Raw BM25 score per place_id. Kosong jika model/query tidak valid."""
    if not bm25_model or not place_ids:
        return {}
    q = [t for t in (query_tokens or []) if t]
    if not q:
        return {pid: 0.0 for pid in place_ids}
    raw_scores = bm25_model.get_scores(list(q))
    if hasattr(raw_scores, 'tolist'):
        raw_scores = raw_scores.tolist()
    out: Dict[str, float] = {}
    for idx, pid in enumerate(place_ids):
        try:
            out[pid] = float(raw_scores[idx])
        except Exception:
            out[pid] = 0.0
    return out


def normalize_bm25_scores(raw_by_place: Dict[str, float]) -> Dict[str, float]:
    """Min-max ke rentang 0..1 terhadap korpus saat ini."""
    if not raw_by_place:
        return {}
    values = list(raw_by_place.values())
    max_v = max(values) if values else 0.0
    min_v = min(values) if values else 0.0
    if max_v <= 0:
        return {pid: 0.0 for pid in raw_by_place}
    if abs(max_v - min_v) < 1e-12:
        # Semua skor sama & positif → 1.0 bila > 0
        return {pid: (1.0 if v > 0 else 0.0) for pid, v in raw_by_place.items()}
    span = max_v - min_v
    return {
        pid: max(0.0, min(1.0, (v - min_v) / span))
        for pid, v in raw_by_place.items()
    }
