# backend/app/repositories/wp_repository.py
"""
Repository for extracting published content from the WordPress MySQL database.

Uses SQLAlchemy Core (not ORM) to query the wp_posts and wp_postmeta tables
directly, which avoids needing a full WordPress ORM mapping.

The Repository Pattern keeps all raw SQL / DB access isolated here.
"""
import logging
import re
from typing import List

from sqlalchemy import create_engine, text
from app.core.settings import settings
from app.domain.schemas import WPDocument

logger = logging.getLogger(__name__)


class WPRepository:
    """
    Reads published posts and pages from the WordPress database.
    Strips HTML tags to produce clean plain-text content.
    """

    def __init__(self) -> None:
        self._engine = create_engine(
            settings.wp_db_uri,
            pool_pre_ping=True,       # reconnect on stale connections
            pool_size=5,
            max_overflow=10,
        )
        self._prefix = settings.wp_table_prefix

    # ── Public API ──────────────────────────────────────────────────

    def extract_published_content(
        self,
        post_types: tuple = ("post", "page"),
    ) -> List[WPDocument]:
        """
        Extract all published posts/pages from WordPress.
        Returns a list of WPDocument domain objects with HTML stripped.
        """
        posts_table = f"{self._prefix}posts"
        query = text(f"""
            SELECT
                ID          AS post_id,
                post_title  AS title,
                post_content AS content,
                post_type,
                post_status,
                guid        AS url
            FROM {posts_table}
            WHERE post_status = 'publish'
              AND post_type IN :post_types
              AND post_content IS NOT NULL
              AND CHAR_LENGTH(post_content) > 50
            ORDER BY post_date DESC
        """)

        documents: List[WPDocument] = []
        with self._engine.connect() as conn:
            rows = conn.execute(query, {"post_types": post_types}).fetchall()

        logger.info("Extracted %d published documents from WordPress.", len(rows))
        for row in rows:
            clean_text = self._strip_html(row.content)
            if len(clean_text.strip()) < 30:
                continue  # skip near-empty content
            documents.append(
                WPDocument(
                    post_id=row.post_id,
                    title=row.title,
                    content=clean_text,
                    post_type=row.post_type,
                    post_status=row.post_status,
                    url=row.url,
                )
            )
        return documents

    def get_document_count(self) -> int:
        """Quick count of published posts for the admin dashboard."""
        posts_table = f"{self._prefix}posts"
        query = text(f"""
            SELECT COUNT(*) AS cnt
            FROM {posts_table}
            WHERE post_status = 'publish'
              AND post_type IN ('post', 'page')
        """)
        with self._engine.connect() as conn:
            result = conn.execute(query).scalar()
        return result or 0

    # ── Internal helpers ────────────────────────────────────────────

    @staticmethod
    def _strip_html(html: str) -> str:
        """
        Remove HTML tags, WordPress shortcodes, and excessive whitespace.
        """
        # Remove WordPress shortcodes like [gallery], [caption id="..."]
        text_content = re.sub(r"\[/?[^\]]+\]", "", html)
        # Remove HTML tags
        text_content = re.sub(r"<[^>]+>", " ", text_content)
        # Decode common HTML entities
        text_content = (
            text_content
            .replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#039;", "'")
        )
        # Collapse whitespace
        text_content = re.sub(r"\s+", " ", text_content).strip()
        return text_content
