# tools/providers/mock_provider.py

class MockSearchProvider:

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