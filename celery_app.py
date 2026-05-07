from __future__ import annotations

import os

from celery import Celery


def _build_celery() -> Celery:
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    app = Celery(
        "cofind",
        broker=redis_url,
        backend=redis_url,
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="Asia/Jakarta",
        enable_utc=False,
        task_track_started=True,
        result_expires=int(os.getenv("COFIND_JOB_RESULT_TTL_SECONDS", "3600")),
        worker_concurrency=int(os.getenv("CELERY_WORKER_CONCURRENCY", "1")),
        worker_prefetch_multiplier=1,
        task_time_limit=int(os.getenv("COFIND_SUMMARY_TASK_TIME_LIMIT_SECONDS", "300")),
        task_soft_time_limit=int(os.getenv("COFIND_SUMMARY_TASK_SOFT_TIME_LIMIT_SECONDS", "240")),
    )
    return app


celery_app = _build_celery()
