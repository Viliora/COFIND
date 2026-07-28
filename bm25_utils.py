"""
BM25 scoring untuk rekomendasi berbasis review.

Setiap coffee shop = satu dokumen (gabungan teks review yang sudah dinormalisasi slang).
Query = token dari PILL_MAPPING + search_keywords.
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


def shop_document_text(reviews: Iterable[dict]) -> str:
    parts = []
    for review in reviews or []:
        text = (review.get('text') or '').strip()
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
