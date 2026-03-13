from typing import List, Dict
from tools.base_tool import BaseTool
from tools.providers.duckduckgo_provider import DuckDuckGoProvider


class WebSearchTool(BaseTool):

    name = "web_search"

    description = "Search the web for relevant information."

    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            }
        },
        "required": ["query"]
    }

    def __init__(self, provider=None, top_k: int = 5):

        self.provider = provider or DuckDuckGoProvider()
        self.top_k = top_k

    def run(self, **kwargs) -> List[Dict]:

        query = kwargs.get("query")

        if not query:
            raise ValueError("web_search requires 'query' parameter")

        print(f"[WebSearchTool] searching: {query}")

        results = self.provider.search(query, self.top_k)

        print("Search results:", results)

        return results