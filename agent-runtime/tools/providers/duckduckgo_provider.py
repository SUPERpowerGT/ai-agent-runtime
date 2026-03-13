from ddgs import DDGS


class DuckDuckGoProvider:

    def search(self, query: str, top_k: int):

        results = []

        with DDGS() as ddgs:

            for r in ddgs.text(query, max_results=top_k):

                results.append(
                    {
                        "title": r.get("title"),
                        "url": r.get("href"),
                        "snippet": r.get("body")
                    }
                )

        return results