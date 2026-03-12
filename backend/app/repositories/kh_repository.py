# backend/app/repositories/kh_repository.py
"""
Repository for extracting published content from the Kitchen Herald MySQL database.

Queries:
  • Articles with associated tags and category/subcategory
  • Events across all cities and dates
  • Active job vacancies
  
Uses SQLAlchemy Core to avoid ORM overhead.
The Repository Pattern isolates all database access.
"""
import logging
import re
from typing import List, Dict, Optional
from datetime import datetime

from sqlalchemy import create_engine, text
from app.core.settings import settings
from app.domain.schemas import KHDocument

logger = logging.getLogger(__name__)


class KitchenHeraldRepository:
    """
    Reads published articles, events, and job listings from Kitchen Herald.
    Produces clean, structured content for embedding and retrieval.
    """

    def __init__(self) -> None:
        self._engine = create_engine(
            settings.kh_db_uri,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )

    # ── Public API ──────────────────────────────────────────────────

    def extract_all_content(self) -> List[KHDocument]:
        """
        Extract all indexable content: articles, events, and job listings.
        Returns a list of KHDocument domain objects.
        """
        documents = []
        documents.extend(self._extract_articles())
        documents.extend(self._extract_events())
        documents.extend(self._extract_job_listings())
        
        logger.info("Extracted %d total documents from Kitchen Herald.", len(documents))
        return documents

    def extract_articles(self) -> List[KHDocument]:
        """Extract only published articles with tags and categories."""
        return self._extract_articles()

    def extract_events(self) -> List[KHDocument]:
        """Extract upcoming and ongoing events."""
        return self._extract_events()

    def extract_job_listings(self) -> List[KHDocument]:
        """Extract active job vacancies."""
        return self._extract_job_listings()

    def get_article_count(self) -> int:
        """Quick count of published articles."""
        query = text("""
            SELECT COUNT(*) AS cnt
            FROM articles
            WHERE status = 'published'
        """)
        with self._engine.connect() as conn:
            result = conn.execute(query).scalar()
        return result or 0

    def get_event_count(self) -> int:
        """Quick count of upcoming events."""
        query = text("""
            SELECT COUNT(*) AS cnt
            FROM events
            WHERE status IN ('upcoming', 'ongoing')
            AND event_date_start >= CURDATE()
        """)
        with self._engine.connect() as conn:
            result = conn.execute(query).scalar()
        return result or 0

    def get_job_count(self) -> int:
        """Quick count of active job postings."""
        query = text("""
            SELECT COUNT(*) AS cnt
            FROM job_vacancies
            WHERE is_active = TRUE
            AND (expires_at IS NULL OR expires_at >= CURDATE())
        """)
        with self._engine.connect() as conn:
            result = conn.execute(query).scalar()
        return result or 0

    # ── Internal extraction methods ──────────────────────────────────

    def _extract_articles(self) -> List[KHDocument]:
        """
        Extract published articles with titles, content, tags, and metadata.
        Falls back to excerpt when body is NULL or too short.
        """
        query = text("""
            SELECT
                a.article_id,
                a.title,
                a.slug,
                a.body,
                a.excerpt,
                a.featured_image_url,
                a.published_at,
                a.view_count,
                a.is_featured,
                c.name AS category,
                c.slug AS category_slug,
                sc.name AS subcategory,
                sc.slug AS subcategory_slug,
                GROUP_CONCAT(t.name ORDER BY t.name SEPARATOR ', ') AS tags,
                au.display_name AS author
            FROM articles a
            LEFT JOIN categories c ON a.category_id = c.category_id
            LEFT JOIN subcategories sc ON a.subcategory_id = sc.subcategory_id
            LEFT JOIN authors au ON a.author_id = au.author_id
            LEFT JOIN article_tags at2 ON a.article_id = at2.article_id
            LEFT JOIN tags t ON at2.tag_id = t.tag_id
            WHERE a.status = 'published'
            AND (
                (a.body IS NOT NULL AND CHAR_LENGTH(a.body) > 50)
                OR (a.excerpt IS NOT NULL AND CHAR_LENGTH(a.excerpt) > 20)
            )
            GROUP BY a.article_id
            ORDER BY a.published_at DESC
        """)

        documents = []
        with self._engine.connect() as conn:
            rows = conn.execute(query).fetchall()

        logger.info("Extracted %d articles from Kitchen Herald.", len(rows))
        for row in rows:
            # Use body if available, otherwise fall back to excerpt
            raw_text = row.body or row.excerpt or ""
            clean_text = self._strip_html(raw_text)
            if len(clean_text.strip()) < 20:
                continue

            # Prepend title and category/tag context for richer embeddings
            enriched_text = f"{row.title}\n"
            if row.category:
                enriched_text += f"Category: {row.category}"
                if row.subcategory:
                    enriched_text += f" > {row.subcategory}"
                enriched_text += "\n"
            if row.tags:
                enriched_text += f"Tags: {row.tags}\n"
            enriched_text += f"\n{clean_text}"

            # Build rich metadata
            article_url = f"https://www.kitchenherald.com/{row.slug}" if row.slug else ""
            metadata = {
                "article_id": row.article_id,
                "category": row.category,
                "subcategory": row.subcategory,
                "tags": row.tags or "",
                "author": row.author or "Kitchen Herald",
                "published_at": str(row.published_at) if row.published_at else "",
                "excerpt": (row.excerpt or "")[:300],
                "image_url": row.featured_image_url or "",
                "url": article_url,
                "view_count": row.view_count or 0,
                "is_featured": bool(row.is_featured),
            }

            documents.append(
                KHDocument(
                    doc_id=f"article_{row.article_id}",
                    title=row.title,
                    content=enriched_text,
                    doc_type="article",
                    metadata=metadata,
                    published_date=str(row.published_at) if row.published_at else None,
                )
            )

        return documents

    def _extract_events(self) -> List[KHDocument]:
        """
        Extract upcoming and ongoing events with location and date info.
        """
        query = text("""
            SELECT
                event_id,
                title,
                slug,
                description,
                venue,
                city,
                state,
                country,
                event_date_start,
                event_date_end,
                organizer,
                registration_url,
                featured_image_url,
                status
            FROM events
            WHERE status IN ('upcoming', 'ongoing')
            AND event_date_start >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            ORDER BY event_date_start ASC
        """)

        documents = []
        with self._engine.connect() as conn:
            rows = conn.execute(query).fetchall()

        logger.info("Extracted %d events from Kitchen Herald.", len(rows))
        for row in rows:
            # Create descriptive content for events
            location_parts = [p for p in [row.city, row.state, row.country] if p]
            location_str = ", ".join(location_parts) if location_parts else row.venue or "TBD"
            
            date_str = row.event_date_start.strftime("%B %d, %Y") if row.event_date_start else "TBD"
            if row.event_date_end and row.event_date_end != row.event_date_start:
                date_str += f" – {row.event_date_end.strftime('%B %d, %Y')}"

            content = f"{row.title}\n\n"
            if row.description:
                content += f"{row.description}\n\n"
            content += f"📍 Location: {location_str}\n"
            if row.venue:
                content += f"🏛️ Venue: {row.venue}\n"
            content += f"📅 Date: {date_str}\n"
            if row.organizer:
                content += f"🏢 Organizer: {row.organizer}\n"
            if row.registration_url:
                content += f"🔗 Register: {row.registration_url}\n"

            event_url = f"https://www.kitchenherald.com/events/{row.slug}" if row.slug else ""
            metadata = {
                "event_id": row.event_id,
                "venue": row.venue,
                "city": row.city,
                "state": row.state,
                "country": row.country,
                "organizer": row.organizer or "",
                "registration_url": row.registration_url or "",
                "event_status": row.status,
                "url": event_url,
                "image_url": row.featured_image_url or "",
            }

            documents.append(
                KHDocument(
                    doc_id=f"event_{row.event_id}",
                    title=row.title,
                    content=content,
                    doc_type="event",
                    metadata=metadata,
                    published_date=str(row.event_date_start) if row.event_date_start else None,
                )
            )

        return documents

    def _extract_job_listings(self) -> List[KHDocument]:
        """
        Extract active job vacancies with company, location, and requirements.
        """
        query = text("""
            SELECT
                job_id,
                title,
                slug,
                company_name,
                location,
                job_type,
                experience_years_min,
                experience_years_max,
                description,
                how_to_apply,
                contact_email,
                posted_at,
                expires_at
            FROM job_vacancies
            WHERE is_active = TRUE
            AND (expires_at IS NULL OR expires_at >= CURDATE())
            ORDER BY posted_at DESC
        """)

        documents = []
        with self._engine.connect() as conn:
            rows = conn.execute(query).fetchall()

        logger.info("Extracted %d job listings from Kitchen Herald.", len(rows))
        for row in rows:
            # Build descriptive job content
            exp_str = ""
            if row.experience_years_min and row.experience_years_max:
                exp_str = f"{row.experience_years_min}-{row.experience_years_max} years"
            elif row.experience_years_min:
                exp_str = f"{row.experience_years_min}+ years"
            
            job_type_display = row.job_type.replace('-', ' ').title() if row.job_type else "Full Time"
            
            content = f"{row.title}\n\n"
            content += f"🏢 Company: {row.company_name}\n"
            content += f"📍 Location: {row.location}\n"
            content += f"💼 Type: {job_type_display}\n"
            if exp_str:
                content += f"⏳ Experience: {exp_str}\n"
            if row.description:
                content += f"\n{row.description}\n"
            if row.how_to_apply:
                content += f"\n📋 How to Apply:\n{row.how_to_apply}\n"
            if row.contact_email:
                content += f"\n📧 Contact: {row.contact_email}\n"

            job_url = f"https://www.kitchenherald.com/jobs/{row.slug}" if row.slug else ""
            metadata = {
                "job_id": row.job_id,
                "company": row.company_name,
                "location": row.location,
                "job_type": job_type_display,
                "experience_min": row.experience_years_min,
                "experience_max": row.experience_years_max,
                "contact_email": row.contact_email or "",
                "expires_at": str(row.expires_at) if row.expires_at else "",
                "url": job_url,
            }

            documents.append(
                KHDocument(
                    doc_id=f"job_{row.job_id}",
                    title=row.title,
                    content=content,
                    doc_type="job",
                    metadata=metadata,
                    published_date=str(row.posted_at) if row.posted_at else None,
                )
            )

        return documents

    # ── HTML Cleaning ───────────────────────────────────────────────

    @staticmethod
    def _strip_html(html: str) -> str:
        """Remove HTML tags and decode entities."""
        if not html:
            return ""
        
        # Remove script and style tags with content
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove HTML tags
        html = re.sub(r"<[^>]+>", "", html)
        
        # Decode common HTML entities
        html = html.replace("&nbsp;", " ")
        html = html.replace("&amp;", "&")
        html = html.replace("&lt;", "<")
        html = html.replace("&gt;", ">")
        html = html.replace("&quot;", '"')
        html = html.replace("&#39;", "'")
        
        # Normalize whitespace
        html = re.sub(r"\s+", " ", html).strip()
        
        return html
