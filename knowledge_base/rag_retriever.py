"""
rag_retriever.py
----------------
SEBI Knowledge Base RAG Retriever.

Full implementation uses ChromaDB + sentence-transformers to embed
and query the SEBI Feb 2025 circular. This stub provides the same
interface using keyword matching so the system runs without requiring
heavy ML dependencies or the circular text file.

To enable full RAG:
  1. pip install chromadb sentence-transformers
  2. Place sebi_circular.txt in knowledge_base/
  3. Replace this file with the full rag_retriever from teammate's repo

Used by: agents/compliance_agent.py
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

# ── Hardcoded SEBI knowledge for keyword-based retrieval ─────────────────────
# Extracted key rules from SEBI/HO/MRD/TPD-1/P/CIR/2025/xx (Feb 2025)

_SEBI_KNOWLEDGE = [
    {
        "section": "Order Frequency",
        "chunk_id": "freq_001",
        "text": (
            "SEBI circular Feb 2025: Retail algorithmic trading is permitted "
            "for tech-savvy investors placing fewer than 10 orders per second. "
            "Strategies exceeding this threshold require full exchange-level "
            "algo registration. Investment-style strategies placing 1-5 orders "
            "per day are well within the tech-savvy retail category."
        ),
    },
    {
        "section": "Explainability",
        "chunk_id": "explain_001",
        "text": (
            "SEBI Feb 2025 framework requires all algorithmic strategies to be "
            "explainable to the end investor. Black-box strategies using opaque "
            "ML/AI models without clear rule-based logic require Research Analyst "
            "registration. Transparent strategies with explicit entry/exit "
            "conditions based on indicators like moving averages, z-scores, "
            "or keyword-based scoring are classified as white-box."
        ),
    },
    {
        "section": "Algo Tagging",
        "chunk_id": "tag_001",
        "text": (
            "Every algorithmic trading strategy must carry a unique algo tag ID "
            "issued by the exchange. This tag must accompany all orders placed "
            "by the strategy for regulatory traceability. The tag format follows "
            "SEBI-EXCHANGE-YEAR-UNIQUEID convention."
        ),
    },
    {
        "section": "Position Limits",
        "chunk_id": "position_001",
        "text": (
            "SEBI retail algo guidelines recommend position sizing controls. "
            "Single position concentration above 20% of portfolio introduces "
            "significant concentration risk. Total algo strategy exposure should "
            "not exceed 60% of portfolio value to maintain adequate diversification."
        ),
    },
    {
        "section": "Broker Responsibility",
        "chunk_id": "broker_001",
        "text": (
            "Under SEBI Feb 2025 framework, brokers act as the principal for "
            "all algo orders routed through their API. The algo provider acts "
            "as the broker's agent. Brokers are ultimately responsible for "
            "ensuring all strategies routed through their systems comply with "
            "SEBI regulations."
        ),
    },
    {
        "section": "Registration",
        "chunk_id": "reg_001",
        "text": (
            "SEBI Feb 2025 mandates that algo providers offering strategies to "
            "retail investors must register with the exchange. Light registration "
            "applies to low-frequency rule-based strategies. Full registration "
            "and audit trail requirements apply to high-frequency or complex "
            "algorithmic strategies."
        ),
    },
]


# ── SEBIKnowledgeBase class (stub matching teammate's interface) ──────────────

class SEBIKnowledgeBase:
    """
    Lightweight keyword-based stub of the full ChromaDB RAG system.
    Provides the same query interface without heavy ML dependencies.
    """

    def __init__(self, *args, **kwargs):
        self._initialized = True
        logger.info("[rag_retriever] Using lightweight keyword-based stub.")

    def query(self, question: str, n_results: int = 3) -> list[dict]:
        """
        Retrieve relevant SEBI knowledge chunks for a question.
        Uses simple keyword matching instead of vector similarity.

        Args:
            question:  Natural language question about SEBI rules
            n_results: Number of results to return

        Returns:
            List of dicts with {text, section, chunk_id, score}
        """
        question_lower = question.lower()
        scored = []

        for chunk in _SEBI_KNOWLEDGE:
            # Count keyword overlaps between question and chunk text
            chunk_words  = set(chunk["text"].lower().split())
            query_words  = set(question_lower.split())
            overlap      = len(chunk_words & query_words)
            section_hit  = any(w in question_lower for w in chunk["section"].lower().split())
            score        = overlap + (5 if section_hit else 0)

            scored.append({**chunk, "score": score})

        # Sort by score descending, return top n
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:n_results]

    def query_text(self, question: str, n_results: int = 3) -> str:
        """
        Return retrieved chunks as a single formatted string.
        Convenience method for passing context to LLM.
        """
        results = self.query(question, n_results)
        if not results:
            return "No relevant SEBI guidelines found."

        lines = ["Relevant SEBI Guidelines:\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. [{r['section']}] {r['text']}\n")

        return "\n".join(lines)

    def is_initialized(self) -> bool:
        return self._initialized


# ── Module-level singleton ────────────────────────────────────────────────────

_kb_instance: SEBIKnowledgeBase | None = None


def get_knowledge_base() -> SEBIKnowledgeBase:
    """
    Return the singleton SEBIKnowledgeBase instance.
    Creates it on first call (lazy initialization).

    This is the function imported by compliance_agent.py:
        from knowledge_base.rag_retriever import get_knowledge_base
    """
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = SEBIKnowledgeBase()
    return _kb_instance


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    kb = get_knowledge_base()

    questions = [
        "What is the order frequency limit for retail algo trading?",
        "Does a momentum strategy need exchange registration?",
        "What are the position sizing guidelines?",
        "Is keyword-based sentiment scoring considered black box?",
    ]

    for q in questions:
        print(f"Q: {q}")
        results = kb.query(q, n_results=2)
        for r in results:
            print(f"  [{r['section']}] score={r['score']}: {r['text'][:80]}...")
        print()

    print("=== query_text ===")
    print(kb.query_text("What registration is needed for a rule-based strategy?"))