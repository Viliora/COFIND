"""ABSA lokal (damasukma/indobert-absa) untuk sentimen klausa per aspek."""

from __future__ import annotations

import os
import threading
from typing import Dict, List, Optional, Sequence, Tuple

from logging_config import get_logger
from vector_cache import PersistentCache, digest_key

logger = get_logger('semantic')

_model = None
_tokenizer = None
_id2label: Dict[int, str] = {}
_model_error: Optional[str] = None
_lock = threading.Lock()
_cache = PersistentCache('absa_sentiment')

_ALLOWED = ('positif', 'negatif', 'netral')


def _env_flag(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or '').strip().lower()
    if not raw:
        return default
    return raw in ('1', 'true', 'yes', 'on')


def absa_enabled() -> bool:
    raw = (os.getenv('COFIND_ABSA_ENABLED') or '').strip()
    if raw:
        return _env_flag('COFIND_ABSA_ENABLED', True)
    return _env_flag('COFIND_LLM_CLAUSE_SENTIMENT', True)


def absa_model_name() -> str:
    return (os.getenv('COFIND_ABSA_MODEL') or 'damasukma/indobert-absa').strip()


def absa_batch_size() -> int:
    raw = (os.getenv('COFIND_ABSA_BATCH_SIZE') or '16').strip()
    try:
        return max(1, min(64, int(raw)))
    except ValueError:
        return 16


def absa_min_confidence() -> float:
    raw = (os.getenv('COFIND_ABSA_MIN_CONFIDENCE') or '0.35').strip()
    try:
        return max(0.1, min(0.95, float(raw)))
    except ValueError:
        return 0.35


def _map_label(label: str) -> str:
    text = str(label or '').strip().lower()
    if 'neg' in text or text in ('negative', 'negatif'):
        return 'negatif'
    if 'pos' in text or text in ('positive', 'positif'):
        return 'positif'
    if text in _ALLOWED:
        return text
    return 'netral'


def _load_model():
    global _model, _tokenizer, _id2label, _model_error
    if _model is not None or _model_error is not None:
        return _model
    with _lock:
        if _model is not None or _model_error is not None:
            return _model
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            name = absa_model_name()
            device = (os.getenv('COFIND_ABSA_DEVICE') or '').strip() or None
            _tokenizer = AutoTokenizer.from_pretrained(name)
            _model = AutoModelForSequenceClassification.from_pretrained(name)
            if device:
                _model = _model.to(device)
            elif torch.cuda.is_available():
                _model = _model.to('cuda')
            _model.eval()
            cfg = getattr(_model, 'config', None)
            raw_map = getattr(cfg, 'id2label', None) or {}
            _id2label = {int(k): str(v) for k, v in raw_map.items()}
        except Exception as err:
            _model_error = str(err)[:200]
            logger.warning('ABSA model tidak dimuat: %s', _model_error)
        return _model


def _format_input(clause: str, aspect: str) -> str:
    return f"{clause} [SEP] {aspect}"


def _cache_key(aspect: str, clause: str) -> str:
    return digest_key('absa-v1', absa_model_name(), aspect.lower(), clause.lower())


def predict_pairs(pairs: Sequence[Tuple[str, str]]) -> List[Tuple[str, float]]:
    """Return (sentiment, confidence) per pair (clause, aspect)."""
    if not pairs:
        return []
    model = _load_model()
    if model is None or _tokenizer is None:
        return [('netral', 0.0)] * len(pairs)
    import torch

    device = next(model.parameters()).device
    texts = [_format_input(c, a) for c, a in pairs]
    out: List[Tuple[str, float]] = []
    bs = absa_batch_size()
    with torch.no_grad():
        for offset in range(0, len(texts), bs):
            batch = texts[offset:offset + bs]
            enc = _tokenizer(batch, padding=True, truncation=True, max_length=256, return_tensors='pt')
            enc = {k: v.to(device) for k, v in enc.items()}
            logits = model(**enc).logits
            probs = torch.softmax(logits, dim=-1)
            for row in probs:
                conf, idx = torch.max(row, dim=0)
                label = _id2label.get(int(idx.item()), str(int(idx.item())))
                out.append((_map_label(label), float(conf.item())))
    return out


def aspects_from_preference_line(preference_line: str) -> List[str]:
    line = str(preference_line or '').strip()
    if not line:
        return ['preferensi umum']
    parts = [p.strip() for p in line.split(',') if p.strip()]
    return parts or [line]


def classify_clause_for_aspects(
    clause: str,
    aspects: Sequence[str],
) -> dict:
    """Satu verdict klausa: relevan jika ada aspek dengan sentimen bukan netral rendah."""
    aspects = [str(a).strip() for a in aspects if str(a).strip()]
    if not aspects:
        aspects = ['preferensi umum']
    min_conf = absa_min_confidence()
    best_relevant = None
    for aspect in aspects:
        key = _cache_key(aspect, clause)
        cached = _cache.get(key)
        if isinstance(cached, dict) and cached.get('sentimen'):
            sentiment = _map_label(str(cached.get('sentimen')))
            conf = float(cached.get('confidence') or 0.5)
        else:
            sentiment, conf = predict_pairs([(clause, aspect)])[0]
            _cache.set(key, {'relevan': True, 'sentimen': sentiment, 'confidence': conf})
        if conf < min_conf:
            continue
        if sentiment == 'negatif':
            return {'relevant': True, 'sentiment': 'negatif', 'source': 'absa', 'aspect': aspect}
        if sentiment == 'positif' and best_relevant is None:
            best_relevant = {'relevant': True, 'sentiment': 'positif', 'source': 'absa', 'aspect': aspect}
    if best_relevant:
        return best_relevant
    return {'relevant': False, 'sentiment': 'netral', 'source': 'absa'}


def classify_clauses_absa(
    clauses: Sequence[str],
    *,
    preference_line: str,
) -> Tuple[Dict[str, dict], Dict[str, object]]:
    """Verdict per klausa via ABSA (setelah triase)."""
    import time

    from clause_triage import apply_clause_triage

    telemetry: Dict[str, object] = {
        'clauses': len(clauses),
        'from_cache': 0,
        'from_absa': 0,
        'absa_batches': 0,
        'latency_ms': 0.0,
        'backend': 'absa',
    }
    verdicts: Dict[str, dict] = {}
    if not clauses:
        return verdicts, telemetry

    aspects = aspects_from_preference_line(preference_line)
    pending = list(dict.fromkeys(str(c).strip() for c in clauses if str(c).strip()))
    started = time.perf_counter()

    need_absa, triaged = apply_clause_triage(pending, preference_line, telemetry)
    verdicts.update(triaged)

    for clause in need_absa:
        ck = _cache_key(aspects[0], clause) if len(aspects) == 1 else None
        if ck:
            cached = _cache.get(ck)
            if isinstance(cached, dict) and cached.get('sentimen'):
                verdicts[clause] = {
                    'relevant': bool(cached.get('relevan', True)),
                    'sentiment': _map_label(str(cached.get('sentimen'))),
                    'source': 'cache',
                }
                telemetry['from_cache'] = int(telemetry['from_cache']) + 1
                continue
        verdicts[clause] = classify_clause_for_aspects(clause, aspects)
        telemetry['from_absa'] = int(telemetry['from_absa']) + 1

    telemetry['absa_batches'] = int(telemetry.get('from_absa') or 0)
    telemetry['latency_ms'] = round((time.perf_counter() - started) * 1000, 1)
    return verdicts, telemetry


def flush_cache() -> None:
    _cache.flush()


def cache_stats() -> Dict[str, int]:
    return _cache.stats()
