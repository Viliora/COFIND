"""
Telemetri pipeline rekomendasi: konfigurasi terpadu, run id, snapshot degradasi,
log JSON terstruktur, dan persistensi ringkas untuk dashboard admin.
"""

from __future__ import annotations

import contextvars
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from logging_config import get_logger

logger = get_logger('metric')

_llm_usage_bucket: contextvars.ContextVar[Optional[List[Dict[str, Any]]]] = contextvars.ContextVar(
    'cofind_llm_usage_bucket',
    default=None,
)

_TABLE_READY = False


def new_pipeline_run_id() -> str:
    return uuid.uuid4().hex


def begin_llm_usage_collection() -> contextvars.Token:
    return _llm_usage_bucket.set([])


def reset_llm_usage_collection(token: contextvars.Token) -> None:
    try:
        _llm_usage_bucket.reset(token)
    except ValueError:
        _llm_usage_bucket.set(None)


def push_llm_usage(
    *,
    stage: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    model: Optional[str] = None,
) -> None:
    bucket = _llm_usage_bucket.get()
    if bucket is None:
        return
    if total_tokens <= 0:
        total_tokens = int(prompt_tokens or 0) + int(completion_tokens or 0)
    bucket.append({
        'stage': str(stage or 'llm'),
        'prompt_tokens': int(prompt_tokens or 0),
        'completion_tokens': int(completion_tokens or 0),
        'total_tokens': int(total_tokens or 0),
        'model': (model or '').strip() or None,
    })


