# backend/main.py
"""
Application Factory — creates and configures the FastAPI application.

Entry point:  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.core.settings import settings
from app.api import chat_router, admin_router

# ── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Application Factory pattern.
    Configures middleware, registers routers, and sets up lifecycle events.
    """
    app = FastAPI(
        title=settings.project_name,
        version="1.0.0",
        description="Multilingual RAG chatbot backed by WordPress + Qdrant + Groq",
    )

    # ── CORS — allow the React dev server ──────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],          # Allow all origins for local dev
        allow_credentials=False,      # Must be False when using wildcard
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],         # Required for SSE streaming
    )

    # ── Register API routers ───────────────────────────────────────
    app.include_router(chat_router.router, prefix="/api/chat", tags=["Chat"])
    app.include_router(admin_router.router, prefix="/api/admin", tags=["Admin"])

    # ── Health check ───────────────────────────────────────────────
    @app.get("/health", tags=["System"])
    async def health_check():
        return {"status": "operational", "project": settings.project_name}

    logger.info("🚀  %s application created.", settings.project_name)
    return app


# Module-level app instance used by uvicorn and Celery integration
app = create_app()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)