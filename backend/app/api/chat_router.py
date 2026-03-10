# backend/app/api/chat_router.py
"""
Chat API router — handles user questions and streams answers via SSE.

Endpoints:
  POST /api/chat/ask       → Full (blocking) answer + sources
  POST /api/chat/stream    → Server-Sent Events token stream
"""
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.domain.schemas import ChatRequest, ChatResponse, SourceDocument
from app.services.rag_orchestrator import RAGOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Dependency Injection ────────────────────────────────────────────
def _get_orchestrator() -> RAGOrchestrator:
    """FastAPI dependency — returns the RAG orchestrator singleton."""
    return RAGOrchestrator()


# ════════════════════════════════════════════════════════════════════
# POST /ask — Blocking response
# ════════════════════════════════════════════════════════════════════
@router.post(
    "/ask",
    response_model=ChatResponse,
    summary="Ask a question (blocking)",
    description="Submit a question and receive the full answer with sources.",
)
async def ask_question(
    body: ChatRequest,
    rag: RAGOrchestrator = Depends(_get_orchestrator),
):
    """
    1. Retrieve relevant chunks via hybrid search.
    2. Generate full answer via Groq Llama 3.3 70B.
    3. Return answer + source documents.
    """
    logger.info("Received question: %s", body.question[:80])
    answer, sources = rag.answer(body.question)
    return ChatResponse(answer=answer, sources=sources)


# ════════════════════════════════════════════════════════════════════
# POST /stream — Server-Sent Events
# ════════════════════════════════════════════════════════════════════
@router.post(
    "/stream",
    summary="Ask a question (streaming SSE)",
    description="Submit a question and receive the answer as a token stream.",
)
async def stream_answer(
    body: ChatRequest,
    rag: RAGOrchestrator = Depends(_get_orchestrator),
):
    """
    1. Retrieve relevant chunks (fast, done before streaming begins).
    2. Stream tokens one-by-one from Groq via SSE.
    3. Final SSE event carries the source documents JSON.
    """
    logger.info("Streaming answer for: %s", body.question[:80])
    token_gen, sources = rag.answer_stream(body.question)

    async def _event_generator() -> AsyncGenerator[str, None]:
        """Yield SSE-formatted events."""
        # Stream tokens
        for token in token_gen:
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        # Final event with sources
        sources_payload = [s.model_dump() for s in sources]
        yield f"data: {json.dumps({'type': 'sources', 'content': sources_payload})}\n\n"

        # Signal stream end
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx SSE support
        },
    )
