from __future__ import annotations


def build_context_blocks(retrieved_documents: list[dict]) -> list[dict]:
    context_blocks: list[dict] = []

    for index, item in enumerate(retrieved_documents, start=1):
        context_blocks.append({
            "id": f"context-{index}",
            "source": item.get("source", "unknown"),
            "chunk_id": item.get("chunk_id", ""),
            "text": item.get("text", ""),
            "score": item.get("rerank_score", item.get("score", 0.0)),
            "start_line": item.get("start_line"),
            "end_line": item.get("end_line"),
            "chunk_type": item.get("chunk_type"),
            "language": item.get("language"),
            "symbol_name": item.get("symbol_name"),
            "symbol_kind": item.get("symbol_kind"),
            "section_title": item.get("section_title"),
        })

    return context_blocks


def build_citations(context_blocks: list[dict]) -> list[dict]:
    citations: list[dict] = []

    for block in context_blocks:
        citations.append({
            "id": block["id"],
            "source": block["source"],
            "chunk_id": block["chunk_id"],
            "score": block["score"],
            "start_line": block.get("start_line"),
            "end_line": block.get("end_line"),
            "chunk_type": block.get("chunk_type"),
            "symbol_name": block.get("symbol_name"),
            "section_title": block.get("section_title"),
        })

    return citations
