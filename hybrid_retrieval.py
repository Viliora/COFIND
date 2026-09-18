"""
Fase 2 — Hybrid Retrieval untuk rekomendasi Cofind.

Pencarian kandidat: BM25 (sparse, kata persis) + embedding (dense, makna),
lalu sedikit bobot kualitas toko (rating / Overall Experience).

PILL_MAPPING dipakai sebagai TEKS QUERY, bukan gerbang lolos/gugur:
  - BM25: label pill + review_keywords (nama fasilitas, istilah spesifik)
  - Dense: kalimat intent dari label pill ("cocok untuk kerja, wifi kencang")
Review yang memparafrase preferensi tetap bisa unggul lewat cosine similarity.
Metadata fasilitas (hanya pill lapis 2 yang user pilih) jadi prior lemah
(COFIND_METADATA_PRIOR_WEIGHT); kontradiksi ulasan memotong skor
(COFIND_METADATA_PENALTY_WEIGHT).

Env:
  COFIND_HYBRID_BM25_WEIGHT        default 0.45
  COFIND_HYBRID_DENSE_WEIGHT       default 0.45
  COFIND_HYBRID_QUALITY_WEIGHT     default 0.10
  COFIND_METADATA_GATE             default true
  COFIND_METADATA_PRIOR_WEIGHT     default 0.08
  COFIND_METADATA_PENALTY_WEIGHT   default 0.18
  COFIND_RETRIEVAL_TOP_K           default 7
  COFIND_DENSE_MAX_REVIEWS         ulasan per toko untuk max-pool dense (default: 20)
  COFIND_PROMPT_REVIEW_SCAN        ulasan yang di-scan saat pilih kutipan LLM (default: 60)
  COFIND_ACTIVITY_DENSE_MIN        ambang cosine cadangan gerbang aktivitas
                                   (default: 0.55). Toko lolos jika ada kata/frasa
                                   aktivitas ATAU act_dense >= ambang ini.
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
from metadata_prior import evaluate_metadata_gate, fuse_metadata_score, metadata_gate_enabled
from semantic_match import score_documents
from slang_normalize import normalize_text_with_slang, tokenize_normalized

logger = get_logger('recommend')

_TOKEN_RE = re.compile(r'[a-z0-9]+', re.IGNORECASE)
# Cukup untuk bukti pendek yang informatif ("wifi ok"), bukan sampah 1-2 huruf.
_MIN_REVIEW_CHARS = 6
_MIN_ACTIVITY_QUOTE_CHARS = 8
_LEXICAL_WEIGHT = 0.3
_DENSE_WEIGHT = 0.7
# Token generik yang tidak boleh jadi bukti aktivitas sendirian.
_GENERIC_ACTIVITY_STOP = frozenset({
    'cari', 'cocok', 'coffee', 'shop', 'kafe', 'cafe', 'tempat', 'enak',
})
_ACTIVITY_STOP_TOKENS_BY_PILL = {
    'bermain game': _GENERIC_ACTIVITY_STOP | frozenset({
        'nongkrong', 'main', 'bareng', 'gas', 'push', 'rank', 'bermain', 'mobile',
        'nge',  # pecahan nge-game; "nge-charge" / "ngecas" bukan bukti nge-game
    }),
    'kerja': _GENERIC_ACTIVITY_STOP | frozenset({'nongkrong', 'ngopi'}),
    'belajar': _GENERIC_ACTIVITY_STOP | frozenset({'nongkrong'}),
    'meeting_sosialisasi': _GENERIC_ACTIVITY_STOP | frozenset({'nongkrong', 'nongki'}),
    'keluarga': _GENERIC_ACTIVITY_STOP,
    'instagrammable': _GENERIC_ACTIVITY_STOP,
}
# Klausa bernada menolak tidak boleh jadi bukti lolos gerbang aktivitas.
# Penolakan "keluarga kurang disarankan" tidak boleh menenggelamkan "main game".
_REJECTION_PHRASES = (
    'tidak cocok',
    'kurang cocok',
    'tidak disarankan',
    'kurang disarankan',
    'bukan untuk',
    'ga cocok',
    'gak cocok',
    'nggak cocok',
    'enggak cocok',
    'tidak direkomendasikan',
    'kurang direkomendasikan',
    'tidak recommended',
    'kurang recommended',
    'bukan tempat yang cocok',
)
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+|[\n;]+')
_CLAUSE_SPLIT_RE = re.compile(
    r'(?<=[.!?])\s+|'
    r'[\n;]+|'
    r'(?:,|\s+)\s*(?:jika|kalau|namun|sedangkan)\s+',
    re.IGNORECASE,
)

# Frasa/istilah khas yang tidak boleh dipecah jadi token generik.
_ACTIVITY_EXTRA_PHRASES = {
    'bermain game': (
        'nge game', 'ngegame', 'main game', 'bermain game', 'main bareng game',
        'mobile legends', 'mobile legend', 'mlbb', 'valorant', 'pubg',
        'free fire', 'honor of kings', 'push rank', 'nge rank', 'ngerank',
        'mabar', 'ngemabar', 'gas game', 'turnamen', 'esport', 'e sport',
        'playstation', 'ps5', 'ps4', 'nintendo', 'steam deck',
        'main ml', 'main ff', 'main pubg', 'main valorant', 'main hok',
        'gamer', 'gaming', 'gamers',
    ),
    'kerja': (
        'work from cafe', 'wfc', 'kerja remote', 'ngantor', 'laptopan',
        'nugas kerja', 'kerjaan kantor', 'work from anywhere', 'meeting online',
        'kerja dari kafe', 'remote working',
    ),
    'belajar': (
        'belajar', 'nugas', 'ngerjain tugas', 'skripsi', 'baca buku',
        'fokus belajar', 'ruang belajar', 'tugas kuliah', 'mengerjakan tugas',
    ),
    'meeting_sosialisasi': (
        'meeting', 'rapat', 'buat rapat', 'untuk meeting', 'pertemuan bisnis',
        'kumpul tim', 'kumpul kerja', 'meeting kantor',
    ),
    'keluarga': (
        'ramah keluarga', 'ramah anak', 'bawa anak', 'family friendly',
        'kumpul keluarga', 'cocok keluarga', 'bawa anak kecil',
    ),
    'instagrammable': (
        'instagrammable', 'spot foto', 'photo spot', 'estetik', 'fotogenik',
        'banyak spot foto',
    ),
}
_ACTIVITY_WHOLE_WORDS = {
    'bermain game': frozenset({
        'game', 'games', 'gaming', 'gamer', 'gamers', 'ngegame', 'ngemabar',
        'mabar', 'mlbb', 'valorant', 'pubg', 'esport', 'esports',
        'playstation', 'turnamen', 'nintendo',
    }),
    'kerja': frozenset({
        'wfc', 'wfh', 'laptopan', 'ngantor', 'deadline', 'zoom', 'produktif',
    }),
    'belajar': frozenset({
        'belajar', 'nugas', 'skripsi', 'kuliah', 'ujian', 'tugas',
    }),
    'meeting_sosialisasi': frozenset({
        'meeting', 'rapat', 'diskusi', 'arisan', 'networking',
    }),
    'keluarga': frozenset({
        'keluarga', 'family', 'playground',
    }),
    'instagrammable': frozenset({
        'instagrammable', 'instagramable', 'fotogenik', 'estetik',
    }),
}
# Akronim pendek hanya dihitung bila ada konteks game di sekitarnya.
_ACTIVITY_SHORT_ACRONYMS = {
    'bermain game': frozenset({'ml', 'ff', 'hok', 'lol'}),
}
_ACRONYM_CONTEXT_TOKENS = frozenset({
    'main', 'mabar', 'game', 'gaming', 'gamer', 'legends', 'mobile', 'rank',
    'push', 'bareng', 'temen', 'teman', 'squad', 'slot', 'rank', 'ngerank',
})
_GAME_WORD_RE = re.compile(
    r'^(?:nge)?game(?:nya|an)?$|^gaming$|^gamers?$',
    re.IGNORECASE,
)


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
    return _env_float('COFIND_ACTIVITY_DENSE_MIN', 0.55, min_value=0.2, max_value=0.9)


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


def _gated_minmax(raw_by_place: Dict[str, float]) -> Dict[str, float]:
    """Minmax di antara toko yang lolos gerbang, tanpa menolkan sinyal yang kalah tipis."""
    norm = minmax_normalize(raw_by_place)
    out: Dict[str, float] = {}
    for pid, raw in (raw_by_place or {}).items():
        try:
            value = float(raw or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        mapped = float(norm.get(pid) or 0.0)
        if value > 0:
            out[pid] = 0.55 + 0.45 * mapped
        else:
            out[pid] = mapped
    return out


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
    if any(phrase in raw for phrase in _REJECTION_PHRASES):
        return True
    norm = normalize_text_with_slang(sentence)
    if not norm:
        return False
    return any(normalize_text_with_slang(phrase) in norm for phrase in _REJECTION_PHRASES)


def drop_rejection_sentences(text: str) -> str:
    """Buang klausa yang memuat frasa penolakan; klausa pendukung tetap dipakai."""
    kept = [part for part in iter_review_clauses(text) if not _sentence_has_rejection_phrase(part)]
    return ' '.join(kept)


def lexical_review_score(text: str, query_tokens: Sequence[str]) -> float:
    """Porsi token query yang muncul di ulasan (0..1), termasuk imbuhan ringan."""
    q = [t for t in (query_tokens or []) if t]
    if not q:
        return 0.0
    kept = drop_rejection_sentences(text)
    if not kept:
        return 0.0
    tokens = set(tokenize_for_match(kept))
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
    return re.sub(r'\s+', ' ', raw).strip()


def compile_activity_matcher(
    activity_pills: Sequence[str],
    *,
    pill_labels: Optional[Dict[str, str]] = None,
    pill_mapping: Optional[Dict[str, dict]] = None,
) -> Dict[str, object]:
    """
    Kompilasi gerbang aktivitas: frasa utuh + kata bermakna + akronim berkonteks.

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
        if len(parts) == 1 and (phrase in stops or (len(phrase) < 3 and phrase not in acronyms)):
            return
        seen_phrases.add(phrase)
        phrases.append(phrase)

    stops = set()
    acronyms = set()
    words: set = set()
    for pill in pills:
        stops |= _ACTIVITY_STOP_TOKENS_BY_PILL.get(pill, frozenset())
        acronyms |= _ACTIVITY_SHORT_ACRONYMS.get(pill, frozenset())
        words.update(_ACTIVITY_WHOLE_WORDS.get(pill, ()))

    for pill in pills:
        _add_phrase(labels.get(pill, pill))
        for kw in (mapping.get(pill) or {}).get('review_keywords') or []:
            _add_phrase(str(kw))
        for extra in _ACTIVITY_EXTRA_PHRASES.get(pill, ()):
            _add_phrase(extra)

    bm25_tokens: List[str] = []
    seen_tok = set()
    for phrase in phrases:
        for tok in tokenize_simple(phrase):
            if tok in stops or tok in seen_tok:
                continue
            if len(tok) < 3 and tok not in acronyms and tok not in words:
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
        'acronyms': frozenset(acronyms),
        'stop_tokens': frozenset(stops),
        'bm25_tokens': bm25_tokens,
    }


