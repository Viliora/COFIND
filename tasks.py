from __future__ import annotations

from celery_app import celery_app


@celery_app.task(name="cofind.summarize_review_task")
def summarize_review_task(place_id: str, shop_name: str):
    """
    Task async untuk summary review per place_id.
    """
    from app import _run_summarize_review_analysis

    result = _run_summarize_review_analysis(place_id, shop_name)
    if not result.get("ok"):
        return {
            "status": "error",
            "message": result.get("message", "Gagal summarize"),
            "status_code": int(result.get("status_code") or 500),
        }
    return result.get("payload") or {"status": "success"}
