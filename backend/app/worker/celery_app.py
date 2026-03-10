# backend/app/worker/celery_app.py
from celery import Celery
from app.core.settings import settings

celery_app = Celery(
    "wp_rag_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"]
)

# Enforce hardware-constrained execution patterns
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    # Strictly limit concurrency to 1 to prevent multiple embedding models loading into VRAM
    worker_concurrency=1,
    # Prevent the worker from reserving multiple heavy tasks in memory simultaneously
    worker_prefetch_multiplier=1,
    task_acks_late=True
)