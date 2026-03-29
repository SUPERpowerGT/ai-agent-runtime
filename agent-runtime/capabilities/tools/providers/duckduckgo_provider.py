from capabilities.tools.providers.protocols import SearchProvider
from capabilities.tools.providers.mock_provider import MockSearchProvider
from observability.logging import log_tool


class DuckDuckGoProvider(SearchProvider):

    def search(self, query: str, top_k: int):
        results = []

        try:
            from ddgs import DDGS

            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=top_k):
                    results.append(
                        {
                            "title": r.get("title"),
                            "url": r.get("href"),
                            "snippet": r.get("body"),
                        }
                    )
            return results
        except Exception as exc:
            primary_error = exc

        try:
            from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=top_k):
                    results.append(
                        {
                            "title": r.get("title"),
                            "url": r.get("href") or r.get("url"),
                            "snippet": r.get("body") or r.get("snippet"),
                        }
                    )
            return results
        except Exception as fallback_exc:
            log_tool(
                "web_search",
                "provider_fallback=mock "
                f"reason={type(primary_error).__name__}: {primary_error}; "
                f"secondary={type(fallback_exc).__name__}: {fallback_exc}",
            )
            return MockSearchProvider().search(query, top_k)
