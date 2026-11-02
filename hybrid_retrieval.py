"""
Fase 2 — Hybrid Retrieval untuk rekomendasi Cofind.

Pencarian kandidat: BM25 (sparse) + embedding/ANN (dense) → Reciprocal Rank
Fusion (RRF). Bobot kualitas toko opsional (env, default off). Jalur pill menambahkan
gerbang aktivitas setelah RRF.

PILL_MAPPING dipakai sebagai TEKS QUERY, bukan gerbang lolos/gugur:
  - BM25: review_keywords (jangkar leksikal); label UI hanya fallback
  - Dense: dense_query per pill (gaya bahasa ulasan); fallback definition, lalu label
Review yang memparafrase preferensi tetap bisa unggul lewat cosine similarity.
Env (RRF aktif):
  COFIND_RRF_K / COFIND_RRF_POOL_SIZE — konstanta RRF dan lebar pool per daftar
  COFIND_RETRIEVAL_TOP_K           default 30 (potong ke MAX_REC setelah rerank)
  COFIND_BM25_UNIT                 review | shop (default: review)
  COFIND_BM25_REVIEW_AGGREGATE     max | sum_top (default: sum_top)
  COFIND_BM25_REVIEW_TOP_N         untuk sum_top (default: 3)
  COFIND_DENSE_MAX_REVIEWS         ulasan per toko untuk max-pool dense fallback (default: 20)
  COFIND_DENSE_USE_ANN             ANN pgvector scoped place_id (default: on if pgvector)
  COFIND_ANN_TOP_K                 review rows fetched by ANN (default: 300)
  COFIND_PROMPT_REVIEW_SCAN        ulasan yang di-scan saat pilih kutipan LLM (default: 60)
  COFIND_ACTIVITY_DENSE_MIN        admisi aktivitas cadangan (cosine dense) bila leksikal miss
                                   (default: 0.55). Hanya dipakai jika COFIND_ACTIVITY_GATE_MODE=hard.
  COFIND_ACTIVITY_GATE_MODE        hard | off | rrf_list (default: hard)
                                   hard = daftar RRF leksikon + filter lolos/gugur pasca-RRF
                                   rrf_list = daftar RRF leksikon saja (tanpa filter)
                                   off = BM25 + dense → RRF (tanpa daftar leksikon aktivitas)
  COFIND_LLM_MIN_FIT               fit_score minimum agar toko dipilih (default: 5.0)
  COFIND_REVIEW_ACTIVITY_INDEX     gunakan tabel review_activity_hits (default: true)
  COFIND_ACTIVITY_LEXICON_PATH     path JSON leksikon (default: data/lexicon/activity_lexicon.json)
  COFIND_RETRIEVAL_QUALITY_WEIGHT  blend RRF norm + quality (0..1, default: 0 = RRF murni)
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
    score_shops_bm25_review_level,
)
from logging_config import get_logger
from semantic_match import score_documents, score_reviews_by_id
from slang_normalize import normalize_text_with_slang, tokenize_normalized

from activity_lexicon import (
    ACTIVITY_PILL_KEYS,
    activity_stop_tokens_by_pill,
    activity_terms,
    game_word_re,
    hidden_gem_typo_re,
    rejection_phrases,
)

logger = get_logger('recommend')

_TOKEN_RE = re.compile(r'[a-z0-9]+', re.IGNORECASE)
# Cukup untuk bukti pendek yang informatif ("wifi ok"), bukan sampah 1-2 huruf.
_MIN_REVIEW_CHARS = 6
_MIN_ACTIVITY_QUOTE_CHARS = 8
_LEXICAL_WEIGHT = 0.3
_DENSE_WEIGHT = 0.7
# Leksikon aktivitas: data/lexicon/activity_lexicon.json (activity_lexicon.py).
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+|[\n;]+')
_CLAUSE_SPLIT_RE = re.compile(
    r'(?<=[.!?])\s+|'
    r'[\n;]+|'
    r'(?:,|\s+)\s*(?:jika|kalau|namun|sedangkan)\s+',
    re.IGNORECASE,
)


def _lexicon_terms(pill: str) -> Sequence[str]:
    return activity_terms(pill)


def _lexicon_stop_tokens(pill: str) -> frozenset:
    return activity_stop_tokens_by_pill().get(pill, frozenset())


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


def retrieval_top_k() -> int:
    return _env_int('COFIND_RETRIEVAL_TOP_K', 30, min_value=3, max_value=50)


def bm25_document_unit() -> str:
    raw = (os.getenv('COFIND_BM25_UNIT') or 'review').strip().lower()
    return 'shop' if raw == 'shop' else 'review'


def bm25_review_aggregate() -> str:
    raw = (os.getenv('COFIND_BM25_REVIEW_AGGREGATE') or 'sum_top').strip().lower()
    if raw in ('sum_top', 'sum', 'topn', 'top_n'):
        return 'sum_top'
    return 'max'


def bm25_review_top_n() -> int:
    return _env_int('COFIND_BM25_REVIEW_TOP_N', 3, min_value=1, max_value=10)


def retrieval_quality_blend_weight() -> float:
    """Bobot quality pada skor retrieval; 0 = RRF ternormalisasi saja (default)."""
    return _env_float(
        'COFIND_RETRIEVAL_QUALITY_WEIGHT',
        0.0,
        min_value=0.0,
        max_value=1.0,
    )


def dense_max_reviews() -> int:
    return _env_int('COFIND_DENSE_MAX_REVIEWS', 20, min_value=5, max_value=80)


def prompt_review_scan() -> int:
    return _env_int('COFIND_PROMPT_REVIEW_SCAN', 60, min_value=10, max_value=200)


def prompt_review_limit() -> int:
    return _env_int('COFIND_PROMPT_REVIEW_LIMIT', 8, min_value=3, max_value=20)


def activity_dense_min() -> float:
    return _env_float('COFIND_ACTIVITY_DENSE_MIN', 0.55, min_value=0.2, max_value=0.9)


def activity_gate_mode() -> str:
    """
    Mode gerbang aktivitas pill: hard | off | rrf_list.
    Alias env: rrf, rrf_only, soft → rrf_list; none/false/0 → off.
    """
    raw = (os.getenv('COFIND_ACTIVITY_GATE_MODE') or 'rrf_list').strip().lower()
    if raw in ('off', 'none', 'false', '0', 'no'):
        return 'off'
    if raw in ('rrf', 'rrf_list', 'rrf_only', 'soft', 'list'):
        return 'rrf_list'
    return 'hard'


def _resolve_activity_gate_mode(
    apply_activity_gate: bool,
    activity_gate_mode_param: Optional[str],
) -> str:
    if activity_gate_mode_param is not None:
        mode = str(activity_gate_mode_param).strip().lower()
        if mode in ('off', 'none', 'false', '0', 'no'):
            return 'off'
        if mode in ('rrf', 'rrf_list', 'rrf_only', 'soft', 'list'):
            return 'rrf_list'
        if mode in ('hard', 'on', 'true', '1', 'yes'):
            return 'hard'
    return 'hard' if apply_activity_gate else 'off'


def _env_flag(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or '').strip().lower()
    if not raw:
        return default
    return raw in ('1', 'true', 'yes', 'on')


def dense_use_ann_enabled() -> bool:
    from review_embedding_store import use_pgvector_store

    raw = (os.getenv('COFIND_DENSE_USE_ANN') or '').strip().lower()
    if raw in ('1', 'true', 'yes', 'on'):
        return True
    if raw in ('0', 'false', 'no', 'off'):
        return False
    return use_pgvector_store()


def ann_top_k() -> int:
    return _env_int('COFIND_ANN_TOP_K', 300, min_value=10, max_value=5000)


def min_fit_score() -> float:
    return _env_float('COFIND_LLM_MIN_FIT', 5.0, min_value=0.0, max_value=10.0)


def tokenize_simple(value: str) -> List[str]:
    """Token alnum lowercase, tanpa kamus slang / stemming."""
    return [t.lower() for t in _TOKEN_RE.findall(str(value or '')) if len(t) > 1]


def tokenize_for_match(value: str) -> List[str]:
    """Token setelah normalisasi slang umum + domain kafe."""
    tokens = tokenize_normalized(value)
    if tokens:
        return tokens
    return tokenize_simple(value)


def minmax_normalize(raw_by_place: Dict[str, float]) -> Dict[str, float]:
    return normalize_bm25_scores(raw_by_place)


def review_row_id(review: object):
    if isinstance(review, dict):
        rid = review.get("id")
        return int(rid) if rid is not None else None
    return None


def review_text(review: object) -> str:
    if isinstance(review, dict):
        return str(review.get('text') or review.get('review_text') or '').strip()
    return str(review or '').strip()


def iter_review_clauses(text: str) -> List[str]:
    """Pecah ulasan ke klausa agar caveat keluarga tidak menelan bukti nge-game."""
    raw = re.sub(r'\s+', ' ', str(text or '')).strip()
    if not raw:
        return []
    parts = [p.strip(' ,') for p in _CLAUSE_SPLIT_RE.split(raw) if p and p.strip(' ,')]
    return parts or [raw]


def _sentence_has_rejection_phrase(sentence: str) -> bool:
    raw = str(sentence or '').lower()
    if any(phrase in raw for phrase in rejection_phrases()):
        return True
    norm = normalize_text_with_slang(sentence)
    if not norm:
        return False
    return any(normalize_text_with_slang(phrase) in norm for phrase in rejection_phrases())


def lexical_review_score(text: str, query_tokens: Sequence[str]) -> float:
    """Porsi token query yang muncul di ulasan (0..1), termasuk imbuhan ringan."""
    q = [t for t in (query_tokens or []) if t]
    if not q:
        return 0.0
    if not str(text or '').strip():
        return 0.0
    tokens = set(tokenize_for_match(text))
    if not tokens:
        return 0.0
    unique_q = list(dict.fromkeys(q))

    def hit(query_tok: str) -> bool:
        if len(query_tok) < 3:
            return False
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


def _normalize_activity_text(text: str) -> str:
    """Lowercase + hyphen jadi spasi, tanpa kamus slang (mabar tidak boleh jadi 'main bareng')."""
    raw = str(text or '').lower().replace('-', ' ').replace('_', ' ')
    raw = hidden_gem_typo_re().sub('hidden gem', raw)
    return re.sub(r'\s+', ' ', raw).strip()


def compile_activity_matcher(
    activity_pills: Sequence[str],
    *,
    pill_labels: Optional[Dict[str, str]] = None,
    pill_mapping: Optional[Dict[str, dict]] = None,
) -> Dict[str, object]:
    """
    Kompilasi gerbang aktivitas dari terms leksikon (frasa + kata utuh).

    Token pendek hasil pecahan hyphen (nge dari nge-game) sengaja dibuang supaya
    'nge-charge laptop' tidak lolos sebagai bukti bermain game.
    """
    pills = [str(p or '').strip() for p in (activity_pills or []) if str(p or '').strip()]
    labels = pill_labels or {}
    mapping = pill_mapping or {}
    phrases: List[str] = []
    seen_phrases = set()

    def _add_phrase(raw: str):
        phrase = _normalize_activity_text(raw)
        if len(phrase) < 3:
            return
        if phrase in seen_phrases:
            return
        parts = phrase.split()
        if len(parts) == 1 and phrase in stops:
            return
        seen_phrases.add(phrase)
        phrases.append(phrase)

    stops = set()
    words: set = set()
    for pill in pills:
        stops |= _lexicon_stop_tokens(pill)
        for term in _lexicon_terms(pill):
            single = _normalize_activity_text(str(term))
            if single and ' ' not in single:
                words.add(single)

    for pill in pills:
        if pill in ACTIVITY_PILL_KEYS:
            term_sources = list(_lexicon_terms(pill))
        else:
            term_sources = [
                str(kw) for kw in ((mapping.get(pill) or {}).get('review_keywords') or [])
            ]
        if not term_sources:
            _add_phrase(labels.get(pill, pill))
        for raw in term_sources:
            _add_phrase(str(raw))

    bm25_tokens: List[str] = []
    seen_tok = set()
    for phrase in phrases:
        for tok in tokenize_simple(phrase):
            if tok in stops or tok in seen_tok:
                continue
            if len(tok) < 3 and tok not in words:
                continue
            seen_tok.add(tok)
            bm25_tokens.append(tok)
    for tok in sorted(words):
        if tok not in seen_tok and tok not in stops:
            seen_tok.add(tok)
            bm25_tokens.append(tok)

    return {
        'pills': pills,
        'phrases': phrases,
        'words': frozenset(words),
        'stop_tokens': frozenset(stops),
        'bm25_tokens': bm25_tokens,
    }


def activity_text_score(text: str, matcher: Optional[dict]) -> float:
    """
    Skor 0..1 seberapa jelas ulasan membahas aktivitas.
    1.0 = frasa khas atau kata jangkar utuh dari terms.
    """
    if not matcher or not text:
        return 0.0
    normalized = _normalize_activity_text(text)
    if not normalized:
        return 0.0
    tokens = tokenize_simple(normalized)
    token_set = set(tokens)

    best = 0.0
    for phrase in matcher.get('phrases') or []:
        if ' ' in phrase:
            if phrase in normalized:
                best = max(best, 1.0)
        elif phrase in token_set:
            best = max(best, 1.0)
        if best >= 1.0:
            return 1.0

    allow_game_word = 'bermain game' in set(matcher.get('pills') or ())
    for tok in tokens:
        if tok in (matcher.get('words') or ()) or (
            allow_game_word and game_word_re().match(tok)
        ):
            best = max(best, 1.0)
            return 1.0

    return best


def text_has_activity_signal(text: str, matcher: Optional[dict]) -> bool:
    return activity_text_score(text, matcher) > 0


def extract_activity_support_text(
    text: str,
    matcher: Optional[dict] = None,
    activity_tokens: Optional[Sequence[str]] = None,
) -> str:
    """
    Ambil klausa yang mendukung aktivitas yang diminta. Caveat pill lain
    di kalimat terpisah tidak menenggelamkan bukti itu.
    """
    kept = []
    for clause in iter_review_clauses(text):
        if _sentence_has_rejection_phrase(clause):
            continue
        if matcher and matcher.get('pills'):
            if not text_has_activity_signal(clause, matcher):
                continue
        elif activity_tokens:
            if lexical_review_score(clause, activity_tokens) <= 0:
                continue
        else:
            continue
        kept.append(clause)
    return ' '.join(kept).strip()


def text_rejects_requested_activity(
    text: str,
    matcher: Optional[dict] = None,
    activity_tokens: Optional[Sequence[str]] = None,
) -> bool:
    """True hanya jika klausa yang sama menyebut aktivitas dan menolaknya."""
    for clause in iter_review_clauses(text):
        if not _sentence_has_rejection_phrase(clause):
            continue
        if matcher and matcher.get('pills'):
            if text_has_activity_signal(clause, matcher):
                return True
        elif activity_tokens and lexical_review_score(clause, activity_tokens) > 0:
            return True
    return False


def empty_activity_matcher() -> Dict[str, object]:
    return compile_activity_matcher([])


def _usable_reviews(reviews: Sequence[object], *, min_chars: int = _MIN_REVIEW_CHARS) -> List[object]:
    out = []
    seen = set()
    for review in reviews or []:
        text = review_text(review)
        if len(text) < min_chars:
            continue
        key = re.sub(r'\s+', ' ', text).strip().lower()
        if not key or key in seen:
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
    activity_matcher: Optional[dict] = None,
) -> List[object]:
    """
    Pilih ulasan yang akan di-encode. Utamakan bukti aktivitas (frasa/kata khas),
    lalu overlap token query, lalu ulasan terbaru. Jangan berhenti saat overlap
    leksikal nol — ulasan bersinonim masih perlu sampai ke embedding.
    """
    usable = _usable_reviews(reviews)
    if len(usable) <= limit:
        return usable

    def rank_key(row: object) -> tuple:
        text = review_text(row)
        activity = activity_text_score(text, activity_matcher)
        primary = lexical_review_score(text, primary_tokens or [])
        full = lexical_review_score(text, query_tokens)
        return (activity, primary, full)

    ranked = sorted(usable, key=rank_key, reverse=True)
    return ranked[:limit]


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
    activity_matcher: Optional[dict] = None,
) -> List[object]:
    """
    Urutkan ulasan menurut relevansi. Ulasan yang benar-benar membahas aktivitas
    (nge-game, kerja, …) selalu di depan fasilitas tambahan, supaya kutipan
    'main ML' mengalahkan 'wifi lancar' / 'nge-charge laptop'.
    """
    take = limit if limit is not None else prompt_review_limit()
    scan = scan_limit if scan_limit is not None else prompt_review_scan()
    matcher = activity_matcher or empty_activity_matcher()
    activity_hits = [
        row for row in (reviews or [])
        if extract_activity_support_text(
            review_text(row), matcher, activity_tokens,
        )
        and len(review_text(row)) >= _MIN_ACTIVITY_QUOTE_CHARS
    ]
    usable = _usable_reviews(reviews)
    if not usable and not activity_hits:
        return []
    act_tokens = list(activity_tokens or matcher.get('bm25_tokens') or [])
    attr_tokens = list(attribute_tokens or [])
    pool = _select_reviews_for_embedding(
        usable or activity_hits,
        query_tokens,
        limit=scan,
        primary_tokens=act_tokens,
        activity_matcher=matcher if matcher.get('pills') else None,
    )
    # Jaminan: semua ulasan berbukti aktivitas ikut dinilai, tidak terpotong kuota scan.
    seen_ids = {id(row) for row in pool}
    for row in activity_hits:
        if id(row) not in seen_ids:
            pool.append(row)
            seen_ids.add(id(row))
    texts = [review_text(row) for row in pool]
    review_items = [(review_row_id(row), review_text(row)) for row in pool]
    full_cosines, telemetry = score_reviews_by_id(query_text, review_items)
    if telemetry.get('skipped'):
        logger.debug(f"rank_reviews_for_query dense dilewati: {telemetry.get('skipped')}")
        full_cosines = [0.0] * len(pool)
    act_cosines = full_cosines
    if activity_query_text and activity_query_text != query_text:
        act_cosines, act_tel = score_reviews_by_id(activity_query_text, review_items)
        if act_tel.get('skipped'):
            act_cosines = full_cosines

    scored = []
    for idx, row in enumerate(pool):
        text = texts[idx]
        act_hit = activity_text_score(text, matcher) if matcher.get('pills') else 0.0
        act_lex = act_hit if act_hit else (
            lexical_review_score(text, act_tokens) if act_tokens else 0.0
        )
        attr_lex = lexical_review_score(text, attr_tokens) if attr_tokens else 0.0
        full_lex = lexical_review_score(text, query_tokens)
        act_dense = max(0.0, float(act_cosines[idx]) if idx < len(act_cosines) else 0.0)
        full_dense = max(0.0, float(full_cosines[idx]) if idx < len(full_cosines) else 0.0)
        if matcher.get('pills'):
            combined = (
                0.45 * act_dense
                + 0.30 * act_lex
                + 0.15 * full_dense
                + 0.10 * attr_lex
            )
            if act_hit > 0:
                combined += 0.45
        else:
            combined = _DENSE_WEIGHT * full_dense + _LEXICAL_WEIGHT * full_lex
        scored.append((combined, act_lex, act_dense, row))
    scored.sort(key=lambda item: (-item[0], -item[1], -item[2]))
    ordered = [row for _, _, _, row in scored]
    if activity_hits:
        hit_ids = {id(row) for row in activity_hits}
        guaranteed = [row for row in ordered if id(row) in hit_ids]
        filler = [row for row in ordered if id(row) not in hit_ids]
        return (guaranteed + filler)[: max(take, len(guaranteed))]
    return ordered[:take]


def sparse_tokens_from_keywords(keywords: Sequence[str]) -> List[str]:
    """
    Token sparse dari keyword free text (frasa LLM / mock eval).
    Pakai tokenize_for_match yang sama dengan korpus ulasan BM25 (slang, colokan→stopkontak, wfc→work from cafe).
    """
    phrases = [str(k).strip() for k in (keywords or []) if str(k or '').strip()]
    if not phrases:
        return []
    return build_query_tokens(
        [], lambda _pill: [], search_keywords=phrases, tokenize_fn=tokenize_for_match,
    )


def build_sparse_query_tokens(
    pills: Sequence[str],
    *,
    pill_labels: Dict[str, str],
    pill_mapping: Dict[str, dict],
) -> List[str]:
    """
    Token BM25 dari review_keywords (query, bukan filter).

    Key pill dan label UI tidak ikut: "Ada musholla" / "Menu Lengkap (Makanan & Minuman)"
    menghasilkan token umum (ada, menu) yang cocok ke hampir semua ulasan.
    Label hanya dipakai bila pill belum punya review_keywords.
    """
    phrases: List[str] = []
    for pill in pills or []:
        keywords = list((pill_mapping.get(pill) or {}).get('review_keywords') or [])
        phrases.extend(keywords or [pill_labels.get(pill, pill)])
    return build_query_tokens(
        [], lambda _pill: [], search_keywords=phrases, tokenize_fn=tokenize_for_match,
    )


_DENSE_DEFINITION_CHARS = 180


def _dense_definition_snippet(text: str, limit: int = _DENSE_DEFINITION_CHARS) -> str:
    """Ambil kalimat pertama definisi, dipotong agar embedding tidak stuffed."""
    cleaned = re.sub(r'\s+', ' ', str(text or '')).strip()
    if not cleaned:
        return ''
    sentence = re.split(r'(?<=[.!?])\s+', cleaned, maxsplit=1)[0].strip()
    if len(sentence) > limit:
        sentence = sentence[: max(0, limit - 1)].rstrip() + '…'
    return sentence


def build_dense_query_text(
    pills: Sequence[str],
    *,
    pill_labels: Dict[str, str],
    pill_mapping: Optional[Dict[str, dict]] = None,
) -> str:
    """
    Teks dense per pill: dense_query, fallback potongan definition, lalu label.

    Tanpa awalan bersama ("Cari coffee shop yang cocok untuk ..."): awalan itu
    mendominasi vektor sehingga query antar-atribut nyaris identik (cosine ~0.91).
    negative_scope tidak pernah masuk dense.
    """
    mapping = pill_mapping or {}
    chunks = []
    for pill in pills or []:
        if not pill:
            continue
        spec = mapping.get(pill) or {}
        text = str(spec.get('dense_query') or '').strip()
        if not text:
            text = _dense_definition_snippet(spec.get('definition') or '')
        if not text:
            text = str(pill_labels.get(pill, pill) or pill).strip()
        if text:
            chunks.append(text)
    return '. '.join(chunks)


def _score_shops_dense_maxpool(
    profiles: Sequence[dict],
    query_text: str,
    *,
    query_tokens: Optional[Sequence[str]] = None,
    primary_tokens: Optional[Sequence[str]] = None,
    activity_matcher: Optional[dict] = None,
) -> Tuple[Dict[str, float], Dict[str, object]]:
    """
    Skor dense per toko = cosine tertinggi di antara ulasannya (max-pool).
    Paling banyak `dense_max_reviews` ulasan per toko yang di-encode.
    `primary_tokens` (biasanya token aktivitas) diutamakan saat memilih ulasan.
    """
    cap = dense_max_reviews()
    owners: List[str] = []
    documents: List[str] = []
    owner_review_ids: List[Optional[int]] = []
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
            activity_matcher=activity_matcher,
        )
        if not selected:
            reviews_per_shop[pid] = 0
            continue
        kept_docs = []
        kept_ids: List[Optional[int]] = []
        for row in selected:
            kept = review_text(row)
            if len(kept) < _MIN_REVIEW_CHARS:
                continue
            kept_docs.append(kept)
            kept_ids.append(review_row_id(row))
        if not kept_docs:
            reviews_per_shop[pid] = 0
            continue
        reviews_per_shop[pid] = len(kept_docs)
        for kept, rid in zip(kept_docs, kept_ids):
            owners.append(pid)
            documents.append(kept)
            owner_review_ids.append(rid)

    telemetry: Dict[str, object] = {
        'shops': len(reviews_per_shop),
        'reviews_embedded': len(documents),
        'max_reviews_per_shop': cap,
        'pool': 'max',
    }
    if not documents:
        telemetry['skipped'] = 'no_reviews'
        return {pid: 0.0 for pid in reviews_per_shop}, telemetry

    review_items = [
        (owner_review_ids[i], documents[i]) for i in range(len(documents))
    ]
    raw_list, doc_telemetry = score_reviews_by_id(query_text, review_items)
    telemetry.update(doc_telemetry)

    best: Dict[str, float] = {pid: 0.0 for pid in reviews_per_shop}
    for idx, pid in enumerate(owners):
        score = float(raw_list[idx]) if idx < len(raw_list) else 0.0
        if score > best.get(pid, 0.0):
            best[pid] = score
    return best, telemetry


def _score_shops_dense_ann(
    profiles: Sequence[dict],
    query_text: str,
) -> Tuple[Dict[str, float], Dict[str, object]]:
    from review_embedding_store import ann_search_reviews
    from semantic_match import embed_query_vector

    place_ids: List[str] = []
    for profile in profiles or []:
        pid = str(profile.get('place_id') or '').strip()
        if pid:
            place_ids.append(pid)
    best: Dict[str, float] = {pid: 0.0 for pid in place_ids}
    telemetry: Dict[str, object] = {
        'pool': 'ann',
        'store': 'pgvector',
        'shops': len(best),
        'ann_top_k': ann_top_k(),
        'reviews_embedded': 0,
        'ann_reviews': 0,
    }
    if not place_ids or not (query_text or '').strip():
        telemetry['skipped'] = 'no_input'
        return best, telemetry
    q, _ = embed_query_vector(query_text)
    if q is None:
        telemetry['skipped'] = 'query_encode_failed'
        return best, telemetry
    rows, ann_tel = ann_search_reviews(q, place_ids, limit=ann_top_k())
    telemetry['ann_ms'] = ann_tel.get('ann_ms')
    if ann_tel.get('error'):
        telemetry['ann_error'] = ann_tel.get('error')
    for row in rows:
        pid = str(row.get('place_id') or '')
        sim = float(row.get('similarity') or 0.0)
        if pid and sim > best.get(pid, 0.0):
            best[pid] = sim
    n_rows = int(ann_tel.get('rows_returned') or len(rows))
    telemetry['reviews_embedded'] = n_rows
    telemetry['ann_reviews'] = n_rows
    return best, telemetry


def score_shops_dense(
    profiles: Sequence[dict],
    query_text: str,
    *,
    query_tokens: Optional[Sequence[str]] = None,
    primary_tokens: Optional[Sequence[str]] = None,
    activity_matcher: Optional[dict] = None,
) -> Tuple[Dict[str, float], Dict[str, object]]:
    """Dense per toko: ANN pgvector (scoped) bila aktif, else max-pool legacy."""
    if dense_use_ann_enabled():
        ann_best, ann_telemetry = _score_shops_dense_ann(profiles, query_text)
        ann_error = ann_telemetry.get('ann_error')
        ann_reviews = int(ann_telemetry.get('ann_reviews') or 0)
        if not ann_error and ann_reviews > 0:
            return ann_best, ann_telemetry
        ann_telemetry['fallback'] = 'maxpool'
        logger.debug(
            "ANN dense fallback ke max-pool: error=%s ann_reviews=%s",
            ann_error,
            ann_reviews,
        )
    return _score_shops_dense_maxpool(
        profiles,
        query_text,
        query_tokens=query_tokens,
        primary_tokens=primary_tokens,
        activity_matcher=activity_matcher,
    )


def activity_signal_tokens(
    tokens: Sequence[str],
    activity_pills: Optional[Sequence[str]] = None,
) -> List[str]:
    """Buang token generik agar gerbang/kutipan aktivitas tidak tertipu 'nongkrong'/'nge'."""
    stops = set()
    words: set = set()
    for pill in activity_pills or []:
        stops |= _lexicon_stop_tokens(pill)
        for term in _lexicon_terms(pill):
            single = _normalize_activity_text(str(term))
            if single and ' ' not in single:
                words.add(single)
    out = []
    seen = set()
    for tok in tokens or []:
        if not tok or tok in stops or tok in seen:
            continue
        if len(tok) < 3 and tok not in words:
            continue
        seen.add(tok)
        out.append(tok)
    return out


def shop_has_activity_signal(
    reviews: Sequence[object],
    activity_tokens: Sequence[str],
    phrases: Optional[Sequence[str]] = None,
    activity_matcher: Optional[dict] = None,
    *,
    place_id: Optional[str] = None,
) -> bool:
    if place_id and activity_matcher:
        try:
            from review_activity_index import place_has_activity_pills

            pills = list(activity_matcher.get("pills") or [])
            if pills and place_has_activity_pills(str(place_id), pills):
                return True
        except Exception:
            pass
    matcher = activity_matcher
    if matcher:
        for row in reviews or []:
            if extract_activity_support_text(review_text(row), matcher, activity_tokens):
                return True
        return False
    if shop_activity_lexical_max(reviews, activity_tokens, activity_matcher=None) > 0:
        return True
    needles = [p for p in (phrases or []) if p]
    if not needles:
        return False
    norm_needles = [normalize_text_with_slang(p) for p in needles]
    for row in reviews or []:
        raw = review_text(row)
        if not raw:
            continue
        lowered = raw.lower()
        if any(p in lowered for p in needles):
            return True
        norm = normalize_text_with_slang(raw)
        if any(np and np in norm for np in norm_needles):
            return True
    return False


def shop_passes_activity_gate(
    reviews: Sequence[object],
    activity_tokens: Sequence[str],
    phrases: Optional[Sequence[str]] = None,
    activity_matcher: Optional[dict] = None,
    *,
    dense_activity_score: float = 0.0,
    place_id: Optional[str] = None,
) -> tuple:
    """
    Gerbang admisi aktivitas: hanya bukti leksikal/frasa (shop_has_activity_signal).

    Return (passed, pass_mode):
      - 'lexical' = sinyal leksikal/indeks ulasan.
      - 'dense' = cosine dense >= COFIND_ACTIVITY_DENSE_MIN (cadangan admisi).
      - '' = ditolak.
    """
    if shop_has_activity_signal(
        reviews,
        activity_tokens,
        phrases,
        activity_matcher=activity_matcher,
        place_id=place_id,
    ):
        return True, 'lexical'
    try:
        dense_score = float(dense_activity_score or 0.0)
    except (TypeError, ValueError):
        dense_score = 0.0
    if dense_score >= activity_dense_min():
        return True, 'dense'
    return False, ''


def shop_activity_lexical_max(
    reviews: Sequence[object],
    activity_tokens: Sequence[str],
    activity_matcher: Optional[dict] = None,
) -> float:
    """Skor leksikal aktivitas tertinggi di seluruh ulasan toko (tanpa embedding)."""
    best = 0.0
    for row in reviews or []:
        text = review_text(row)
        if activity_matcher:
            best = max(best, activity_text_score(text, activity_matcher))
        else:
            best = max(best, lexical_review_score(text, activity_tokens))
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
    activity_pills: Optional[Sequence[str]] = None,
) -> Tuple[List[str], List[str]]:
    """Pill yang disebut di kumpulan teks vs yang belum."""
    covered = []
    uncovered = []
    activity_set = set(activity_pills or [])
    for pill in pills or []:
        if pill in activity_set:
            matcher = compile_activity_matcher(
                [pill], pill_labels=pill_labels, pill_mapping=pill_mapping,
            )
            hit = any(text_has_activity_signal(str(text or ''), matcher) for text in texts)
        else:
            tokens = build_sparse_query_tokens(
                [pill], pill_labels=pill_labels, pill_mapping=pill_mapping,
            )
            hit = any(text_matches_tokens(str(text or ''), tokens) for text in texts)
        if hit:
            covered.append(pill)
        else:
            uncovered.append(pill)
    return covered, uncovered


def blend_rrf_norm_with_quality(
    rrf_score: float,
    max_rrf: float,
    quality_raw=None,
    *,
    quality_weight: Optional[float] = None,
) -> tuple:
    """
    Normalisasi skor RRF mentah; blend opsional dengan skor kualitas toko.
    Default: RRF murni (COFIND_RETRIEVAL_QUALITY_WEIGHT=0).
    """
    rrf_norm = (rrf_score / max_rrf) if max_rrf > 0 else 0.0
    weight = retrieval_quality_blend_weight() if quality_weight is None else float(quality_weight)
    weight = max(0.0, min(1.0, weight))
    try:
        quality_s = None if quality_raw is None else float(quality_raw)
    except (TypeError, ValueError):
        quality_s = None
    if quality_s is None or weight <= 0.0:
        return rrf_norm, rrf_norm, None
    total = (1.0 - weight) * rrf_norm + weight * quality_s
    return rrf_norm, total, quality_s


def rrf_k_constant() -> int:
    return _env_int('COFIND_RRF_K', 60, min_value=1, max_value=1000)


def rrf_pool_size() -> int:
    return _env_int('COFIND_RRF_POOL_SIZE', 50, min_value=5, max_value=500)


def score_bm25_for_hybrid_retrieval(
    profiles: Sequence[dict],
    query_tokens: Sequence[str],
    *,
    expansion_tokens: Optional[Sequence[str]] = None,
) -> Tuple[Dict[str, float], Dict[str, object]]:
    """
    Skor BM25 sparse untuk Fase 2: default per-ulasan + agregasi ke toko.
    Postgres FTS hanya dipakai bila COFIND_BM25_UNIT=shop.

    `expansion_tokens` (query expansion LLM) dan document expansion
    (COFIND_DOC_EXPANSION) hanya berlaku untuk BM25 memory per-ulasan.
    """
    meta: Dict[str, object] = {}
    clean_tokens = [str(t).strip() for t in (query_tokens or []) if str(t or '').strip()]
    clean_expansion = [str(t).strip() for t in (expansion_tokens or []) if str(t or '').strip()]
    place_ids = [
        str(p.get('place_id') or '').strip()
        for p in (profiles or [])
        if str(p.get('place_id') or '').strip()
    ]
    meta['bm25_shops'] = len(place_ids)
    meta['bm25_unit'] = bm25_document_unit()
    if not clean_tokens:
        return {pid: 0.0 for pid in place_ids}, meta

    unit = bm25_document_unit()
    from postgres_fts import postgres_fts_enabled, score_shops_fts

    if unit == 'review' or not postgres_fts_enabled():
        if unit == 'review' and postgres_fts_enabled():
            meta['bm25_postgres_skipped'] = (
                'postgres FTS shop-level; pakai memory per-ulasan'
            )
        from query_expansion import query_expansion_weight
        from review_expansion_store import doc_expansion_enabled

        doc_expansions: Dict[int, str] = {}
        if doc_expansion_enabled():
            try:
                import review_expansion_store

                doc_expansions = review_expansion_store.doc_expansions_for_profiles(profiles)
            except Exception as err:
                logger.warning(f"Document expansion gagal dimuat: {str(err)[:160]}")
                meta['doc_expansion_error'] = str(err)[:200]
        bm25_raw, bm25_meta = score_shops_bm25_review_level(
            profiles,
            clean_tokens,
            tokenize_for_match,
            aggregate=bm25_review_aggregate(),
            top_n=bm25_review_top_n(),
            expansion_tokens=clean_expansion,
            expansion_weight=query_expansion_weight(),
            expansion_by_review_id=doc_expansions,
        )
        meta['bm25_backend'] = 'memory_review'
        meta['bm25_review'] = bm25_meta
        return bm25_raw, meta

    if clean_expansion:
        meta['bm25_query_expansion_skipped'] = 'postgres FTS shop-level'
    meta['bm25_backend'] = 'postgres'
    return score_shops_fts(place_ids, clean_tokens), meta


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[str]],
    *,
    k: Optional[int] = None,
) -> Dict[str, float]:
    """
    RRF: RRFscore(d) = sum_r 1/(k + rank_r(d)).
    `ranked_lists` = daftar peringkat terpisah (mis. BM25 sparse vs dense/ANN).
    """
    k_value = k if k is not None else rrf_k_constant()
    scores: Dict[str, float] = {}
    for ranked in ranked_lists or []:
        for rank, doc_id in enumerate(ranked or [], start=1):
            key = str(doc_id or '').strip()
            if not key:
                continue
            scores[key] = scores.get(key, 0.0) + 1.0 / (k_value + rank)
    return dict(sorted(scores.items(), key=lambda kv: -kv[1]))


def _rrf_ranked_place_ids(
    raw_scores: Dict[str, float],
    profiles_by_pid: Dict[str, dict],
    pool_size: int,
) -> List[str]:
    ranked = sorted(
        (pid for pid in profiles_by_pid if float(raw_scores.get(pid) or 0.0) > 1e-9),
        key=lambda pid: -float(raw_scores.get(pid) or 0.0),
    )
    return ranked[:pool_size]


def _hybrid_retrieve_rrf_core(
    profiles: Sequence[dict],
    *,
    bm25_tokens: Sequence[str],
    dense_query_text: str,
    quality_by_place: Optional[Dict[str, Optional[float]]] = None,
    top_k: Optional[int] = None,
    dense_query_tokens: Optional[Sequence[str]] = None,
    dense_primary_tokens: Optional[Sequence[str]] = None,
    activity_matcher: Optional[dict] = None,
    query_tokens_out: Sequence[str],
    query_text_out: str,
    activity_tokens_out: Sequence[str],
    attribute_tokens_out: Sequence[str],
    activity_query_text_out: str,
    activity_matcher_out: dict,
    telemetry: Dict[str, object],
    pills: Optional[Sequence[str]] = None,
    pill_labels: Optional[Dict[str, str]] = None,
    pill_mapping: Optional[Dict[str, dict]] = None,
    attribute_pills: Optional[Sequence[str]] = None,
    activity_pills: Optional[Sequence[str]] = None,
    activity_tokens_for_gate: Optional[Sequence[str]] = None,
    activity_phrase_list: Optional[Sequence[str]] = None,
    apply_activity_gate: bool = False,
    activity_gate_mode_param: Optional[str] = None,
    bm25_expansion_tokens: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    """
    Hybrid retrieval standar: BM25 + dense/ANN → dua daftar peringkat → RRF.
    Opsional: daftar RRF leksikon aktivitas dan/atau filter hard pasca-RRF (pill).
    `bm25_expansion_tokens` = query expansion (bobot lebih rendah, BM25 saja).
    """
    limit = top_k if top_k is not None else retrieval_top_k()
    quality_by_place = quality_by_place or {}
    clean_tokens = [str(t).strip() for t in (bm25_tokens or []) if str(t or '').strip()]
    dense_text = str(dense_query_text or '').strip()
    pool_size = rrf_pool_size()
    gate_mode = _resolve_activity_gate_mode(apply_activity_gate, activity_gate_mode_param)
    activity_list = list(activity_pills or [])
    use_activity_rrf = gate_mode != 'off' and bool(activity_list)
    apply_hard_gate = gate_mode == 'hard' and bool(activity_list)
    telemetry.setdefault('mode', 'hybrid_rrf')
    telemetry.setdefault('rrf_k', rrf_k_constant())
    telemetry.setdefault('rrf_pool_size', pool_size)
    telemetry['activity_gate_mode'] = gate_mode
    if use_activity_rrf or apply_hard_gate:
        telemetry.setdefault('activity_pass_lexical', 0)
        telemetry.setdefault('activity_pass_dense_only', 0)
        telemetry.setdefault('activity_rejected', 0)
        telemetry['activity_dense_min'] = activity_dense_min()

    bm25_raw: Dict[str, float] = {}
    try:
        expansion = list(bm25_expansion_tokens or [])
        telemetry['bm25_query_expansion'] = expansion
        if expansion:
            bm25_raw, bm25_meta = score_bm25_for_hybrid_retrieval(
                profiles, clean_tokens, expansion_tokens=expansion,
            )
        else:
            bm25_raw, bm25_meta = score_bm25_for_hybrid_retrieval(profiles, clean_tokens)
        telemetry.update(bm25_meta)
    except Exception as err:
        logger.warning(f"BM25 retrieval gagal: {err}")
        telemetry['bm25_error'] = str(err)[:200]

    dense_q_tokens = list(dense_query_tokens or clean_tokens)
    dense_primary = list(dense_primary_tokens or dense_q_tokens)
    dense_raw, dense_telemetry = score_shops_dense(
        profiles,
        dense_text,
        query_tokens=dense_q_tokens,
        primary_tokens=dense_primary,
        activity_matcher=activity_matcher if use_activity_rrf else None,
    )
    telemetry['dense'] = dense_telemetry

    profiles_by_pid: Dict[str, dict] = {}
    for profile in profiles or []:
        pid = str(profile.get('place_id') or '').strip()
        if pid:
            profiles_by_pid[pid] = profile

    act_tokens_gate = list(activity_tokens_for_gate or [])
    act_phrases = list(activity_phrase_list or [])
    act_matcher = activity_matcher if use_activity_rrf else None

    bm25_rank_list = _rrf_ranked_place_ids(bm25_raw, profiles_by_pid, pool_size)
    dense_rank_list = _rrf_ranked_place_ids(dense_raw, profiles_by_pid, pool_size)
    telemetry['bm25_matched'] = len(bm25_rank_list)
    telemetry['dense_matched'] = len(dense_rank_list)

    rank_lists: List[Sequence[str]] = [bm25_rank_list, dense_rank_list]
    if use_activity_rrf and act_matcher:
        lex_scores: Dict[str, float] = {}
        for pid, profile in profiles_by_pid.items():
            reviews = profile.get('reviews') or []
            if not shop_has_activity_signal(
                reviews,
                act_tokens_gate,
                act_phrases,
                activity_matcher=act_matcher,
                place_id=pid,
            ):
                continue
            lex_scores[pid] = shop_activity_lexical_max(
                reviews, act_tokens_gate, activity_matcher=act_matcher,
            )
        lex_rank_list = sorted(lex_scores, key=lambda p: -lex_scores[p])[:pool_size]
        telemetry['activity_lex_matched'] = len(lex_rank_list)
        if lex_rank_list:
            rank_lists.append(lex_rank_list)

    rrf_scores = reciprocal_rank_fusion(rank_lists)
    telemetry['rrf_candidates'] = len(rrf_scores)

    pill_list = list(pills or [])
    attr_list = list(attribute_pills or [])

    # RRF mentah ~1/(k+rank) ≈ 0.016–0.033; dinormalisasi ke rrf_norm. Blend quality
    # hanya jika COFIND_RETRIEVAL_QUALITY_WEIGHT > 0 (default: RRF murni).
    max_rrf = max(rrf_scores.values(), default=0.0)

    scored = []
    for pid, rrf_score in rrf_scores.items():
        profile = profiles_by_pid.get(pid)
        if not profile:
            continue
        reviews = profile.get('reviews') or []
        rrf_norm, total, quality_s = blend_rrf_norm_with_quality(
            rrf_score,
            max_rrf,
            quality_by_place.get(pid),
        )

        if apply_hard_gate:
            passed, pass_mode = shop_passes_activity_gate(
                reviews,
                act_tokens_gate,
                act_phrases,
                act_matcher,
                dense_activity_score=float(dense_raw.get(pid) or 0.0),
                place_id=pid,
            )
            if pass_mode == 'dense':
                telemetry['activity_pass_dense'] = int(
                    telemetry.get('activity_pass_dense') or 0,
                ) + 1
                telemetry['activity_pass_dense_only'] = int(
                    telemetry.get('activity_pass_dense_only') or 0,
                ) + 1
            if not passed:
                telemetry['activity_rejected'] = int(telemetry.get('activity_rejected') or 0) + 1
                continue
            if pass_mode == 'lexical':
                telemetry['activity_pass_lexical'] = int(
                    telemetry.get('activity_pass_lexical') or 0,
                ) + 1

        scored.append({
            'place_id': pid,
            'name': profile.get('name') or '',
            'score': round(total, 6),
            'profile': profile,
            'score_detail': {
                'bm25_raw': round(float(bm25_raw.get(pid) or 0.0), 4),
                'bm25_score': round(float(bm25_raw.get(pid) or 0.0), 4),
                'dense_raw': round(float(dense_raw.get(pid) or 0.0), 4),
                'dense_score': round(float(dense_raw.get(pid) or 0.0), 4),
                'rrf_score': round(rrf_score, 6),
                'rrf_norm': round(rrf_norm, 4),
                'activity_combo': round(rrf_norm, 4),
                'attribute_bm25': 0.0,
                'quality_score': None if quality_s is None else round(quality_s, 4),
                'retrieval_score': round(total, 4),
                'total_score': round(total, 4),
                'covered_pills': [],
                'uncovered_pills': list(pill_list),
                'activity_pills': list(activity_pills or []),
                'attribute_pills': list(attr_list),
            },
        })

    scored.sort(key=lambda item: (
        -item['score'],
        -float((item.get('score_detail') or {}).get('rrf_score') or 0.0),
    ))
    telemetry['kept_with_signal'] = len(scored)
    if use_activity_rrf or apply_hard_gate:
        telemetry['activity_gated'] = len(scored)

    return {
        'candidates': scored[:limit],
        'query_tokens': list(query_tokens_out),
        'query_text': query_text_out,
        'activity_tokens': list(activity_tokens_out),
        'attribute_tokens': list(attribute_tokens_out),
        'activity_query_text': activity_query_text_out,
        'activity_matcher': activity_matcher_out,
        'telemetry': telemetry,
    }


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
    Hybrid retrieval pill: BM25 + dense/ANN → RRF, lalu gerbang aktivitas
    (jika ada pill aktivitas) dan metadata gate fasilitas.

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
        'activity_gate_on': activity_gate_mode() != 'off' and bool(activity_list),
        'activity_gate_mode': activity_gate_mode(),
        'activity_pass_lexical': 0,
        'activity_pass_dense_only': 0,
        'activity_rejected': 0,
        'activity_dense_min': activity_dense_min(),
    }

    query_tokens = build_sparse_query_tokens(
        pills, pill_labels=pill_labels, pill_mapping=pill_mapping,
    )
    activity_matcher = compile_activity_matcher(
        activity_list, pill_labels=pill_labels, pill_mapping=pill_mapping,
    ) if activity_list else empty_activity_matcher()
    activity_tokens = list(activity_matcher.get('bm25_tokens') or [])
    if not activity_tokens:
        activity_tokens = activity_signal_tokens(
            build_sparse_query_tokens(
                activity_list, pill_labels=pill_labels, pill_mapping=pill_mapping,
            ) if activity_list else [],
            activity_list,
        )
    activity_phrase_list = list(activity_matcher.get('phrases') or [])
    attribute_tokens = build_sparse_query_tokens(
        attribute_list, pill_labels=pill_labels, pill_mapping=pill_mapping,
    ) if attribute_list else []
    query_text = build_dense_query_text(
        pills, pill_labels=pill_labels, pill_mapping=pill_mapping,
    )
    activity_query_text = (
        build_dense_query_text(
            activity_list, pill_labels=pill_labels, pill_mapping=pill_mapping,
        )
        if activity_list else query_text
    )
    telemetry['query_tokens'] = len(query_tokens)
    telemetry['activity_tokens'] = len(activity_tokens)
    telemetry['dense_query'] = activity_query_text

    # BM25 untuk RRF: utamakan token aktivitas agar frasa khas (mabar, ML) masuk
    # daftar peringkat sparse; query_tokens penuh tetap dipakai untuk dense.
    bm25_tokens = activity_tokens if activity_list else (query_tokens or activity_tokens)
    from query_expansion import pill_query_expansion_tokens

    bm25_expansion = pill_query_expansion_tokens(
        activity_list or list(pills or []), original_tokens=bm25_tokens,
    )
    return _hybrid_retrieve_rrf_core(
        profiles,
        bm25_tokens=bm25_tokens,
        dense_query_text=activity_query_text,
        quality_by_place=quality_by_place,
        top_k=limit,
        dense_query_tokens=query_tokens,
        dense_primary_tokens=activity_tokens or query_tokens,
        activity_matcher=activity_matcher if activity_list else None,
        query_tokens_out=query_tokens,
        query_text_out=query_text,
        activity_tokens_out=activity_tokens,
        attribute_tokens_out=attribute_tokens,
        activity_query_text_out=activity_query_text,
        activity_matcher_out=activity_matcher,
        telemetry=telemetry,
        pills=list(pills or []),
        pill_labels=pill_labels,
        pill_mapping=pill_mapping,
        attribute_pills=attribute_list,
        activity_pills=activity_list,
        activity_tokens_for_gate=activity_tokens,
        activity_phrase_list=activity_phrase_list,
        apply_activity_gate=bool(activity_list),
        activity_gate_mode_param=activity_gate_mode(),
        bm25_expansion_tokens=bm25_expansion,
    )


# --------------------------------------------------------------------------
# Retrieval free text (keyword hasil ekstraksi LLM) — RRF, tanpa pill
# --------------------------------------------------------------------------
#
# Dipakai saat user mengisi kotak kata kunci bebas (bukan memilih pill).
# Tidak ada gerbang aktivitas / metadata-prior berbasis pill di sini —
# BM25 dan dense search dijalankan independen atas seluruh korpus review,
# masing-masing menghasilkan daftar peringkat (top-N place_id), lalu
# digabung dengan Reciprocal Rank Fusion (RRF) jadi satu ranking akhir.
#
# Kontrak return SENGAJA identik dengan retrieve_top_k() (key: candidates,
# query_tokens, query_text, activity_tokens, attribute_tokens,
# activity_query_text, activity_matcher, telemetry) supaya pemanggil
# (app.py) bisa memperlakukan hasil jalur ini sama seperti jalur pill —
# evidence building, LLM rerank, grounding, dan summary tidak perlu cabang
# kode baru.


def retrieve_top_k_by_text(
    profiles: Sequence[dict],
    *,
    query_tokens: Sequence[str],
    dense_query_text: str,
    quality_by_place: Optional[Dict[str, Optional[float]]] = None,
    top_k: Optional[int] = None,
    expansion_tokens: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    """
    Free text (setelah intent LLM): BM25 + dense/ANN → RRF.
    Tanpa gerbang aktivitas/metadata pill — rerank LLM yang memfilter bukti.
    `expansion_tokens` = sinonim/slang hasil intent LLM (sudah disanitasi).
    """
    limit = top_k if top_k is not None else retrieval_top_k()
    quality_by_place = quality_by_place or {}
    raw_keywords = [str(t).strip() for t in (query_tokens or []) if str(t or '').strip()]
    clean_tokens = sparse_tokens_from_keywords(raw_keywords)
    dense_text = str(dense_query_text or '').strip()
    empty_matcher = empty_activity_matcher()

    telemetry: Dict[str, object] = {
        'mode': 'free_text_rrf',
        'profiles': len(profiles or []),
        'top_k': limit,
        'bm25_shops': 0,
        'dense': {},
        'query_keywords_raw': raw_keywords,
        'query_tokens': len(clean_tokens),
    }

    return _hybrid_retrieve_rrf_core(
        profiles,
        bm25_tokens=clean_tokens,
        dense_query_text=dense_text,
        quality_by_place=quality_by_place,
        top_k=limit,
        dense_query_tokens=clean_tokens,
        dense_primary_tokens=clean_tokens,
        activity_matcher=None,
        query_tokens_out=clean_tokens,
        query_text_out=dense_text,
        activity_tokens_out=clean_tokens,
        attribute_tokens_out=[],
        activity_query_text_out=dense_text,
        activity_matcher_out=empty_matcher,
        telemetry=telemetry,
        apply_activity_gate=False,
        bm25_expansion_tokens=expansion_tokens,
    )

