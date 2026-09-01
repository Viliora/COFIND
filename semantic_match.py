"""
Gerbang makna (semantic gate) untuk pipeline rekomendasi Cofind.

Masalah yang diselesaikan: pencocokan kata kunci (exact/stem) hanya menangkap
kata yang persis ada di `PILL_MAPPING`. Ulasan bersifat subjektif, sehingga
"wifinya ngebut" atau "koneksinya kenceng" bisa lolos padahal maksudnya sama
dengan pill "wifi kencang".

Modul ini menambahkan jaring kedua: kalimat/klausa yang GAGAL pencocokan kata
dibandingkan maknanya dengan frasa acuan pill memakai sentence embedding
(cosine similarity). Perannya hanya penyaring murah — keputusan sentimen tetap
diserahkan ke LLM (lihat llm_clause_sentiment.py).

Vektor yang sudah dihitung disimpan di vector_cache (memori → Redis → file),
jadi review yang sama tidak pernah di-encode dua kali.

Env:
  COFIND_SEMANTIC_GATE             aktifkan gerbang makna (default: true)
  COFIND_EMBEDDING_MODEL           model sentence-transformers
                                   (default: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
  COFIND_SEMANTIC_THRESHOLD        ambang cosine similarity 0..1 (default: 0.55)
  COFIND_SEMANTIC_MAX_CLAUSES      batas klausa yang di-encode per toko (default: 80)
  COFIND_SEMANTIC_BATCH_SIZE       batch encode (default: 32)
  COFIND_SEMANTIC_SCORE_CAP        batas kontribusi sinyal semantik ke skor (default: 0.6)
  COFIND_EMBEDDING_DEVICE          paksa device torch, mis. "cpu" (default: auto)
"""

from __future__ import annotations

import contextvars
import os
import re
import threading
import time
from typing import Dict, List, Optional, Sequence, Tuple

from logging_config import get_logger
from vector_cache import PersistentCache, decode_vector, digest_key, encode_vector

DEFAULT_MODEL = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'

logger = get_logger('semantic')

_MIN_CLAUSE_TOKENS = 2
_MAX_CLAUSE_CHARS = 320
# Pemisahan pada koma hanya untuk potongan yang cukup panjang; frasa pendek
# seperti "adem, nyaman" justru lebih jelas bila dibiarkan utuh.
_COMMA_SPLIT_MIN_TOKENS = 4

_SENTENCE_SPLIT_RE = re.compile(r'[.!?;\n\r]+|\u2026')
_CONTRAST_SPLIT_RE = re.compile(
    r'\s+(?:tapi|tetapi|namun|namun demikian|walaupun|walau|meskipun|meski|'
    r'sedangkan|sayangnya|padahal|cuma|kecuali|hanya saja|tp)\s+',
    re.IGNORECASE,
)
_COMMA_SPLIT_RE = re.compile(r'\s*,\s*')

_cache = PersistentCache('semantic_embeddings')
_model = None
_model_error: Optional[str] = None
_model_lock = threading.Lock()
_encode_lock = threading.Lock()
_reference_cache: Dict[str, object] = {}
_reference_lock = threading.Lock()


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


def semantic_gate_enabled() -> bool:
    return _env_flag('COFIND_SEMANTIC_GATE', True)


