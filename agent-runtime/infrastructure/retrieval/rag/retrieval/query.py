from __future__ import annotations

import re

from infrastructure.retrieval.rag.models import QueryBundle


STOPWORDS = {
    "a", "an", "the", "to", "for", "in", "of", "and", "or", "with",
    "please", "uploaded", "code", "function", "script", "file", "files",
}


def build_query_bundle(query: str) -> QueryBundle:
    normalized_query = " ".join(query.strip().split())
    lowered = normalized_query.lower()
    query_terms = [
        term for term in _tokenize(lowered)
        if term not in STOPWORDS
    ]

    rewritten_queries = [normalized_query] if normalized_query else []
    if query_terms:
        keyword_query = " ".join(dict.fromkeys(query_terms))
        if keyword_query and keyword_query not in rewritten_queries:
            rewritten_queries.append(keyword_query)

    return QueryBundle(
        original_query=query,
        normalized_query=normalized_query,
        rewritten_queries=rewritten_queries,
        query_terms=query_terms,
    )


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z_][a-zA-Z0-9_#+.-]*", text.lower())
