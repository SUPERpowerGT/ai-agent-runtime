from __future__ import annotations

from infrastructure.retrieval.rag.pipeline import run_local_rag
from capabilities.tools.providers.protocols import RetrievalProvider


class LocalRagProvider(RetrievalProvider):
    """
    Provider for the built-in local RAG pipeline.
    """

    def retrieve(
        self,
        *,
        query: str,
        uploaded_files: list[str] | None = None,
        top_k: int = 4,
    ) -> dict:
        return run_local_rag(
            query=query,
            uploaded_files=uploaded_files,
            top_k=top_k,
        )
