from __future__ import annotations

from infrastructure.retrieval.rag.retrieval.keyword import keyword_retrieve


def retrieve_relevant_chunks(
    query: str,
    documents: list[dict] | None = None,
    *,
    chunks=None,
    top_k: int = 4,
) -> list[dict]:
    """
    Compatibility wrapper for the original retrieval entry point.
    """
    return keyword_retrieve(
        query=query,
        documents=documents,
        chunks=chunks,
        top_k=top_k,
    )
