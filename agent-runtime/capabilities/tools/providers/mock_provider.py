# tools/providers/mock_provider.py

from capabilities.tools.providers.protocols import SearchProvider


class MockSearchProvider(SearchProvider):

    def search(self, query: str, top_k: int):

        results = []

        for i in range(top_k):

            results.append(
                {
                    "title": f"Result {i} for {query}",
                    "url": f"https://example.com/{query}/{i}",
                    "snippet": f"This page explains {query}"
                }
            )

        return results
