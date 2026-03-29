from __future__ import annotations

"""
Compatibility layer for legacy imports.

The active implementation now lives under the infrastructure retrieval package.
"""

from infrastructure.retrieval.rag.ingest.loaders import SUPPORTED_EXTENSIONS, load_supported_documents
from infrastructure.retrieval.rag.models import DocumentChunk
from infrastructure.retrieval.rag.processing.chunking import chunk_documents
from infrastructure.retrieval.rag.retrieval.retriever import retrieve_relevant_chunks

__all__ = [
    "SUPPORTED_EXTENSIONS",
    "DocumentChunk",
    "load_supported_documents",
    "chunk_documents",
    "retrieve_relevant_chunks",
]
