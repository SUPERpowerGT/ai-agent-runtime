from __future__ import annotations

from capabilities.tools.base_tool import BaseTool, ToolCapability
from capabilities.tools.providers.mcp import MCPRagRetrieveProvider
from observability.logging import log_tool


class RagRetrieveTool(BaseTool):
    name = "rag_retrieve"
    description = "Retrieve document context through an MCP-backed retrieval provider."
    capability = ToolCapability(
        category="retrieval",
        networked=True,
        requires_files=True,
        read_only=True,
        tags=["rag", "documents", "mcp"],
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Retrieval query",
            },
            "uploaded_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Uploaded files to search against",
            },
            "top_k": {
                "type": "integer",
                "description": "Maximum number of retrieved chunks",
            },
        },
        "required": ["query"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "retrieved_documents": {"type": "array"},
            "context_blocks": {"type": "array"},
            "retrieval_metadata": {"type": "object"},
        },
        "required": ["retrieved_documents", "context_blocks", "retrieval_metadata"],
    }

    def __init__(self, provider=None, top_k: int = 4):
        self.provider = provider or MCPRagRetrieveProvider()
        self.top_k = top_k

    def run(self, **kwargs) -> dict:
        query = kwargs.get("query")
        uploaded_files = kwargs.get("uploaded_files") or []
        top_k = kwargs.get("top_k", self.top_k)

        if not query:
            raise ValueError("rag_retrieve requires 'query' parameter")

        transport = self._provider_transport()
        log_tool(
            self.name,
            f"transport={transport} retrieving context for: {query}",
        )

        result = self.provider.retrieve(
            query=query,
            uploaded_files=uploaded_files,
            top_k=top_k,
        )

        log_tool(
            self.name,
            (
                f"docs={result['retrieval_metadata']['documents_loaded']} "
                f"chunks={result['retrieval_metadata']['chunks_created']} "
                f"hits={len(result['retrieved_documents'])}"
            ),
        )

        return result

    def build_metadata(self, data: dict) -> dict:
        retrieval_metadata = data.get("retrieval_metadata", {}) if isinstance(data, dict) else {}
        metadata = {
            "documents_loaded": retrieval_metadata.get("documents_loaded", 0),
            "chunks_created": retrieval_metadata.get("chunks_created", 0),
            "documents_retrieved": retrieval_metadata.get("documents_retrieved", 0),
            "retrieval_strategies": retrieval_metadata.get("retrieval_strategies", []),
        }
        metadata.update(self._provider_metadata())
        return metadata

    def summarize_output(self, data):
        if not isinstance(data, dict):
            return data
        return {
            "retrieved_documents": data.get("retrieved_documents", [])[:3],
            "context_blocks": data.get("context_blocks", [])[:3],
            "retrieval_metadata": data.get("retrieval_metadata", {}),
        }

    def _provider_metadata(self) -> dict:
        if hasattr(self.provider, "describe_transport"):
            return self.provider.describe_transport()
        return {"transport": "unknown"}

    def _provider_transport(self) -> str:
        return self._provider_metadata().get("transport", "unknown")
