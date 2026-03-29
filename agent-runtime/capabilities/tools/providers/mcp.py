from __future__ import annotations

from infrastructure.protocols.mcp.client import MCPClient


class MCPWebSearchProvider:
    """
    Search provider backed by a remote MCP endpoint.
    """

    def __init__(
        self,
        *,
        client: MCPClient | None = None,
        tool_name: str = "web_search",
    ):
        self.client = client or MCPClient()
        self.tool_name = tool_name

    def describe_transport(self) -> dict[str, str]:
        metadata = self.client.describe()
        metadata["tool"] = self.tool_name
        return metadata

    def search(self, query: str, top_k: int) -> list[dict]:
        self.client.get_tool(self.tool_name)
        data = self.client.call_tool(
            tool_name=self.tool_name,
            arguments={
                "query": query,
                "top_k": top_k,
            },
        )
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            return data["results"]
        if not isinstance(data, list):
            raise ValueError("MCP web_search provider expected list response")
        return data


class MCPRagRetrieveProvider:
    """
    Retrieval provider backed by a remote MCP endpoint.
    """

    def __init__(
        self,
        *,
        client: MCPClient | None = None,
        tool_name: str = "rag_retrieve",
    ):
        self.client = client or MCPClient()
        self.tool_name = tool_name

    def describe_transport(self) -> dict[str, str]:
        metadata = self.client.describe()
        metadata["tool"] = self.tool_name
        return metadata

    def retrieve(
        self,
        *,
        query: str,
        uploaded_files: list[str] | None = None,
        top_k: int = 4,
    ) -> dict:
        self.client.get_tool(self.tool_name)
        data = self.client.call_tool(
            tool_name=self.tool_name,
            arguments={
                "query": query,
                "uploaded_files": uploaded_files or [],
                "top_k": top_k,
            },
        )
        if not isinstance(data, dict):
            raise ValueError("MCP rag_retrieve provider expected dict response")
        return data


class MCPSandboxExecuteProvider:
    """
    Execution provider backed by a remote MCP endpoint.
    """

    def __init__(
        self,
        *,
        client: MCPClient | None = None,
        tool_name: str = "sandbox_execute",
    ):
        self.client = client or MCPClient()
        self.tool_name = tool_name

    def describe_transport(self) -> dict[str, str]:
        metadata = self.client.describe()
        metadata["tool"] = self.tool_name
        return metadata

    def execute(
        self,
        *,
        command: list[str],
        cwd: str | None = None,
        timeout_seconds: int = 10,
        env: dict[str, str] | None = None,
        policy_mode: str | None = None,
        allowed_cwds: list[str] | None = None,
        blocked_commands: list[str] | None = None,
        allowed_env_keys: list[str] | None = None,
    ) -> dict:
        self.client.get_tool(self.tool_name)
        data = self.client.call_tool(
            tool_name=self.tool_name,
            arguments={
                "command": command,
                "cwd": cwd,
                "timeout_seconds": timeout_seconds,
                "env": env or {},
                "policy_mode": policy_mode,
                "allowed_cwds": allowed_cwds or [],
                "blocked_commands": blocked_commands or [],
                "allowed_env_keys": allowed_env_keys or [],
            },
        )
        if not isinstance(data, dict):
            raise ValueError("MCP sandbox_execute provider expected dict response")
        return data
