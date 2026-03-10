# backend/app/worker/tasks.py
"""
Celery tasks for the asynchronous ETL pipeline.

The sync_wordpress_data task runs on a Celery worker with concurrency=1,
ensuring the BGE-M3 model never exceeds the 4 GB VRAM limit.

Progress updates are pushed to Redis and polled by the admin dashboard.
"""
import logging
from celery import shared_task

from app.repositories.wp_repository import WPRepository
from app.services.chunking_engine import ChunkingEngine
from app.core.embedding_model import EmbeddingModel
from app.repositories.vector_store import VectorStore
from app.core.settings import settings

logger = logging.getLogger(__name__)


def _batched(iterable, batch_size: int):
    """Yield successive batches from an iterable."""
    for i in range(0, len(iterable), batch_size):
        yield iterable[i : i + batch_size]


@shared_task(bind=True, name="sync_wordpress_data")
def sync_wordpress_data(self):
    """
    Full Extract → Transform → Load pipeline.

    Phases:
      1. Extract published posts from WordPress MySQL
      2. Chunk the raw text using recursive splitting
      3. Embed chunks via BGE-M3 (dense + sparse)
      4. Upsert to Qdrant for hybrid retrieval

    Each phase updates the task state so the admin dashboard can
    render a live progress bar.
    """
    try:
        # ── Phase 1: Extraction ────────────────────────────────────
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 5,
                "total": 100,
                "status": "Connecting to WordPress MySQL database …",
            },
        )
        wp_repo = WPRepository()
        raw_documents = wp_repo.extract_published_content()
        doc_count = len(raw_documents)

        self.update_state(
            state="PROGRESS",
            meta={
                "current": 15,
                "total": 100,
                "status": f"Extracted {doc_count} published documents.",
            },
        )
        logger.info("Extraction complete: %d documents.", doc_count)

        if doc_count == 0:
            return {
                "current": 100,
                "total": 100,
                "status": "No published content found in the database.",
                "chunks_processed": 0,
            }

        # ── Phase 2: Chunking ──────────────────────────────────────
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 25,
                "total": 100,
                "status": "Splitting documents into chunks …",
            },
        )
        chunker = ChunkingEngine(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        document_chunks = chunker.split_documents(raw_documents)
        chunk_count = len(document_chunks)

        self.update_state(
            state="PROGRESS",
            meta={
                "current": 35,
                "total": 100,
                "status": f"Created {chunk_count} text chunks.",
            },
        )
        logger.info("Chunking complete: %d chunks.", chunk_count)

        # ── Phase 3: Reset collection ──────────────────────────────
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 40,
                "total": 100,
                "status": "Resetting Qdrant collection for fresh sync …",
            },
        )
        vector_store = VectorStore()
        vector_store.delete_collection()  # full re-sync strategy

        # ── Phase 4: Embed + Upsert in batches ────────────────────
        embedder = EmbeddingModel()
        batch_size = settings.embedding_batch_size
        batches = list(_batched(document_chunks, batch_size))
        total_batches = len(batches)

        for batch_idx, batch in enumerate(batches):
            progress = 45 + int((batch_idx / total_batches) * 50)
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": min(progress, 95),
                    "total": 100,
                    "status": (
                        f"Embedding & upserting batch {batch_idx + 1}/{total_batches} "
                        f"({len(batch)} chunks) …"
                    ),
                },
            )

            texts = [c.content for c in batch]
            dense_vectors, sparse_vectors = embedder.encode_hybrid(texts)
            vector_store.upsert_hybrid_batch(batch, dense_vectors, sparse_vectors)

            logger.info(
                "Batch %d/%d upserted (%d chunks).",
                batch_idx + 1,
                total_batches,
                len(batch),
            )

        # ── Done ───────────────────────────────────────────────────
        result = {
            "current": 100,
            "total": 100,
            "status": "Synchronisation complete ✓",
            "documents_extracted": doc_count,
            "chunks_processed": chunk_count,
        }
        logger.info("ETL pipeline finished successfully: %s", result)
        return result

    except Exception as e:
        logger.error("ETL Pipeline failed: %s", str(e), exc_info=True)
        self.update_state(
            state="FAILURE",
            meta={
                "exc_type": type(e).__name__,
                "exc_message": str(e),
            },
        )
        raise e