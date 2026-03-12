# backend/app/api/admin_router.py
"""
Admin API router — triggers and monitors the Kitchen Herald data sync.

Endpoints:
  POST /api/admin/sync           → Queue a new sync job
  GET  /api/admin/sync/{task_id} → Poll task progress
  GET  /api/admin/status         → System health overview
"""
import logging

from fastapi import APIRouter
from celery.result import AsyncResult

from app.domain.schemas import SyncTriggerResponse, TaskStatusResponse, TaskState
from app.worker.celery_app import celery_app
from app.worker.tasks import sync_kitchen_herald_data
from app.repositories.kh_repository import KitchenHeraldRepository
from app.repositories.vector_store import VectorStore

logger = logging.getLogger(__name__)
router = APIRouter()


# ════════════════════════════════════════════════════════════════════
# POST /sync — Trigger Kitchen Herald data synchronisation
# ════════════════════════════════════════════════════════════════════
@router.post(
    "/sync",
    response_model=SyncTriggerResponse,
    summary="Trigger Kitchen Herald data sync",
    description="Queues an asynchronous ETL job via Celery.",
)
async def trigger_sync():
    """
    Dispatch the sync_kitchen_herald_data Celery task.
    Returns the task ID immediately so the frontend can poll for progress.
    """
    task = sync_kitchen_herald_data.delay()
    logger.info("Queued Kitchen Herald sync task: %s", task.id)
    return SyncTriggerResponse(task_id=task.id)


# ════════════════════════════════════════════════════════════════════
# GET /sync/{task_id} — Poll task progress
# ════════════════════════════════════════════════════════════════════
@router.get(
    "/sync/{task_id}",
    response_model=TaskStatusResponse,
    summary="Get sync task status",
    description="Returns the current progress of a sync task.",
)
async def get_task_status(task_id: str):
    """
    Read the task state from Redis via Celery's AsyncResult.
    Maps Celery's internal states to our API schema.
    """
    result = AsyncResult(task_id, app=celery_app)

    # Build response based on celery state
    if result.state == "PENDING":
        return TaskStatusResponse(
            task_id=task_id,
            state=TaskState.PENDING,
            progress=0,
            status_message="Task is waiting in queue …",
        )

    elif result.state == "STARTED":
        return TaskStatusResponse(
            task_id=task_id,
            state=TaskState.STARTED,
            progress=5,
            status_message="Task has been picked up by the worker.",
        )

    elif result.state == "PROGRESS":
        meta = result.info or {}
        return TaskStatusResponse(
            task_id=task_id,
            state=TaskState.PROGRESS,
            progress=meta.get("current", 0),
            status_message=meta.get("status", "Processing …"),
        )

    elif result.state == "SUCCESS":
        meta = result.result or {}
        return TaskStatusResponse(
            task_id=task_id,
            state=TaskState.SUCCESS,
            progress=100,
            status_message=meta.get("status", "Complete"),
            result=meta,
        )

    elif result.state == "FAILURE":
        error_msg = str(result.info) if result.info else "Unknown error"
        return TaskStatusResponse(
            task_id=task_id,
            state=TaskState.FAILURE,
            progress=0,
            status_message="Task failed.",
            error=error_msg,
        )

    else:
        return TaskStatusResponse(
            task_id=task_id,
            state=TaskState.PENDING,
            progress=0,
            status_message=f"Unknown state: {result.state}",
        )


# ════════════════════════════════════════════════════════════════════
# GET /status — System overview
# ════════════════════════════════════════════════════════════════════
@router.get(
    "/status",
    summary="System health overview",
    description="Returns counts from Kitchen Herald DB and Qdrant collection.",
)
async def system_status():
    """
    Quick system health check for the admin dashboard.
    """
    try:
        kh_repo = KitchenHeraldRepository()
        article_count = kh_repo.get_article_count()
        event_count = kh_repo.get_event_count()
        job_count = kh_repo.get_job_count()
    except Exception as e:
        article_count = event_count = job_count = f"Error: {e}"

    try:
        qdrant_info = VectorStore().get_collection_info()
    except Exception as e:
        qdrant_info = {"error": str(e)}

    return {
        "kitchen_herald": {
            "articles": article_count,
            "events": event_count,
            "jobs": job_count,
        },
        "qdrant": qdrant_info,
    }