def summarize_llm_usage(entries: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    rows = entries if entries is not None else (_llm_usage_bucket.get() or [])
    prompt = sum(int(r.get('prompt_tokens') or 0) for r in rows)
    completion = sum(int(r.get('completion_tokens') or 0) for r in rows)
    total = sum(int(r.get('total_tokens') or 0) for r in rows)
    if total <= 0:
        total = prompt + completion
    by_stage: Dict[str, Dict[str, int]] = {}
    for row in rows:
        stage = str(row.get('stage') or 'llm')
        slot = by_stage.setdefault(stage, {'calls': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0})
        slot['calls'] += 1
        slot['prompt_tokens'] += int(row.get('prompt_tokens') or 0)
        slot['completion_tokens'] += int(row.get('completion_tokens') or 0)
        slot['total_tokens'] += int(row.get('total_tokens') or 0)
    return {
        'calls': len(rows),
        'prompt_tokens': prompt,
        'completion_tokens': completion,
        'total_tokens': total,
        'by_stage': by_stage,
    }


def full_pipeline_config() -> Dict[str, object]:
    """Gabungan flag env pipeline rekomendasi (audit / respons API)."""
    import os

    from hybrid_retrieval import (
        ann_top_k,
        dense_use_ann_enabled,
        metadata_gate_enabled,
        retrieval_top_k,
    )
    from llm_clause_sentiment import clause_sentiment_enabled, sentiment_config
    from llm_recommender import pipeline_config as llm_core_config
    from review_embedding_store import (
        PGVECTOR_DIM,
        embedding_store_mode,
        use_pgvector_store,
    )
    from semantic_match import gate_config as semantic_gate_config, model_name as embedding_model_name
    from recommendation.flags import recommendation_overall_experience_enabled

    def _flag(name: str, default: bool = False) -> bool:
        raw = (os.getenv(name) or '').strip().lower()
        if not raw:
            return default
        return raw in ('1', 'true', 'yes', 'on')

    core = dict(llm_core_config())
    clause = dict(sentiment_config())
    semantic = dict(semantic_gate_config())
    return {
        **core,
        'retrieval_top_k': retrieval_top_k(),
        'metadata_gate': metadata_gate_enabled(),
        'clause_sentiment': clause,
        'semantic_gate': semantic,
        'dev_llm_strict': _flag('COFIND_DEV_LLM_STRICT', False),
        'modal_quote_llm': _flag('COFIND_MODAL_QUOTE_LLM', False),
        'clause_sentiment_dedup': _flag('COFIND_CLAUSE_SENTIMENT_DEDUP', True),
        'embedding_store': embedding_store_mode(),
        'pgvector_active': use_pgvector_store(),
        'embedding_model': embedding_model_name(),
        'pgvector_dim': PGVECTOR_DIM,
        'dense_use_ann': dense_use_ann_enabled(),
        'ann_top_k': ann_top_k(),
        'embedding_async': _flag('COFIND_EMBEDDING_ASYNC', False),
        'recommend_use_overall_experience': recommendation_overall_experience_enabled(),
    }


def build_degradation_snapshot(
    *,
    llm_available: bool,
    clause_sentiment_telemetry: Optional[Dict[str, object]] = None,
    rerank_backend: str = 'hybrid',
    rerank_telemetry: Optional[Dict[str, object]] = None,
    delivered_count: int = 0,
    summary_fallback_count: int = 0,
) -> Dict[str, object]:
    clause = dict(clause_sentiment_telemetry or {})
    skipped = clause.get('skipped')
    from llm_clause_sentiment import clause_sentiment_enabled as clause_flag_enabled

    if not clause_flag_enabled():
        clause_mode = 'disabled'
    elif skipped:
        clause_mode = f'skipped:{skipped}'
    elif (
        int(clause.get('from_absa') or 0) > 0
        or int(clause.get('llm_calls') or 0) > 0
        or int(clause.get('from_cache') or 0) > 0
    ):
        clause_mode = 'absa'
    else:
        clause_mode = 'heuristic_only'

    rerank_tel = dict(rerank_telemetry or {})
    rerank_backend = str(rerank_backend or 'hybrid').strip().lower()
    if rerank_backend in ('cross_encoder', 'cache'):
        ranking = 'cross_encoder'
    elif rerank_backend == 'llm':
        ranking = 'llm'
    else:
        ranking = 'hybrid_fallback'

    return {
        'llm_available': bool(llm_available),
        'ranking': ranking,
        'rerank_error': rerank_tel.get('error'),
        'clause_sentiment': clause_mode,
        'summary': 'llm' if summary_fallback_count <= 0 and llm_available else 'mixed_or_fallback',
        'delivered_count': int(delivered_count or 0),
    }


def log_recommendation_run_json(payload: Dict[str, Any]) -> None:
    """Satu baris JSON untuk agregasi log (grep / Loki / skripsi)."""
    try:
        logger.info(json.dumps({'event': 'recommendation_pipeline_run', **payload}, ensure_ascii=False))
    except Exception as err:
        logger.debug(f"log_recommendation_run_json gagal: {err}")


def ensure_pipeline_runs_table() -> bool:
    global _TABLE_READY
    if _TABLE_READY:
        return True
    conn = None
    try:
        from auth_utils import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recommendation_pipeline_runs (
                id SERIAL PRIMARY KEY,
                run_id TEXT NOT NULL UNIQUE,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                preferences_key TEXT,
                status TEXT NOT NULL DEFAULT 'success',
                delivered_count INTEGER NOT NULL DEFAULT 0,
                total_ms REAL,
                clause_sentiment_ms REAL,
                rerank_backend TEXT,
                clause_sentiment_mode TEXT,
                metadata_prior_applied INTEGER DEFAULT 0,
                metadata_penalized INTEGER DEFAULT 0,
                llm_prompt_tokens INTEGER DEFAULT 0,
                llm_completion_tokens INTEGER DEFAULT 0,
                llm_total_tokens INTEGER DEFAULT 0,
                snapshot_json TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        conn.commit()
        _TABLE_READY = True
        return True
    except Exception as err:
        logger.warning(f"ensure_pipeline_runs_table: {err}")
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def record_pipeline_run(
    *,
    run_id: str,
    user_id: Optional[int],
    preferences_key: str,
    status: str,
    delivered_count: int,
    stage_ms: Dict[str, object],
    retrieval_telemetry: Dict[str, object],
    snapshot: Dict[str, object],
    token_usage: Dict[str, object],
) -> None:
    if not ensure_pipeline_runs_table():
        return
    conn = None
    try:
        from auth_utils import get_db_connection

        clause_mode = str((snapshot or {}).get('clause_sentiment') or '')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO recommendation_pipeline_runs (
                run_id, user_id, preferences_key, status, delivered_count, total_ms,
                clause_sentiment_ms, rerank_backend, clause_sentiment_mode,
                metadata_prior_applied, metadata_penalized,
                llm_prompt_tokens, llm_completion_tokens, llm_total_tokens,
                snapshot_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                run_id,
                user_id,
                preferences_key or '',
                status or 'success',
                int(delivered_count or 0),
                float(stage_ms.get('total_ms') or 0),
                float(stage_ms.get('clause_sentiment_ms') or 0),
                str(stage_ms.get('rerank_backend') or ''),
                clause_mode,
                int(retrieval_telemetry.get('metadata_prior_applied') or 0),
                int(retrieval_telemetry.get('metadata_penalized') or 0),
                int(token_usage.get('prompt_tokens') or 0),
                int(token_usage.get('completion_tokens') or 0),
                int(token_usage.get('total_tokens') or 0),
                json.dumps(snapshot or {}, ensure_ascii=False),
            ),
        )
        conn.commit()
    except Exception as err:
        logger.warning(f"record_pipeline_run gagal: {err}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def fetch_pipeline_dashboard_stats(days: int = 14) -> Dict[str, object]:
    """Agregat ringkas untuk panel admin."""
    out: Dict[str, object] = {
        'runs_total': 0,
        'runs_success': 0,
        'avg_total_ms': None,
        'avg_clause_sentiment_ms': None,
        'avg_llm_tokens': None,
        'rerank_llm_rate': None,
        'clause_applied_rate': None,
        'avg_metadata_prior_applied': None,
        'avg_hybrid_retrieval_ms': None,
        'ann_usage_rate': None,
        'daily_runs': [],
    }
    if not ensure_pipeline_runs_table():
        return out
    conn = None
    try:
        from auth_utils import get_db_connection
        from db_backend import dict_from_row, use_postgres

        days = max(1, min(int(days or 14), 90))
        conn = get_db_connection()
        cursor = conn.cursor()
        if use_postgres():
            agg = cursor.execute(
                '''
                SELECT COUNT(*) AS runs_total,
                       SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS runs_success,
                       AVG(total_ms) AS avg_total_ms,
                       AVG(clause_sentiment_ms) AS avg_clause_sentiment_ms,
                       AVG(CASE WHEN clause_sentiment_mode = 'applied' THEN 1.0 ELSE 0.0 END) AS clause_applied_rate,
                       AVG(CASE WHEN rerank_backend = 'llm' THEN 1.0 ELSE 0.0 END) AS rerank_llm_rate,
                       AVG(llm_total_tokens) AS avg_llm_tokens,
                       AVG(metadata_prior_applied) AS avg_metadata_prior_applied
                FROM recommendation_pipeline_runs
                WHERE created_at >= NOW() - (%s * INTERVAL '1 day')
                ''',
                (days,),
            ).fetchone()
        else:
            agg = cursor.execute(
                '''
                SELECT COUNT(*) AS runs_total,
                       SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS runs_success,
                       AVG(total_ms) AS avg_total_ms,
                       AVG(clause_sentiment_ms) AS avg_clause_sentiment_ms,
                       AVG(CASE WHEN clause_sentiment_mode = 'applied' THEN 1.0 ELSE 0.0 END) AS clause_applied_rate,
                       AVG(CASE WHEN rerank_backend = 'llm' THEN 1.0 ELSE 0.0 END) AS rerank_llm_rate,
                       AVG(llm_total_tokens) AS avg_llm_tokens,
                       AVG(metadata_prior_applied) AS avg_metadata_prior_applied
                FROM recommendation_pipeline_runs
                WHERE datetime(created_at) >= datetime('now', ?)
                ''',
                (f'-{days} days',),
            ).fetchone()
        rd = dict_from_row(cursor, agg) or {}
        runs_total = int(rd.get('runs_total') or 0)
        out['runs_total'] = runs_total
        out['runs_success'] = int(rd.get('runs_success') or 0)
        if runs_total > 0:
            for key in (
                'avg_total_ms',
                'avg_clause_sentiment_ms',
                'avg_llm_tokens',
                'avg_metadata_prior_applied',
            ):
                val = rd.get(key)
                if val is not None:
                    out[key] = round(float(val), 1)
            for key in ('clause_applied_rate', 'rerank_llm_rate'):
                val = rd.get(key)
                if val is not None:
                    out[key] = round(100.0 * float(val), 1)

        if use_postgres():
            daily_rows = cursor.execute(
                '''
                SELECT TO_CHAR(DATE(created_at), 'YYYY-MM-DD') AS day_key, COUNT(*) AS cnt
                FROM recommendation_pipeline_runs
                WHERE created_at >= NOW() - (%s * INTERVAL '1 day')
                GROUP BY DATE(created_at)
                ORDER BY DATE(created_at)
                ''',
                (days,),
            ).fetchall()
        else:
            daily_rows = cursor.execute(
                '''
                SELECT date(created_at) AS day_key, COUNT(*) AS cnt
                FROM recommendation_pipeline_runs
                WHERE datetime(created_at) >= datetime('now', ?)
                GROUP BY date(created_at)
                ORDER BY date(created_at)
                ''',
                (f'-{days} days',),
            ).fetchall()
        trend = []
        for row in daily_rows or []:
            drow = dict_from_row(cursor, row) or {}
            trend.append({
                'date': str(drow.get('day_key') or '')[:10],
                'count': int(drow.get('cnt') or 0),
            })
        out['daily_runs'] = trend

        if use_postgres():
            snap_rows = cursor.execute(
                '''
                SELECT snapshot_json, total_ms
                FROM recommendation_pipeline_runs
                WHERE created_at >= NOW() - (%s * INTERVAL '1 day')
                  AND snapshot_json IS NOT NULL AND snapshot_json != ''
                ''',
                (days,),
            ).fetchall()
        else:
            snap_rows = cursor.execute(
                '''
                SELECT snapshot_json, total_ms
                FROM recommendation_pipeline_runs
                WHERE datetime(created_at) >= datetime('now', ?)
                  AND snapshot_json IS NOT NULL AND snapshot_json != ''
                ''',
                (f'-{days} days',),
            ).fetchall()
        hybrid_ms_vals = []
        ann_hits = 0
        snap_total = 0
        for row in snap_rows or []:
            srow = dict_from_row(cursor, row) or {}
            raw = srow.get('snapshot_json')
            if not raw:
                continue
            snap_total += 1
            try:
                snap = json.loads(raw) if isinstance(raw, str) else raw
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(snap, dict):
                continue
            hms = snap.get('hybrid_retrieval_ms')
            if hms is not None:
                try:
                    hybrid_ms_vals.append(float(hms))
                except (TypeError, ValueError):
                    pass
            if str(snap.get('dense_pool') or '').lower() == 'ann':
                ann_hits += 1
        if hybrid_ms_vals:
            out['avg_hybrid_retrieval_ms'] = round(
                sum(hybrid_ms_vals) / len(hybrid_ms_vals), 1,
            )
        if snap_total > 0:
            out['ann_usage_rate'] = round(100.0 * ann_hits / snap_total, 1)
    except Exception as err:
        logger.warning(f"fetch_pipeline_dashboard_stats: {err}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    return out