def activity_text_score(text: str, matcher: Optional[dict]) -> float:
    """
    Skor 0..1 seberapa jelas ulasan membahas aktivitas.
    1.0 = frasa khas / kata game utuh; 0.6 = akronim (ML) dengan konteks.
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
            allow_game_word and _GAME_WORD_RE.match(tok)
        ):
            best = max(best, 1.0)
            return 1.0

    acronyms = matcher.get('acronyms') or ()
    if acronyms:
        for idx, tok in enumerate(tokens):
            if tok not in acronyms:
                continue
            window = set(tokens[max(0, idx - 3): idx + 4])
            if window & _ACRONYM_CONTEXT_TOKENS or window & set(matcher.get('words') or ()):
                best = max(best, 0.6)
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
        if len(drop_rejection_sentences(text)) < min_chars:
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
    texts = [drop_rejection_sentences(review_text(row)) for row in pool]
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

    return build_query_tokens(pills, keywords, tokenize_fn=tokenize_for_match)


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
    """Kalimat intent + potongan definisi aktivitas (tanpa negative_scope)."""
    mapping = pill_mapping or {}
    chunks = []
    for pill in pills or []:
        if not pill:
            continue
        label = str(pill_labels.get(pill, pill) or pill).strip()
        spec = mapping.get(pill) or {}
        definition = _dense_definition_snippet(spec.get('definition') or '')
        if definition:
            chunks.append(f'{label}: {definition}')
        elif label:
            chunks.append(label)
    if not chunks:
        return ''
    return 'Cari coffee shop yang cocok untuk ' + ' '.join(chunks)


def score_shops_dense(
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
        for row in selected:
            kept = drop_rejection_sentences(review_text(row))
            if len(kept) < _MIN_REVIEW_CHARS:
                continue
            kept_docs.append(kept)
        if not kept_docs:
            reviews_per_shop[pid] = 0
            continue
        reviews_per_shop[pid] = len(kept_docs)
        for kept in kept_docs:
            owners.append(pid)
            documents.append(kept)

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
    """Buang token generik agar gerbang/kutipan aktivitas tidak tertipu 'nongkrong'/'nge'."""
    stops = set()
    acronyms = set()
    for pill in activity_pills or []:
        stops |= _ACTIVITY_STOP_TOKENS_BY_PILL.get(pill, frozenset())
        acronyms |= _ACTIVITY_SHORT_ACRONYMS.get(pill, frozenset())
    out = []
    seen = set()
    for tok in tokens or []:
        if not tok or tok in stops or tok in seen:
            continue
        if len(tok) < 3 and tok not in acronyms:
            continue
        seen.add(tok)
        out.append(tok)
    return out


def activity_phrases(
    activity_pills: Sequence[str],
    *,
    pill_labels: Dict[str, str],
    pill_mapping: Dict[str, dict],
) -> List[str]:
    """Frasa gerbang aktivitas; delegasi ke compile_activity_matcher."""
    matcher = compile_activity_matcher(
        activity_pills, pill_labels=pill_labels, pill_mapping=pill_mapping,
    )
    return list(matcher.get('phrases') or [])


def shop_has_activity_signal(
    reviews: Sequence[object],
    activity_tokens: Sequence[str],
    phrases: Optional[Sequence[str]] = None,
    activity_matcher: Optional[dict] = None,
) -> bool:
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
        kept = drop_rejection_sentences(review_text(row)).lower()
        if not kept:
            continue
        if any(p in kept for p in needles):
            return True
        norm = normalize_text_with_slang(kept)
        if any(np and np in norm for np in norm_needles):
            return True
    return False


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
    """Aktivitas ~80%, fasilitas tambahan ~14%, kualitas ~6% (dinormalisasi)."""
    parts = {
        'activity': 0.80,
        'attribute': 0.14 if has_attribute else 0.0,
        'quality': 0.06 if has_quality else 0.0,
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

    Toko masuk top-k jika matcher menemukan bukti aktivitas di ulasan
    (belajar, WFC, nge-game, meeting, keluarga, instagrammable). Fasilitas
    tambahan hanya penguat ranking, bukan syarat tampil.

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
        'activity_pass_lexical': 0,
        'activity_pass_dense_only': 0,
        'activity_rejected': 0,
        'activity_dense_min': activity_dense_min(),
        'metadata_prior_applied': 0,
        'metadata_penalized': 0,
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

    activity_bm25_raw: Dict[str, float] = {}
    attribute_bm25_raw: Dict[str, float] = {}
    try:
        place_ids, bm25_model, _corpus = build_bm25_index(
            profiles, tokenize_fn=tokenize_for_match,
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
        activity_matcher=activity_matcher if activity_list else None,
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
        act_lex = shop_activity_lexical_max(
            reviews, activity_tokens, activity_matcher=activity_matcher if activity_list else None,
        )
        act_hits = sum(
            1 for row in reviews
            if extract_activity_support_text(
                review_text(row), activity_matcher, activity_tokens,
            )
        ) if activity_list else 0
        act_bm25 = float(activity_bm25_raw.get(pid) or 0.0)
        act_dense = float(dense_raw.get(pid) or 0.0)
        if activity_list:
            # Bukti aktivitas: frasa/kata khas di ulasan mana pun.
            # "nge-charge" tidak dihitung; "main ML" / "mabar" dihitung.
            lex_ok = shop_has_activity_signal(
                reviews, activity_tokens, activity_phrase_list,
                activity_matcher=activity_matcher,
            )
            if not lex_ok:
                telemetry['activity_rejected'] = int(telemetry['activity_rejected']) + 1
                continue
            telemetry['activity_pass_lexical'] = int(telemetry['activity_pass_lexical']) + 1
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
            'act_lex': act_lex + 0.15 * min(act_hits, 3) / 3.0,
            'act_bm25_raw': act_bm25,
            'act_dense_raw': act_dense,
            'attr_bm25_raw': float(attribute_bm25_raw.get(pid) or 0.0),
            'quality_s': quality_s,
            'act_hits': act_hits,
        })

    telemetry['activity_gated'] = len(gated_rows)
    act_bm25_norm = _gated_minmax(
        {row['place_id']: row['act_bm25_raw'] for row in gated_rows}
    ) if gated_rows else {}
    act_dense_norm = _gated_minmax(
        {row['place_id']: row['act_dense_raw'] for row in gated_rows}
    ) if gated_rows else {}
    act_lex_norm = _gated_minmax(
        {row['place_id']: row['act_lex'] for row in gated_rows}
    ) if gated_rows else {}
    attr_bm25_norm = _gated_minmax(
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
        gate = evaluate_metadata_gate(
            row['profile'],
            pills,
            pill_mapping=pill_mapping,
            pill_labels=pill_labels,
            attribute_pills=attribute_list,
        ) if metadata_gate_enabled() else {
            'enabled': False,
            'claimed_pills': [],
            'claimed_fields': [],
            'matched_attribute_pills': [],
            'matched_attribute_labels': [],
            'prior': 0.0,
            'contradicted_pills': [],
            'contradiction': 0.0,
            'quotes': [],
        }
        fusion = fuse_metadata_score(total, gate, review_signal=act_combo)
        if fusion['prior_boost'] > 0:
            telemetry['metadata_prior_applied'] = int(telemetry['metadata_prior_applied']) + 1
        if fusion['penalty'] > 0:
            telemetry['metadata_penalized'] = int(telemetry['metadata_penalized']) + 1
        scored.append({
            'place_id': pid,
            'name': row['name'],
            'score': fusion['fused_score'],
            'profile': row['profile'],
            'metadata_gate': gate,
            'score_detail': {
                'bm25_raw': round(row['act_bm25_raw'], 4),
                'bm25_score': round(float(act_bm25_norm.get(pid) or 0.0), 4),
                'dense_raw': round(row['act_dense_raw'], 4),
                'dense_score': round(float(act_dense_norm.get(pid) or 0.0), 4),
                'activity_lex': round(row['act_lex'], 4),
                'activity_combo': round(act_combo, 4),
                'activity_hits': int(row.get('act_hits') or 0),
                'attribute_bm25': round(row['attr_bm25_raw'], 4),
                'quality_score': None if quality_s is None else round(quality_s, 4),
                'score_weights': weights,
                'retrieval_score': round(total, 4),
                'metadata_prior': gate.get('prior'),
                'metadata_prior_boost': fusion['prior_boost'],
                'metadata_contradiction': gate.get('contradiction'),
                'metadata_penalty': fusion['penalty'],
                'metadata_claimed_pills': list(gate.get('claimed_pills') or []),
                'metadata_matched_attribute_pills': list(gate.get('matched_attribute_pills') or []),
                'metadata_matched_attribute_labels': list(gate.get('matched_attribute_labels') or []),
                'metadata_contradicted_pills': list(gate.get('contradicted_pills') or []),
                'total_score': fusion['fused_score'],
                'covered_pills': [],
                'uncovered_pills': list(pills or []),
            },
        })

    scored.sort(key=lambda item: (
        -item['score'],
        -float((item.get('score_detail') or {}).get('attribute_bm25') or 0.0),
        -float((item.get('score_detail') or {}).get('activity_combo') or 0.0),
    ))
    telemetry['kept_with_signal'] = len(scored)
    telemetry['weights'] = _activity_attribute_weights(has_attr, True)
    return {
        'candidates': scored[:limit],
        'query_tokens': query_tokens,
        'query_text': query_text,
        'activity_tokens': activity_tokens,
        'attribute_tokens': attribute_tokens,
        'activity_query_text': activity_query_text,
        'activity_matcher': activity_matcher,
        'telemetry': telemetry,
    }
