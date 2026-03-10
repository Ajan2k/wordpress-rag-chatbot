# backend/app/services/chunking_engine.py
"""
Recursive Character Text Splitter for breaking WordPress content
into manageable chunks for embedding.

Mirrors LangChain's RecursiveCharacterTextSplitter logic without
adding LangChain as a dependency.
"""
import logging
from typing import List

from app.domain.schemas import WPDocument, DocumentChunk

logger = logging.getLogger(__name__)


class ChunkingEngine:
    """
    Splits long documents into overlapping text chunks using a
    hierarchical set of separators (paragraphs → sentences → words).
    """

    # Separators tried in order — we prefer to split on paragraph,
    # then sentence, then word boundaries.
    SEPARATORS = ["\n\n", "\n", ". ", ", ", " ", ""]

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50) -> None:
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    # ── Public API ──────────────────────────────────────────────────

    def split_documents(
        self, documents: List[WPDocument]
    ) -> List[DocumentChunk]:
        """
        Split a list of WPDocuments into DocumentChunks.
        Each chunk carries its parent post_id and title for traceability.
        """
        all_chunks: List[DocumentChunk] = []
        for doc in documents:
            text_chunks = self._recursive_split(doc.content, self.SEPARATORS)
            for idx, text in enumerate(text_chunks):
                chunk = DocumentChunk(
                    chunk_id=f"{doc.post_id}_{idx}",
                    post_id=doc.post_id,
                    title=doc.title,
                    content=text,
                    chunk_index=idx,
                    metadata={
                        "post_type": doc.post_type,
                        "url": doc.url,
                    },
                )
                all_chunks.append(chunk)

        logger.info(
            "Chunked %d documents into %d chunks (size=%d, overlap=%d).",
            len(documents),
            len(all_chunks),
            self._chunk_size,
            self._chunk_overlap,
        )
        return all_chunks

    # ── Internal recursive splitting ────────────────────────────────

    def _recursive_split(
        self, text: str, separators: List[str]
    ) -> List[str]:
        """
        Recursively split text using the first applicable separator.
        Falls back to character-level splitting as a last resort.
        """
        final_chunks: List[str] = []

        # Find the best separator for this text
        separator = separators[-1]
        for sep in separators:
            if sep == "":
                separator = sep
                break
            if sep in text:
                separator = sep
                break

        splits = text.split(separator) if separator else list(text)

        # Merge small splits until they reach chunk_size
        current_chunk: List[str] = []
        current_len = 0

        for piece in splits:
            piece_len = len(piece) + (len(separator) if separator else 0)

            if current_len + piece_len > self._chunk_size and current_chunk:
                merged = separator.join(current_chunk).strip()
                if merged:
                    final_chunks.append(merged)
                # Keep overlap
                overlap_chunks: List[str] = []
                overlap_len = 0
                for item in reversed(current_chunk):
                    if overlap_len + len(item) > self._chunk_overlap:
                        break
                    overlap_chunks.insert(0, item)
                    overlap_len += len(item)
                current_chunk = overlap_chunks
                current_len = overlap_len

            current_chunk.append(piece)
            current_len += piece_len

        # Flush remaining
        if current_chunk:
            merged = separator.join(current_chunk).strip()
            if merged:
                final_chunks.append(merged)

        return final_chunks
