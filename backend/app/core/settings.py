# backend/app/core/settings.py
"""
Centralized application settings loaded from environment variables.
Uses pydantic-settings for automatic .env file loading and type validation.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
from typing import Optional


class Settings(BaseSettings):
    """
    Application-wide configuration.
    All values default to local development settings and can be
    overridden via a `.env` file or OS-level environment variables.
    """

    project_name: str = "Herald Kitchen — Multilingual WP RAG"

    # ── Infrastructure Connections ──────────────────────────────────
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "wp_healthcare_content"
    redis_url: str = "redis://localhost:6379/0"

    # ── WordPress MySQL Database ───────────────────────────────────
    wp_db_uri: str = "mysql+pymysql://root:password@localhost:3306/wordpress"
    # Optional: WordPress table prefix (usually 'wp_')
    wp_table_prefix: str = "wp_"

    # ── Groq Cloud API (Generation Layer) ──────────────────────────
    groq_api_key: SecretStr
    groq_model: str = "llama-3.3-70b-versatile"

    # ── RAG Configuration ──────────────────────────────────────────
    chunk_size: int = 500
    chunk_overlap: int = 50
    embedding_model_name: str = "BAAI/bge-m3"
    # Max dense / sparse vectors returned by hybrid search
    retrieval_top_k: int = 10

    # ── VRAM Safety ────────────────────────────────────────────────
    embedding_batch_size: int = 32  # batch size for BGE-M3 inference

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Module-level singleton — imported everywhere
settings = Settings()