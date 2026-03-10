# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.core.settings import settings
# from app.api import chat_router, admin_router  # To be implemented

def create_app() -> FastAPI:
    app = FastAPI(title=settings.project_name)

    # Configure CORS for the React Frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"], # Default Vite React port
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Routers
    # app.include_router(chat_router.router, prefix="/api/chat", tags=["Chat"])
    # app.include_router(admin_router.router, prefix="/api/admin", tags=["Admin"])

    @app.get("/health")
    async def health_check():
        return {"status": "operational", "project": settings.project_name}

    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)