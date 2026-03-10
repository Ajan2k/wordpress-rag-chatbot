# backend/app/repositories/vector_store.py
"""
Repository for the Qdrant vector database.

Manages:
  • Collection creation with hybrid (dense + sparse) configuration
  • Upserting document chunks with both dense and sparse vectors
  • Hybrid search using Reciprocal Rank Fusion (RRF)
"""
import logging
import uuid
from typing import List, Dict, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseIndexParams,
    PointStruct,
    SparseVector,
    SearchRequest,
    NamedVector,
    NamedSparseVector,
    Filter,
    models,
)
from app.core.settings import settings
from app.domain.schemas import DocumentChunk, SourceDocument

logger = logging.getLogger(__name__)

# BGE-M3 dense dimension
DENSE_DIM = 1024


class VectorStore:
    """
    Qdrant-backed vector store supporting hybrid search via RRF.
    """

    def __init__(self) -> None:
        self._client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
        self._collection = settings.qdrant_collection
        self._ensure_collection()

    # ── Collection Management ───────────────────────────────────────

    def _ensure_collection(self) -> None:
        """Create the collection if it does not already exist."""
        collections = [
            c.name for c in self._client.get_collections().collections
        ]
        if self._collection in collections:
            logger.info("Qdrant collection '%s' already exists.", self._collection)
            return

        logger.info("Creating Qdrant collection '%s' …", self._collection)
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config={
                "dense": VectorParams(
                    size=DENSE_DIM,
                    distance=Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=SparseIndexParams(on_disk=False),
                ),
            },
        )
        logger.info("Collection '%s' created.", self._collection)

    # ── Upserting ───────────────────────────────────────────────────

    def upsert_hybrid_batch(
        self,
        chunks: List[DocumentChunk],
        dense_vectors: List[List[float]],
        sparse_vectors: List[Dict[int, float]],
    ) -> None:
        """
        Upsert a batch of document chunks with both dense and sparse vectors.
        """
        points: List[PointStruct] = []
        for chunk, dense_vec, sparse_dict in zip(
            chunks, dense_vectors, sparse_vectors
        ):
            # Convert sparse dict {token_id: weight} → SparseVector
            indices = list(sparse_dict.keys())
            values = list(sparse_dict.values())

            point = PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk.chunk_id)),
                vector={
                    "dense": dense_vec,
                    "sparse": SparseVector(indices=indices, values=values),
                },
                payload={
                    "chunk_id": chunk.chunk_id,
                    "post_id": chunk.post_id,
                    "title": chunk.title,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                },
            )
            points.append(point)

        self._client.upsert(
            collection_name=self._collection,
            points=points,
        )
        logger.debug("Upserted batch of %d points.", len(points))

    # ── Hybrid Search (RRF) ─────────────────────────────────────────

    def hybrid_search(
        self,
        dense_query: List[float],
        sparse_query: Dict[int, float],
        top_k: int = 10,
    ) -> List[SourceDocument]:
        """
        Execute a hybrid search combining dense cosine similarity
        and sparse (exact keyword) matching via Reciprocal Rank Fusion.

        RRF formula:  score = Σ  1 / (k + rank)   with k = 60
        """
        k_rrf = 60  # RRF constant

        # Dense search
        dense_results = self._client.search(
            collection_name=self._collection,
            query_vector=("dense", dense_query),
            limit=top_k * 2,          # fetch more for better fusion
            with_payload=True,
        )

        # Sparse search
        sparse_indices = list(sparse_query.keys())
        sparse_values = list(sparse_query.values())
        sparse_results = self._client.search(
            collection_name=self._collection,
            query_vector=NamedSparseVector(
                name="sparse",
                vector=SparseVector(
                    indices=sparse_indices,
                    values=sparse_values,
                ),
            ),
            limit=top_k * 2,
            with_payload=True,
        )

        # ── Reciprocal Rank Fusion ─────────────────────────────────
        rrf_scores: Dict[str, float] = {}
        payloads: Dict[str, dict] = {}

        for rank, hit in enumerate(dense_results, start=1):
            point_id = str(hit.id)
            rrf_scores[point_id] = rrf_scores.get(point_id, 0.0) + 1.0 / (k_rrf + rank)
            payloads[point_id] = hit.payload

        for rank, hit in enumerate(sparse_results, start=1):
            point_id = str(hit.id)
            rrf_scores[point_id] = rrf_scores.get(point_id, 0.0) + 1.0 / (k_rrf + rank)
            payloads[point_id] = hit.payload

        # Sort by fused score descending and take top_k
        sorted_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:top_k]

        sources: List[SourceDocument] = []
        for pid in sorted_ids:
            p = payloads[pid]
            sources.append(
                SourceDocument(
                    title=p.get("title", ""),
                    content_preview=p.get("content", "")[:200],
                    post_id=p.get("post_id", 0),
                    score=round(rrf_scores[pid], 6),
                )
            )
        return sources

    # ── Utilities ───────────────────────────────────────────────────

    def get_collection_info(self) -> dict:
        """Return stats about the vector collection."""
        try:
            info = self._client.get_collection(self._collection)
            return {
                "name": self._collection,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status.value if info.status else "unknown",
            }
        except Exception:
            return {"name": self._collection, "status": "not_found"}

    def delete_collection(self) -> None:
        """Delete the entire collection (used before a full re-sync)."""
        self._client.delete_collection(self._collection)
        logger.warning("Deleted Qdrant collection '%s'.", self._collection)
        self._ensure_collection()
