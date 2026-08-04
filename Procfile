web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
worker: celery -A celery_app.celery_app worker --loglevel=info --concurrency=${CELERY_WORKER_CONCURRENCY:-1}
