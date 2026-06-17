"""
SEBI Knowledge Base RAG Retriever — ChromaDB + sentence-transformers.

Loads the SEBI circular, chunks it into ~200-word overlapping segments,
embeds with all-MiniLM-L6-v2, and stores in a persistent ChromaDB
collection for retrieval-augmented compliance checks.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default paths
_DEFAULT_CIRCULAR_PATH = Path(__file__).parent / "sebi_circular.txt"
_DEFAULT_CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"


class SEBIKnowledgeBase:
    """
    RAG system over the SEBI algorithmic trading circular.

    Uses sentence-transformers for embedding and ChromaDB for
    vector storage and retrieval.

    Usage:
        kb = SEBIKnowledgeBase()
        results = kb.query("What is the order frequency limit?")
        print(results)
    """

    def __init__(
        self,
        circular_path: str | Path = _DEFAULT_CIRCULAR_PATH,
        chroma_dir: str | Path = _DEFAULT_CHROMA_DIR,
    ):
        self.circular_path = Path(circular_path)
        self.chroma_dir = Path(chroma_dir)
        self._collection = None
        self._embedder = None
        self._chunks: list[dict] = []  # {text, section, chunk_id}
        self._initialized = False

    def _load_and_chunk(self) -> list[dict]:
        """
        Load the SEBI circular and split into ~200-word overlapping chunks
        with metadata.

        Returns:
            List of dicts with {text, section, chunk_id}.
        """
        if not self.circular_path.exists():
            logger.error(f"SEBI circular not found at {self.circular_path}")
            return []

        raw_text = self.circular_path.read_text(encoding="utf-8")

        # Split into sections on the section divider (━━━)
        raw_sections = raw_text.split("━" * 10)

        chunks = []
        chunk_id = 0

        for section_text in raw_sections:
            section_text = section_text.strip()
            if len(section_text) < 50:
                continue

            # Extract section name from the first line
            lines = section_text.split("\n")
            section_name = "General"
            for line in lines[:5]:
                line = line.strip()
                if line.startswith("SECTION") or line.startswith("RULE"):
                    section_name = line
                    break
                elif line and len(line) > 10 and not line.startswith("─"):
                    section_name = line[:80]
                    break

            # Split section into ~200-word overlapping chunks
            words = section_text.split()
            chunk_size = 200
            overlap = 50

            if len(words) <= chunk_size:
                # Section fits in one chunk
                chunks.append({
                    "text": section_text,
                    "section": section_name,
                    "chunk_id": f"chunk_{chunk_id:03d}",
                })
                chunk_id += 1
            else:
                # Sliding window chunking
                start = 0
                while start < len(words):
                    end = min(start + chunk_size, len(words))
                    chunk_text = " ".join(words[start:end])
                    chunks.append({
                        "text": chunk_text,
                        "section": section_name,
                        "chunk_id": f"chunk_{chunk_id:03d}",
                    })
                    chunk_id += 1
                    start += chunk_size - overlap

        logger.info(
            f"Loaded {len(chunks)} chunks from {self.circular_path.name}"
        )
        self._chunks = chunks
        return chunks

    def _build_index(self) -> None:
        """
        Embed chunks using all-MiniLM-L6-v2 and store in ChromaDB.

        Persists the collection to the chroma_db folder so subsequent
        runs don't need to re-embed.
        """
        try:
            import chromadb
            from chromadb.utils import embedding_functions
        except ImportError:
            logger.error(
                "chromadb not installed. Run: pip install chromadb"
            )
            raise

        if not self._chunks:
            self._load_and_chunk()

        if not self._chunks:
            logger.error("No chunks to index — SEBI circular may be missing.")
            return

        # Create persistent ChromaDB client
        self.chroma_dir.mkdir(parents=True, exist_ok=True)

        client = chromadb.PersistentClient(path=str(self.chroma_dir))

        # Use sentence-transformers embedding function
        self._embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        # Delete existing collection if it exists, to rebuild fresh
        try:
            client.delete_collection("sebi_rules")
        except Exception:
            pass

        self._collection = client.create_collection(
            name="sebi_rules",
            embedding_function=self._embedder,
            metadata={"description": "SEBI Feb 2025 Algo Trading Circular"},
        )

        # Add all chunks
        self._collection.add(
            documents=[c["text"] for c in self._chunks],
            metadatas=[
                {"section": c["section"], "chunk_id": c["chunk_id"]}
                for c in self._chunks
            ],
            ids=[c["chunk_id"] for c in self._chunks],
        )

        logger.info(
            f"Built ChromaDB index with {self._collection.count()} vectors "
            f"(persisted to {self.chroma_dir})"
        )
        self._initialized = True

    def _ensure_initialized(self) -> None:
        """Lazy initialization — build index on first query."""
        if not self._initialized:
            self._load_and_chunk()
            self._build_index()

    def query(self, question: str, n_results: int = 3) -> str:
        """
        Query the SEBI knowledge base for relevant rule text.

        Args:
            question: Natural language question about SEBI rules.
            n_results: Number of top relevant chunks to return.

        Returns:
            Formatted string with the top-k relevant chunks,
            including section metadata.

        Example queries it must answer well:
            - "What is the order frequency limit for retail investors?"
            - "What qualifies as a black box algorithm under SEBI rules?"
            - "What is the algo tag ID requirement?"
        """
        self._ensure_initialized()

        if self._collection is None:
            # Fallback: return raw chunks if ChromaDB failed
            logger.warning("ChromaDB not available, returning raw chunks")
            return "\n\n---\n\n".join(
                c["text"] for c in self._chunks[:n_results]
            )

        try:
            results = self._collection.query(
                query_texts=[question],
                n_results=min(n_results, self._collection.count()),
            )

            if not results or not results["documents"] or not results["documents"][0]:
                return "No relevant SEBI rules found for this query."

            # Format results
            formatted_parts = []
            for i, (doc, metadata) in enumerate(
                zip(results["documents"][0], results["metadatas"][0])
            ):
                section = metadata.get("section", "Unknown")
                chunk_id = metadata.get("chunk_id", "?")
                formatted_parts.append(
                    f"[Source: {section} | {chunk_id}]\n{doc}"
                )

            return "\n\n---\n\n".join(formatted_parts)

        except Exception as e:
            logger.error(f"ChromaDB query failed: {e}")
            # Fallback to raw text search
            return self._fallback_search(question, n_results)

    def _fallback_search(
        self, question: str, n_results: int = 3
    ) -> str:
        """Simple keyword-based fallback when vector search fails."""
        question_words = set(question.lower().split())
        scored = []

        for chunk in self._chunks:
            chunk_words = set(chunk["text"].lower().split())
            overlap = len(question_words & chunk_words)
            scored.append((overlap, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:n_results]

        return "\n\n---\n\n".join(
            f"[Source: {c['section']}]\n{c['text']}" for _, c in top
        )


# ── Module-level convenience instance ────────────────────────────────────────

_default_kb: Optional[SEBIKnowledgeBase] = None


def get_knowledge_base() -> SEBIKnowledgeBase:
    """Get or create the default SEBI knowledge base instance."""
    global _default_kb
    if _default_kb is None:
        _default_kb = SEBIKnowledgeBase()
    return _default_kb
