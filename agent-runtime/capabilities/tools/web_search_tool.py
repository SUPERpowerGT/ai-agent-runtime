from typing import List, Dict

from capabilities.tools.base_tool import BaseTool, ToolCapability
from capabilities.tools.providers.mcp import MCPWebSearchProvider
from observability.logging import log_tool


class WebSearchTool(BaseTool):

    name = "web_search"

    description = "Search the web for relevant information."
    capability = ToolCapability(
        category="search",
        networked=True,
        requires_files=False,
        read_only=True,
        tags=["web", "search", "mcp"],
    )

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
    output_schema = {
        "type": "object",
        "properties": {
            "results": {"type": "array"},
        },
        "required": ["results"],
    }

    def __init__(self, provider=None, top_k: int = 5):
        self.provider = provider or MCPWebSearchProvider()
        self.top_k = top_k

    def run(self, **kwargs) -> List[Dict]:
        query = kwargs.get("query")

        if not query:
            raise ValueError("web_search requires 'query' parameter")

        transport = self._provider_transport()
        log_tool(
            self.name,
            f"transport={transport} searching for: {query}",
        )

        results = self.provider.search(query, self.top_k)

        log_tool(self.name, f"results={len(results)}")

        return results

    def build_metadata(self, data) -> Dict:
        metadata = {
            "result_count": len(data or []),
        }
        metadata.update(self._provider_metadata())
        return metadata

    def summarize_output(self, data):
        if not isinstance(data, list):
            return data
        return data[:3]

    def _provider_metadata(self) -> Dict:
        if hasattr(self.provider, "describe_transport"):
            return self.provider.describe_transport()
        return {"transport": "unknown"}

    def _provider_transport(self) -> str:
        return self._provider_metadata().get("transport", "unknown")
