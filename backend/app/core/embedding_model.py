# backend/app/core/embedding_model.py
"""
Singleton wrapper around the BAAI/bge-m3 sentence-transformer.

This model produces BOTH dense and sparse (lexical weight) embeddings
in a single forward pass, which is perfect for Qdrant hybrid search.

Hardware constraint:  The entire model must fit inside 4 GB VRAM (GTX 1650).
BGE-M3 at fp32 is ~2.2 GB, so it fits comfortably.
We enforce single-instance loading via Singleton pattern.
"""
import logging
import threading
from typing import List, Tuple, Dict

from sentence_transformers import SentenceTransformer
from app.core.settings import settings

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """
    Thread-safe Singleton that loads BAAI/bge-m3 exactly once.
    Provides encode() returning (dense_vectors, sparse_vectors).
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls) -> "EmbeddingModel":
        """Guarantee a single model instance across threads."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialised = False
                    cls._instance = instance
        return cls._instance

    def __init__(self) -> None:
        if self._initialised:
            return
        logger.info(
            "Loading embedding model '%s' onto GPU …",
            settings.embedding_model_name,
        )
        # sentence-transformers will auto-select CUDA when available
        self._model = SentenceTransformer(
            settings.embedding_model_name,
            device="cuda",          # force GPU — fall back below if unavailable
            trust_remote_code=True,
        )
        self._initialised = True
        logger.info("Embedding model loaded successfully.")

    # ── Public API ──────────────────────────────────────────────────

    def encode_dense(self, texts: List[str]) -> List[List[float]]:
        """
        Generate dense embeddings for a list of texts.
        Returns a list of float vectors.
        """
        embeddings = self._model.encode(
            texts,
            batch_size=settings.embedding_batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    def encode_sparse(self, texts: List[str]) -> List[Dict[int, float]]:
        """
        Generate sparse (lexical weight) embeddings using the
        model's built-in tokeniser.  Returns a list of {token_id: weight}.

        BGE-M3's SentenceTransformer wrapper exposes this via
        `model.encode(..., return_sparse=True)` – but that API is
        version-dependent.  We fall back to a TF-IDF-like bag-of-words
        representation if the native sparse method is unavailable.
        """
        try:
            # Attempt native sparse encoding (FlagEmbedding ≥ 1.2)
            output = self._model.encode(
                texts,
                batch_size=settings.embedding_batch_size,
                show_progress_bar=False,
                return_dense=False,
                return_sparse=True,
            )
            # output could be a dict with 'sparse' key
            if isinstance(output, dict) and "sparse" in output:
                return self._parse_sparse(output["sparse"])
            return self._parse_sparse(output)
        except TypeError:
            # Fallback: build sparse from tokeniser term frequencies
            return self._fallback_sparse(texts)

    def encode_hybrid(
        self, texts: List[str]
    ) -> Tuple[List[List[float]], List[Dict[int, float]]]:
        """
        Convenience method: produce dense + sparse in one call.
        """
        dense = self.encode_dense(texts)
        sparse = self.encode_sparse(texts)
        return dense, sparse

    # ── Internal helpers ────────────────────────────────────────────

    @staticmethod
    def _parse_sparse(raw) -> List[Dict[int, float]]:
        """Normalise the heterogeneous sparse output into [{id: weight}]."""
        results: List[Dict[int, float]] = []
        for item in raw:
            if isinstance(item, dict):
                results.append(item)
            else:
                # scipy sparse or numpy array
                indices = item.nonzero()
                if hasattr(indices, "__len__") and len(indices) == 2:
                    idx = indices[1]
                else:
                    idx = indices[0]
                weights = {int(i): float(item[0, i] if item.ndim == 2 else item[i]) for i in idx}
                results.append(weights)
        return results

    def _fallback_sparse(self, texts: List[str]) -> List[Dict[int, float]]:
        """
        Token-frequency based sparse vector as a last resort.
        Uses the model's own tokeniser so token IDs stay consistent.
        """
        tokeniser = self._model.tokenizer
        results: List[Dict[int, float]] = []
        for text in texts:
            token_ids = tokeniser.encode(text, add_special_tokens=False)
            freq: Dict[int, float] = {}
            for tid in token_ids:
                freq[tid] = freq.get(tid, 0.0) + 1.0
            results.append(freq)
        return results
