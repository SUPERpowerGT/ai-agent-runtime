from __future__ import annotations

import math
import re

from infrastructure.retrieval.rag.models import DocumentChunk
from infrastructure.retrieval.rag.processing.chunking import chunk_documents


def keyword_retrieve(
    query: str,
    documents: list[dict] | None = None,
    *,
    chunks: list[DocumentChunk] | None = None,
    top_k: int = 4,
) -> list[dict]:
    chunks = chunks or chunk_documents(documents or [])
    query_terms = _tokenize(query)

    if not query_terms:
        return []

    ranked_chunks: list[DocumentChunk] = []
    for chunk in chunks:
        chunk.score = _score_chunk(query_terms, chunk.text)
        if chunk.score <= 0:
            continue

        ranked_chunks.append(chunk)

    ranked_chunks.sort(key=lambda chunk: chunk.score, reverse=True)

    return [
        {
            "source": chunk.source,
            "chunk_id": chunk.chunk_id,
            "score": round(chunk.score, 4),
            "text": chunk.text,
            "start_offset": chunk.start_offset,
            "end_offset": chunk.end_offset,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "chunk_type": chunk.chunk_type,
            "language": chunk.language,
            "symbol_name": chunk.symbol_name,
            "symbol_kind": chunk.symbol_kind,
            "section_title": chunk.section_title,
            "retrieval_strategy": "keyword",
        }
        for chunk in ranked_chunks[:top_k]
    ]


def tokenize_query(text: str) -> list[str]:
    return _tokenize(text)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z_][a-zA-Z0-9_#+.-]*", text.lower())


def _score_chunk(query_terms: list[str], chunk_text: str) -> float:
    chunk_terms = _tokenize(chunk_text)
    if not chunk_terms:
        return 0.0

    chunk_term_set = set(chunk_terms)
    overlap = sum(1 for term in query_terms if term in chunk_term_set)
    if overlap == 0:
        return 0.0

    density_bonus = overlap / math.sqrt(len(chunk_terms))
    return overlap + density_bonus
