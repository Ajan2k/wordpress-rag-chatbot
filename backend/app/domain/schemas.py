# backend/app/domain/schemas.py
"""
Pydantic models (schemas) used across the application.
These define the strict data contracts for API requests/responses
and inter-service communication.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


# ════════════════════════════════════════════════════════════════════
# Chat Schemas
# ════════════════════════════════════════════════════════════════════


class ChatRequest(BaseModel):
    """Incoming chat question from the frontend."""
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User's question in any language.",
        examples=["What are the symptoms of Type 2 Diabetes?"],
    )


class SourceDocument(BaseModel):
    """One source document chunk returned alongside the answer."""
    title: str
    content_preview: str = Field(
        ..., description="First ~200 chars of the chunk."
    )
    doc_id: str              # Kitchen Herald document id (article_123, event_45, etc.)
    doc_type: str = "article"  # article, event, job
    score: float = Field(
        ..., description="Combined RRF relevance score."
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """Full (non-streaming) response to a chat question."""
    answer: str
    sources: List[SourceDocument] = []


# ════════════════════════════════════════════════════════════════════
# Admin / ETL Schemas
# ════════════════════════════════════════════════════════════════════


class SyncTriggerResponse(BaseModel):
    """Returned when a new sync job is queued."""
    task_id: str
    status: str = "QUEUED"
    message: str = "Kitchen Herald data synchronisation has been queued."


class TaskState(str, Enum):
    """Possible states of a Celery task."""
    PENDING = "PENDING"
    STARTED = "STARTED"
    PROGRESS = "PROGRESS"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    REVOKED = "REVOKED"


class TaskStatusResponse(BaseModel):
    """Live task status — polled by the admin dashboard."""
    task_id: str
    state: TaskState
    progress: int = Field(0, ge=0, le=100)
    status_message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ════════════════════════════════════════════════════════════════════
# Internal Domain Objects (not exposed via API)
# ════════════════════════════════════════════════════════════════════


class KHDocument(BaseModel):
    """Represents a Kitchen Herald document (article, event, or job listing)."""
    doc_id: str           # unique id: article_ID, event_ID, or job_ID
    title: str
    content: str          # clean, HTML-stripped text
    doc_type: str = Field("article", description="article | event | job")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    published_date: Optional[str] = None  # ISO datetime or date string


class DocumentChunk(BaseModel):
    """A text chunk derived from a KHDocument after splitting."""
    chunk_id: str         # deterministic id: f"{doc_id}_{chunk_index}"
    doc_id: str           # original document id (article_ID, event_ID, job_ID)
    doc_type: str = "article"
    title: str
    content: str          # plain text chunk (~500 tokens)
    chunk_index: int
    metadata: Dict[str, Any] = Field(default_factory=dict)

