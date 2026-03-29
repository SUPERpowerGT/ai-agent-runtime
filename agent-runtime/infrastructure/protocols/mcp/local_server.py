from __future__ import annotations

import time
from typing import Any


class LocalMCPServer:
    """
    In-process MCP loopback server.

    The server implements a small but MCP-shaped JSON-RPC subset so that the
    runtime can follow MCP semantics locally before a remote MCP server is
    deployed.
    """

    def __init__(self):
        self.initialized = False

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = message.get("method")
        params = message.get("params") or {}
        request_id = message.get("id")

        if method == "notifications/initialized":
            self.initialized = True
            return None

        try:
            if method == "initialize":
                result = self._initialize(params)
            elif method == "tools/list":
                result = self._tools_list()
            elif method == "tools/call":
                result = self._tools_call(params)
            else:
                return self._error_response(
                    request_id,
                    code=-32601,
                    message=f"Unsupported MCP method: {method}",
                )
        except Exception as exc:
            return self._error_response(
                request_id,
                code=-32000,
                message=str(exc),
            )

        if request_id is None:
            return None
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        protocol_version = params.get("protocolVersion", "2025-11-25")
        return {
            "protocolVersion": protocol_version,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {
                "name": "local-loopback-mcp",
                "version": "0.1.0",
                "description": "In-process MCP loopback for local development",
            },
            "instructions": (
                "This local MCP server exposes runtime tools through an "
                "in-process JSON-RPC loopback transport."
            ),
        }

    def _tools_list(self) -> dict[str, Any]:
        from capabilities.tools.rag_retrieve_tool import RagRetrieveTool
        from capabilities.tools.sandbox_execute_tool import SandboxExecuteTool
        from capabilities.tools.web_search_tool import WebSearchTool

        return {
            "tools": [
                WebSearchTool.describe_mcp_tool(),
                RagRetrieveTool.describe_mcp_tool(),
                SandboxExecuteTool.describe_mcp_tool(),
            ],
        }

    def _tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}

        try:
            if tool_name == "web_search":
                provider = self._build_search_provider()
                data = {
                    "results": provider.search(
                    arguments.get("query", ""),
                    int(arguments.get("top_k", 5) or 5),
                    ),
                }
            elif tool_name == "rag_retrieve":
                from capabilities.tools.providers.local_rag_provider import LocalRagProvider

                provider = LocalRagProvider()
                data = provider.retrieve(
                    query=arguments.get("query", ""),
                    uploaded_files=arguments.get("uploaded_files") or [],
                    top_k=int(arguments.get("top_k", 4) or 4),
                )
            elif tool_name == "sandbox_execute":
                from capabilities.tools.providers.local_execution_provider import (
                    LocalExecutionProvider,
                )

                provider = LocalExecutionProvider()
                data = provider.execute(
                    command=arguments.get("command") or [],
                    cwd=arguments.get("cwd"),
                    timeout_seconds=int(arguments.get("timeout_seconds", 10) or 10),
                    env=arguments.get("env") or {},
                    policy_mode=arguments.get("policy_mode"),
                    allowed_cwds=arguments.get("allowed_cwds") or [],
                    blocked_commands=arguments.get("blocked_commands") or [],
                    allowed_env_keys=arguments.get("allowed_env_keys") or [],
                )
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Unsupported MCP tool: {tool_name}",
                        },
                    ],
                    "structuredContent": {"error": f"Unsupported MCP tool: {tool_name}"},
                    "isError": True,
                    "_meta": self._meta(),
                }
        except Exception as exc:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": str(exc),
                    },
                ],
                "structuredContent": {"error": str(exc)},
                "isError": True,
                "_meta": self._meta(),
            }

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"{tool_name} executed successfully",
                },
            ],
            "structuredContent": data,
            "isError": False,
            "_meta": self._meta(),
        }

    def _meta(self) -> dict[str, Any]:
        return {
            "transport": "local_loopback",
            "server": "local-loopback-mcp",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def _error_response(self, request_id: Any, *, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    def _build_search_provider(self):
        try:
            from capabilities.tools.providers.duckduckgo_provider import DuckDuckGoProvider

            return DuckDuckGoProvider()
        except ModuleNotFoundError:
            from capabilities.tools.providers.mock_provider import MockSearchProvider

            return MockSearchProvider()
