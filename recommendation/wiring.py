"""
Satukan API internal modul rekomendasi setelah pecah app.py.

Penyebab NameError beruntun (progress map, split pills, evidence, _MIN_QUOTE_CHARS):
`from module import *` di Python TIDAK mengekspor nama yang diawali `_`, sementara
hampir seluruh helper pipeline memakai prefix itu. Modul saling memanggil tanpa
import eksplisit → simbol hilang saat runtime (bukan saat import checker).

Urutan wiring (hindari import sirkular):
  1. helpers (tanpa import evidence)
  2. evidence (bind private helpers → namespace evidence)
  3. helpers ← evidence (private evidence → namespace helpers)
  4. pipeline (helpers + evidence → namespace pipeline)
"""
from __future__ import annotations

from types import ModuleType

_WIRED = False


def _copy_private_names(source: ModuleType, target: ModuleType) -> int:
    tg = target.__dict__
    added = 0
    for name, val in vars(source).items():
        if not name.startswith('_') or name.startswith('__'):
            continue
        if name in tg:
            continue
        tg[name] = val
        added += 1
    return added


def ensure_recommendation_wiring() -> None:
    """Idempotent: panggil sebelum menjalankan pipeline atau helper lintas-modul."""
    global _WIRED
    if _WIRED:
        return

    import recommendation.helpers as helpers_mod

    # evidence mem-bind helpers saat import; pastikan modul evidence sudah lengkap.
    import recommendation.evidence as evidence_mod  # noqa: F401

    _copy_private_names(evidence_mod, helpers_mod)
    helpers_mod._evidence_private_api_merged = True  # type: ignore[attr-defined]

    _WIRED = True


def populate_pipeline_namespace(namespace: dict) -> None:
    """Isi globals pipeline.py dengan simbol public + private helpers/evidence."""
    ensure_recommendation_wiring()
    import recommendation.evidence as evidence_mod
    import recommendation.helpers as helpers_mod

    for mod in (helpers_mod, evidence_mod):
        for name, val in vars(mod).items():
            if name.startswith('__'):
                continue
            if not name.startswith('_') and name in namespace:
                continue
            namespace[name] = val


def assert_pipeline_symbols(namespace: dict, *, extra: tuple[str, ...] = ()) -> None:
    """Raises AssertionError jika simbol kritikal pipeline hilang (untuk tes)."""
    required = (
        '_RECOMMENDATION_PROGRESS_BY_STAGE',
        '_split_preference_pills',
        '_build_retrieval_evidence',
        '_build_review_based_evidence',
        '_facilities_tab_display_for_intent',
        '_quote_is_caveat',
        '_merge_evidence_private_api',
        'RATING_VOTE_WEIGHTS',
        'coverage_bonus',
        'activity_coverage_share',
        'coverage_semantic_min',
        '_score_shop_by_user_reviews',
        *extra,
    )
    missing = [n for n in required if n not in namespace]
    if missing:
        raise AssertionError(f'simbol pipeline hilang: {missing}')
