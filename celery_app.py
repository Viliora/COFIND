from __future__ import annotations

import os
import ssl

from celery import Celery
from dotenv import load_dotenv

from redis_utils import get_redis_url

load_dotenv()


def _build_celery() -> Celery:
    redis_url = get_redis_url()
    app = Celery(
        "cofind",
        broker=redis_url,
        backend=redis_url,
    )

    conf = {
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        "timezone": "Asia/Jakarta",
        "enable_utc": False,
        "task_track_started": True,
        "result_expires": int(os.getenv("COFIND_JOB_RESULT_TTL_SECONDS", "3600")),
        "worker_concurrency": int(os.getenv("CELERY_WORKER_CONCURRENCY", "1")),
        "worker_prefetch_multiplier": 1,
        "task_time_limit": int(os.getenv("COFIND_SUMMARY_TASK_TIME_LIMIT_SECONDS", "300")),
        "task_soft_time_limit": int(os.getenv("COFIND_SUMMARY_TASK_SOFT_TIME_LIMIT_SECONDS", "240")),
        "broker_connection_retry_on_startup": True,
    }

    # TLS untuk Upstash (rediss://)
    if redis_url.startswith("rediss://"):
        ssl_opts = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
        conf["broker_use_ssl"] = ssl_opts
        conf["redis_backend_use_ssl"] = ssl_opts

    app.conf.update(conf)
    return app


celery_app = _build_celery()
