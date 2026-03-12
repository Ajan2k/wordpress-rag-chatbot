# backend/app/services/chunking_engine.py
"""
Recursive Character Text Splitter for breaking Kitchen Herald content
(articles, events, jobs) into manageable chunks for embedding.

Optimized for different document types with adaptive chunk sizing.
Mirrors LangChain's RecursiveCharacterTextSplitter logic without
adding LangChain as a dependency.
"""
import logging
from typing import List

from app.domain.schemas import KHDocument, DocumentChunk

logger = logging.getLogger(__name__)


class ChunkingEngine:
    """
    Splits long documents into overlapping text chunks using a
    hierarchical set of separators (paragraphs → sentences → words).
    
    Adaptive chunking based on document type:
    - Articles: 500 tokens (default)
    - Events: 300 tokens (usually shorter)
    - Jobs: 400 tokens (balanced)
    """

    # Separators tried in order — we prefer to split on paragraph,
    # then sentence, then word boundaries.
    SEPARATORS = ["\n\n", "\n", ". ", ", ", " ", ""]
    
    # Adaptive chunk sizes by document type (in characters, roughly)
    DOC_TYPE_CHUNK_SIZES = {
        "article": 500,
        "event": 300,
        "job": 400,
    }

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50) -> None:
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    # ── Public API ──────────────────────────────────────────────────

    def split_documents(
        self, documents: List[KHDocument]
    ) -> List[DocumentChunk]:
        """
        Split a list of KHDocument objects into DocumentChunks.
        Each chunk carries metadata for traceability and retrieval.
        
        Uses adaptive chunk sizing based on document type.
        """
        all_chunks: List[DocumentChunk] = []
        
        for doc in documents:
            # Determine chunk size based on document type
            chunk_size = self.DOC_TYPE_CHUNK_SIZES.get(doc.doc_type, self._chunk_size)
            text_chunks = self._recursive_split(doc.content, self.SEPARATORS, chunk_size)
            
            for idx, text in enumerate(text_chunks):
                chunk = DocumentChunk(
                    chunk_id=f"{doc.doc_id}_{idx}",
                    doc_id=doc.doc_id,
                    doc_type=doc.doc_type,
                    title=doc.title,
                    content=text,
                    chunk_index=idx,
                    metadata={
                        **doc.metadata,  # Include all original metadata
                        "published_date": doc.published_date,
                    },
                )
                all_chunks.append(chunk)

        logger.info(
            "Chunked %d documents into %d chunks (overlap=%d).",
            len(documents),
            len(all_chunks),
            self._chunk_overlap,
        )
        return all_chunks

    # ── Internal recursive splitting ────────────────────────────────

    def _recursive_split(
        self, text: str, separators: List[str], chunk_size: int = None
    ) -> List[str]:
        """
        Recursively split text using the first applicable separator.
        Falls back to character-level splitting as a last resort.
        
        Args:
            text: Text to split
            separators: List of separators to try in order
            chunk_size: Chunk size for this split (if None, uses self._chunk_size)
        """
        if chunk_size is None:
            chunk_size = self._chunk_size
            
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

            if current_len + piece_len > chunk_size and current_chunk:
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
