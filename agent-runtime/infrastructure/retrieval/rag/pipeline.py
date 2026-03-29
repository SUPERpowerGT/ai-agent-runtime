from __future__ import annotations

from infrastructure.retrieval.rag.ingest.loaders import load_supported_documents
from infrastructure.retrieval.rag.assembly.context import build_citations, build_context_blocks
from infrastructure.retrieval.rag.models import RagPipelineResult
from infrastructure.retrieval.rag.processing.cleaning import clean_documents
from infrastructure.retrieval.rag.processing.chunking import chunk_documents
from infrastructure.retrieval.rag.retrieval.hybrid import hybrid_retrieve
from infrastructure.retrieval.rag.retrieval.query import build_query_bundle
from infrastructure.retrieval.rag.retrieval.reranker import rerank_documents
from runtime.services.languages import extract_behavior_summaries, extract_code_contracts


def run_local_rag(
    *,
    query: str,
    uploaded_files: list[str] | None = None,
    top_k: int = 4,
) -> dict:
    """
    Run the built-in lightweight local RAG flow for uploaded files.
    """
    documents = load_supported_documents(uploaded_files or [])
    cleaned_documents = clean_documents(documents)
    query_bundle = build_query_bundle(query)
    chunks = chunk_documents(cleaned_documents)

    retrieval_run = hybrid_retrieve(
        queries=query_bundle.rewritten_queries or [query],
        chunks=chunks,
        top_k=top_k,
    )
    deduped_documents = retrieval_run["results"]
    reranked_documents = rerank_documents(
        deduped_documents,
        query_terms=query_bundle.query_terms,
        top_k=top_k,
    )
    context_blocks = build_context_blocks(reranked_documents)
    citations = build_citations(context_blocks)
    code_contracts = extract_code_contracts(cleaned_documents)
    behavior_summaries = extract_behavior_summaries(cleaned_documents)

    result = RagPipelineResult(
        documents=documents,
        cleaned_documents=cleaned_documents,
        chunks=[
            {
                "source": chunk.source,
                "chunk_id": chunk.chunk_id,
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
            }
            for chunk in chunks
        ],
        retrieved_documents=reranked_documents,
        context_blocks=context_blocks,
        citations=citations,
        query_analysis={
            "original_query": query_bundle.original_query,
            "normalized_query": query_bundle.normalized_query,
            "rewritten_queries": query_bundle.rewritten_queries,
            "query_terms": query_bundle.query_terms,
        },
        retrieval_metadata={
            "documents_loaded": len(documents),
            "documents_cleaned": len(cleaned_documents),
            "chunks_created": len(chunks),
            "documents_retrieved": len(reranked_documents),
            "retrieval_strategies": retrieval_run["strategies"],
            "retrieval_runs": retrieval_run["per_query_results"],
        },
        code_contracts=code_contracts,
        behavior_summaries=behavior_summaries,
    )
    return result.__dict__
