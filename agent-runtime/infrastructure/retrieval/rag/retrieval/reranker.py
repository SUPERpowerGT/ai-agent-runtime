from __future__ import annotations


def rerank_documents(
    documents: list[dict],
    *,
    query_terms: list[str],
    top_k: int = 4,
) -> list[dict]:
    reranked: list[dict] = []

    for index, document in enumerate(documents):
        text = document.get("text", "").lower()
        lexical_hits = sum(1 for term in query_terms if term in text)
        structural_bonus = 0.15 if "def " in text or "function " in text else 0.0
        rerank_score = float(document.get("score", 0.0)) + lexical_hits + structural_bonus

        reranked.append({
            **document,
            "retrieval_rank": index,
            "rerank_score": round(rerank_score, 4),
        })

    reranked.sort(key=lambda item: item["rerank_score"], reverse=True)
    return reranked[:top_k]
