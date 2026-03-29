from __future__ import annotations

from infrastructure.retrieval.rag.retrieval.keyword import keyword_retrieve


def hybrid_retrieve(
    *,
    queries: list[str],
    documents: list[dict] | None = None,
    chunks=None,
    top_k: int = 4,
) -> dict:
    keyword_results_by_query: list[dict] = []

    for query in queries:
        keyword_results = keyword_retrieve(
            query=query,
            documents=documents,
            chunks=chunks,
            top_k=top_k,
        )
        keyword_results_by_query.append({
            "query": query,
            "strategy": "keyword",
            "results": keyword_results,
        })

    merged_results = merge_retrieval_results(keyword_results_by_query, top_k=top_k)

    return {
        "results": merged_results,
        "strategies": ["keyword"],
        "per_query_results": keyword_results_by_query,
    }


def merge_retrieval_results(retrieval_runs: list[dict], *, top_k: int = 4) -> list[dict]:
    merged: dict[str, dict] = {}

    for run in retrieval_runs:
        query = run.get("query", "")
        strategy = run.get("strategy", "unknown")

        for result in run.get("results", []):
            chunk_id = result.get("chunk_id", "")
            if not chunk_id:
                continue

            enriched = {
                **result,
                "matched_queries": sorted({*result.get("matched_queries", []), query} if query else result.get("matched_queries", [])),
                "retrieval_strategies": sorted({
                    *result.get("retrieval_strategies", []),
                    strategy,
                    result.get("retrieval_strategy", strategy),
                }),
            }

            existing = merged.get(chunk_id)
            if existing is None:
                merged[chunk_id] = enriched
                continue

            if float(enriched.get("score", 0.0)) > float(existing.get("score", 0.0)):
                existing["score"] = enriched["score"]
                existing["text"] = enriched["text"]

            existing["matched_queries"] = sorted(set(existing.get("matched_queries", [])) | set(enriched.get("matched_queries", [])))
            existing["retrieval_strategies"] = sorted(set(existing.get("retrieval_strategies", [])) | set(enriched.get("retrieval_strategies", [])))

    ranked_results = list(merged.values())
    ranked_results.sort(
        key=lambda item: (
            float(item.get("score", 0.0)),
            len(item.get("matched_queries", [])),
        ),
        reverse=True,
    )
    return ranked_results[:top_k]
