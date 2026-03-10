# backend/app/services/rag_orchestrator.py
"""
RAG Orchestrator — the single entry point for the query pipeline.

Flow:
  1. Receive user question (any language)
  2. Generate dense + sparse embeddings via local BGE-M3
  3. Execute hybrid search on Qdrant (RRF)
  4. Build context string from retrieved chunks
  5. Stream answer tokens from Groq Llama 3.3 70B

This service owns NO state — it composes the Singletons
(EmbeddingModel, VectorStore, GroqClient) via Dependency Injection.
"""
import logging
from typing import Generator, Tuple, List

from app.core.embedding_model import EmbeddingModel
from app.core.groq_client import GroqClient
from app.repositories.vector_store import VectorStore
from app.domain.schemas import SourceDocument

logger = logging.getLogger(__name__)


class RAGOrchestrator:
    """
    Coordinates retrieval and generation for a single user query.
    """

    def __init__(
        self,
        embedding_model: EmbeddingModel | None = None,
        vector_store: VectorStore | None = None,
        groq_client: GroqClient | None = None,
    ) -> None:
        self._embedder = embedding_model or EmbeddingModel()
        self._store = vector_store or VectorStore()
        self._groq = groq_client or GroqClient()

    # ── Public API ──────────────────────────────────────────────────

    def answer(self, question: str) -> Tuple[str, List[SourceDocument]]:
        """
        Blocking RAG: retrieve context → generate full answer.
        Returns (answer_text, source_documents).
        """
        sources = self._retrieve(question)
        context = self._build_context(sources)
        answer = self._groq.generate(context, question)
        return answer, sources

    def answer_stream(
        self, question: str
    ) -> Tuple[Generator[str, None, None], List[SourceDocument]]:
        """
        Streaming RAG: retrieve context → yield tokens one-by-one.
        Returns (token_generator, source_documents).

        The sources are computed up front (retrieval is fast);
        only the generation is streamed.
        """
        sources = self._retrieve(question)
        context = self._build_context(sources)
        token_gen = self._groq.generate_stream(context, question)
        return token_gen, sources

    # ── Internal pipeline ───────────────────────────────────────────

    def _retrieve(self, question: str) -> List[SourceDocument]:
        """Embed the question and run hybrid search."""
        dense_vecs, sparse_vecs = self._embedder.encode_hybrid([question])
        sources = self._store.hybrid_search(
            dense_query=dense_vecs[0],
            sparse_query=sparse_vecs[0],
        )
        logger.info(
            "Retrieved %d sources for question: '%s'",
            len(sources),
            question[:80],
        )
        return sources

    @staticmethod
    def _build_context(sources: List[SourceDocument]) -> str:
        """
        Concatenate the retrieved chunk previews into a single
        context string fed to the LLM.
        """
        if not sources:
            return "(No relevant context found in the knowledge base.)"

        parts = []
        for i, src in enumerate(sources, 1):
            parts.append(
                f"[{i}] {src.title}\n{src.content_preview}"
            )
        return "\n\n".join(parts)