def model_name() -> str:
    return (os.getenv('COFIND_EMBEDDING_MODEL') or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def similarity_threshold() -> float:
    # Default 0,55 berasal dari kalibrasi tests/smoke/smoke_threshold.py (16 klausa
    # berlabel): presisi 1,00 dan recall 0,88. Klausa topikal yang lolos berada di
    # 0,61-0,83, klausa tidak relevan tertinggi 0,35. Recall belum 1,00 karena
    # klausa implisit seperti "sinyal susah masuk di lantai dua" hanya 0,33.
    # Tabel presisi/recall per ambang: docs/kalibrasi-parameter.md.
    return _env_float('COFIND_SEMANTIC_THRESHOLD', 0.55, min_value=0.1, max_value=0.95)


def max_clauses_per_shop() -> int:
    return _env_int('COFIND_SEMANTIC_MAX_CLAUSES', 80, min_value=5, max_value=1000)


def encode_batch_size() -> int:
    return _env_int('COFIND_SEMANTIC_BATCH_SIZE', 32, min_value=1, max_value=256)


def semantic_score_cap() -> float:
    return _env_float('COFIND_SEMANTIC_SCORE_CAP', 0.6, min_value=0.0, max_value=1.0)


def encode_budget_per_request() -> int:
    """Batas klausa BARU yang boleh di-encode dalam satu request (0 = tanpa batas)."""
    return _env_int('COFIND_SEMANTIC_ENCODE_BUDGET', 1500, min_value=0, max_value=1_000_000)


# Budget encode per request hanya dipotong oleh klausa baru; klausa dari cache
# tidak menghabiskan budget.
_encode_budget_var = contextvars.ContextVar('cofind_semantic_encode_budget', default=None)


def begin_encode_budget(limit: Optional[int] = None):
    """Mulai budget encode untuk satu request; return token untuk reset."""
    value = encode_budget_per_request() if limit is None else int(limit)
    return _encode_budget_var.set({'remaining': value if value > 0 else None, 'encoded': 0, 'throttled': 0})


def reset_encode_budget(token) -> None:
    if token is None:
        return
    try:
        _encode_budget_var.reset(token)
    except ValueError:
        _encode_budget_var.set(None)


def encode_budget_state() -> Dict[str, object]:
    state = _encode_budget_var.get()
    return dict(state) if isinstance(state, dict) else {}


def _take_encode_budget(requested: int) -> int:
    state = _encode_budget_var.get()
    if not isinstance(state, dict):
        return requested
    remaining = state.get('remaining')
    if remaining is None:
        state['encoded'] = int(state.get('encoded') or 0) + requested
        return requested
    allowed = max(0, min(int(remaining), requested))
    state['remaining'] = int(remaining) - allowed
    state['encoded'] = int(state.get('encoded') or 0) + allowed
    if allowed < requested:
        state['throttled'] = int(state.get('throttled') or 0) + (requested - allowed)
    return allowed


def gate_config() -> Dict[str, object]:
    return {
        'enabled': semantic_gate_enabled(),
        'model': model_name(),
        'threshold': similarity_threshold(),
        'max_clauses_per_shop': max_clauses_per_shop(),
        'score_cap': semantic_score_cap(),
        'encode_budget': encode_budget_per_request(),
        'model_loaded': _model is not None,
        'model_error': _model_error,
    }


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------

def load_model():
    """
    Muat SentenceTransformer sekali per proses. Return None (tanpa raise) bila
    library/model tidak tersedia, supaya pipeline tetap jalan tanpa gerbang makna.
    """
    global _model, _model_error
    if _model is not None or _model_error is not None:
        return _model
    with _model_lock:
        if _model is not None or _model_error is not None:
            return _model
        started = time.perf_counter()
        try:
            from sentence_transformers import SentenceTransformer

            kwargs = {}
            device = (os.getenv('COFIND_EMBEDDING_DEVICE') or '').strip()
            if device:
                kwargs['device'] = device
            _model = SentenceTransformer(model_name(), **kwargs)
            logger.info(
                f"Model siap: {model_name()} "
                f"({round((time.perf_counter() - started) * 1000)}ms)"
            )
        except Exception as err:
            _model_error = str(err)[:200]
            _model = None
            logger.warning(f"Model tidak tersedia: {_model_error}")
        return _model


def model_available() -> bool:
    return semantic_gate_enabled() and load_model() is not None


# --------------------------------------------------------------------------
# Pemecahan klausa
# --------------------------------------------------------------------------

def _clean_clause(value: str) -> str:
    cleaned = re.sub(r'\s+', ' ', str(value or '')).strip(' \t-–—•·"\',:;.')
    if len(cleaned) > _MAX_CLAUSE_CHARS:
        cleaned = cleaned[:_MAX_CLAUSE_CHARS].rstrip()
    return cleaned


def _token_count(value: str) -> int:
    return len([t for t in str(value or '').split() if t])


def split_clauses(text: object, *, limit: Optional[int] = None) -> List[str]:
    """
    Pecah teks review menjadi klausa yang dinilai terpisah.

    Tiga tingkat pemisah: tanda baca kuat, konjungsi kontras ("tapi", "namun", ...),
    lalu koma untuk potongan yang masih panjang. Hasilnya kalimat bernada campur
    seperti "kursinya bagus tapi ngga nyaman, wifinya bagus" dinilai per klausa.
    """
    raw = re.sub(r'\s+', ' ', str(text or '')).strip()
    if not raw:
        return []

    clauses: List[str] = []
    seen = set()

    def push(candidate: str) -> None:
        cleaned = _clean_clause(candidate)
        if _token_count(cleaned) < _MIN_CLAUSE_TOKENS:
            return
        key = cleaned.lower()
        if key in seen:
            return
        seen.add(key)
        clauses.append(cleaned)

    for sentence in _SENTENCE_SPLIT_RE.split(raw):
        sentence = _clean_clause(sentence)
        if not sentence:
            continue
        for part in _CONTRAST_SPLIT_RE.split(sentence):
            part = _clean_clause(part)
            if not part:
                continue
            if ',' in part and _token_count(part) >= _COMMA_SPLIT_MIN_TOKENS:
                for chunk in _COMMA_SPLIT_RE.split(part):
                    push(chunk)
            else:
                push(part)

    if limit is not None and limit > 0:
        return clauses[:limit]
    return clauses


# --------------------------------------------------------------------------
# Embedding + cache
# --------------------------------------------------------------------------

def _cache_key(text: str) -> str:
    return digest_key(model_name(), 'v1', text.lower())


def embed_texts(texts: Sequence[str]) -> Dict[str, object]:
    """
    Vektor ter-normalisasi (cosine = dot product) per teks unik.
    Teks yang sudah pernah dihitung diambil dari cache, sisanya di-encode batch.
    """
    unique: List[str] = []
    seen = set()
    for text in texts or []:
        cleaned = _clean_clause(text)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(cleaned)
    if not unique:
        return {}

    model = load_model()
    if model is None:
        return {}

    import numpy as np

    vectors: Dict[str, object] = {}
    cache_keys = {text: _cache_key(text) for text in unique}
    cached = _cache.get_many(cache_keys.values())
    missing: List[str] = []
    for text in unique:
        payload = cached.get(cache_keys[text])
        vector = decode_vector(payload) if payload is not None else None
        if vector is None or getattr(vector, 'size', 0) == 0:
            missing.append(text)
        else:
            vectors[text] = vector

    if missing:
        # Klausa dari cache selalu dipakai; hanya encoding baru yang dibatasi budget.
        allowed = _take_encode_budget(len(missing))
        missing = missing[:allowed]
    if missing:
        batch = encode_batch_size()
        # Encoding diserialisasi agar dua request paralel tidak berebut CPU.
        with _encode_lock:
            encoded = model.encode(
                missing,
                batch_size=batch,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        to_store = {}
        for text, vector in zip(missing, np.asarray(encoded)):
            vec = np.asarray(vector, dtype=np.float32)
            vectors[text] = vec
            to_store[cache_keys[text]] = encode_vector(vec)
        _cache.set_many(to_store)

    return vectors


def reference_embeddings(terms: Sequence[str]):
    """Matriks vektor frasa acuan pill (dihitung sekali per kombinasi frasa)."""
    cleaned = []
    seen = set()
    for term in terms or []:
        text = _clean_clause(term)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    if not cleaned:
        return [], None

    signature = digest_key(model_name(), '|'.join(sorted(t.lower() for t in cleaned)))
    with _reference_lock:
        hit = _reference_cache.get(signature)
    if hit is not None:
        return hit  # type: ignore[return-value]

    import numpy as np

    # Frasa acuan pendek (1-3 kata) tidak perlu dipecah klausa.
    vectors = embed_texts(cleaned)
    kept = [t for t in cleaned if t in vectors]
    if not kept:
        return [], None
    matrix = np.vstack([np.asarray(vectors[t], dtype=np.float32) for t in kept])
    result = (kept, matrix)
    with _reference_lock:
        _reference_cache[signature] = result
    return result


def similarity_matrix(clause_matrix, reference_matrix):
    """
    Cosine similarity antar dua matriks vektor ter-normalisasi.
    Memakai model.similarity() bila tersedia (sentence-transformers >= 3),
    fallback ke dot product numpy.
    """
    import numpy as np

    model = load_model()
    if model is not None and hasattr(model, 'similarity'):
        try:
            scores = model.similarity(clause_matrix, reference_matrix)
            return np.asarray(getattr(scores, 'cpu', lambda: scores)(), dtype=np.float32)
        except Exception as err:
            logger.debug(f"model.similarity gagal, pakai dot product numpy: {str(err)[:120]}")
    return np.asarray(clause_matrix, dtype=np.float32) @ np.asarray(reference_matrix, dtype=np.float32).T


def score_documents(query_text: str, documents: Sequence[str]) -> Tuple[List[float], Dict[str, object]]:
    """
    Cosine similarity query vs tiap dokumen (vektor ter-normalisasi).
    Dipakai Hybrid Retrieval: satu vektor per ulasan, lalu max-pool per toko.
    Dokumen yang gagal di-encode mendapat skor 0.
    """
    telemetry: Dict[str, object] = {
        'documents': len(documents or []),
        'encoded': 0,
        'skipped': None,
    }
    if not query_text or not documents:
        telemetry['skipped'] = 'no_input'
        return [0.0] * len(documents or []), telemetry
    if not model_available():
        telemetry['skipped'] = 'model_unavailable'
        return [0.0] * len(documents), telemetry

    import numpy as np

    cleaned_docs = [_clean_clause(doc) for doc in documents]
    vectors = embed_texts([query_text, *[d for d in cleaned_docs if d]])
    query_key = _clean_clause(query_text)
    query_vec = vectors.get(query_key)
    if query_vec is None:
        telemetry['skipped'] = 'query_encode_failed'
        return [0.0] * len(documents), telemetry

    q = np.asarray(query_vec, dtype=np.float32)
    scores: List[float] = []
    encoded = 0
    for doc in cleaned_docs:
        vec = vectors.get(doc) if doc else None
        if vec is None:
            scores.append(0.0)
            continue
        encoded += 1
        scores.append(float(np.dot(q, np.asarray(vec, dtype=np.float32))))
    telemetry['encoded'] = encoded
    return scores, telemetry


# --------------------------------------------------------------------------
# Gerbang makna per review
# --------------------------------------------------------------------------

def match_reviews(
    reviews: Sequence[dict],
    reference_terms: Sequence[str],
    *,
    threshold: Optional[float] = None,
    max_clauses: Optional[int] = None,
) -> Tuple[Dict[int, dict], Dict[str, object]]:
    """
    Cari review yang maknanya dekat dengan frasa acuan meski tidak memuat katanya.

    Return (matches, telemetry):
      matches: index review -> {'score', 'clause', 'term'} untuk yang lolos ambang
      telemetry: ringkasan jumlah klausa/hit untuk logging
    """
    telemetry: Dict[str, object] = {
        'reviews': len(reviews or []),
        'clauses': 0,
        'matched_reviews': 0,
        'best_score': 0.0,
        'skipped': None,
    }
    if not reviews or not reference_terms:
        telemetry['skipped'] = 'no_input'
        return {}, telemetry
    if not model_available():
        telemetry['skipped'] = 'model_unavailable'
        return {}, telemetry

    limit = max_clauses if max_clauses is not None else max_clauses_per_shop()
    gate = threshold if threshold is not None else similarity_threshold()

    clause_owner: List[int] = []
    clause_texts: List[str] = []
    for idx, review in enumerate(reviews):
        if limit and len(clause_texts) >= limit:
            break
        text = review.get('text') if isinstance(review, dict) else review
        for clause in split_clauses(text):
            if limit and len(clause_texts) >= limit:
                break
            clause_texts.append(clause)
            clause_owner.append(idx)

    telemetry['clauses'] = len(clause_texts)
    if not clause_texts:
        telemetry['skipped'] = 'no_clauses'
        return {}, telemetry

    terms, reference_matrix = reference_embeddings(reference_terms)
    if reference_matrix is None:
        telemetry['skipped'] = 'no_reference'
        return {}, telemetry

    clause_vectors = embed_texts(clause_texts)
    usable = [(owner, text) for owner, text in zip(clause_owner, clause_texts) if text in clause_vectors]
    if not usable:
        telemetry['skipped'] = 'encode_failed'
        return {}, telemetry

    import numpy as np

    clause_matrix = np.vstack([np.asarray(clause_vectors[text], dtype=np.float32) for _, text in usable])
    scores = similarity_matrix(clause_matrix, reference_matrix)
    if scores.ndim == 1:
        scores = scores.reshape(len(usable), -1)

    matches: Dict[int, dict] = {}
    best_overall = 0.0
    for row_idx, (owner, text) in enumerate(usable):
        row = scores[row_idx]
        best_col = int(np.argmax(row))
        best_score = float(row[best_col])
        best_overall = max(best_overall, best_score)
        if best_score < gate:
            continue
        current = matches.get(owner)
        if current is not None and current['score'] >= best_score:
            continue
        matches[owner] = {
            'score': round(best_score, 4),
            'clause': text,
            'term': terms[best_col] if best_col < len(terms) else '',
        }

    telemetry['matched_reviews'] = len(matches)
    telemetry['best_score'] = round(best_overall, 4)
    # Rata-rata skor review yang lolos, dipakai pemanggil sebagai tingkat keyakinan.
    telemetry['mean_score'] = (
        round(sum(item['score'] for item in matches.values()) / len(matches), 4) if matches else 0.0
    )
    return matches, telemetry


def flush_cache() -> None:
    """Simpan lapis file cache (dipanggil di akhir pipeline / batch job)."""
    _cache.flush()


def cache_stats() -> Dict[str, int]:
    return _cache.stats()
