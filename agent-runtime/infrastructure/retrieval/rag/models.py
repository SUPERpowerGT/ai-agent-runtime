from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DocumentChunk:
    source: str
    chunk_id: str
    text: str
    start_offset: int
    end_offset: int
    start_line: int
    end_line: int
    chunk_type: str
    language: str | None = None
    symbol_name: str | None = None
    symbol_kind: str | None = None
    section_title: str | None = None
    score: float = 0.0


@dataclass
class QueryBundle:
    original_query: str
    normalized_query: str
    rewritten_queries: list[str]
    query_terms: list[str]


@dataclass
class RagPipelineResult:
    documents: list[dict]
    cleaned_documents: list[dict]
    chunks: list[dict]
    retrieved_documents: list[dict]
    context_blocks: list[dict]
    citations: list[dict]
    query_analysis: dict[str, Any]
    retrieval_metadata: dict[str, Any]
    code_contracts: list[dict]
    behavior_summaries: list[dict]
