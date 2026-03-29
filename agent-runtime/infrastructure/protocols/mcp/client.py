from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests

from infrastructure.protocols.mcp.local_server import LocalMCPServer


@dataclass(frozen=True)
class MCPCallToolResult:
    content: list[dict[str, Any]]
    structured_content: dict[str, Any] | None
    is_error: bool
    meta: dict[str, Any]


class MCPClient:
    """
    Minimal JSON-RPC MCP client.

    This client now speaks a subset of the MCP lifecycle:
    - initialize
    - notifications/initialized
    - tools/list
    - tools/call

    The transport can be either:
    - remote HTTP JSON-RPC
    - local in-process loopback
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        api_key: str | None = None,
        protocol_version: str | None = None,
    ):
        self.base_url = (base_url or os.getenv("MCP_BASE_URL") or "").rstrip("/")
        self.timeout_seconds = timeout_seconds or float(
            os.getenv("MCP_TIMEOUT_SECONDS", "10"),
        )
        self.api_key = api_key or os.getenv("MCP_API_KEY")
        self.transport = (os.getenv("MCP_TRANSPORT") or "").strip().lower()
        self.protocol_version = protocol_version or os.getenv(
            "MCP_PROTOCOL_VERSION",
            "2025-11-25",
        )
        self.local_server = LocalMCPServer()
        self._request_id = 0
        self._initialized = False
        self._server_info: dict[str, Any] | None = None
        self._tools_by_name: dict[str, dict[str, Any]] = {}

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def transport_name(self) -> str:
        if self.base_url:
            return "http"
        return "local_loopback"

    def endpoint(self) -> str:
        if self.base_url:
            return self.base_url
        return "in-process"

    def describe(self) -> dict[str, str]:
        description = {
            "transport": self.transport_name(),
            "endpoint": self.endpoint(),
            "protocol": "json-rpc",
            "protocol_version": self.protocol_version,
        }
        if self._server_info:
            description["server"] = self._server_info.get("name", "unknown")
        return description

    def list_tools(self) -> list[dict[str, Any]]:
        self._ensure_initialized()
        result = self._request("tools/list")
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            raise ValueError("MCP tools/list returned invalid tools payload")
        self._tools_by_name = {
            tool.get("name"): tool
            for tool in tools
            if isinstance(tool, dict) and isinstance(tool.get("name"), str)
        }
        return tools

    def get_tool(self, tool_name: str) -> dict[str, Any]:
        if tool_name not in self._tools_by_name:
            self.list_tools()
        tool = self._tools_by_name.get(tool_name)
        if not isinstance(tool, dict):
            raise ValueError(f"MCP tool '{tool_name}' is not advertised by the server")
        return tool

    def call_tool(self, *, tool_name: str, arguments: dict[str, Any]) -> Any:
        result = self.call_tool_result(tool_name=tool_name, arguments=arguments)
        if result.is_error:
            error_message = self._extract_error_text(result.content)
            raise ValueError(error_message or "MCP tool call failed")

        if result.structured_content is not None:
            return result.structured_content

        if len(result.content) == 1:
            block = result.content[0]
            if isinstance(block, dict) and block.get("type") == "text":
                return block.get("text")
        return result.content

    def call_tool_result(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> MCPCallToolResult:
        self._ensure_initialized()
        self.get_tool(tool_name)
        result = self._request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments,
            },
        )
        return self._parse_call_result(result)

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        result = self._request(
            "initialize",
            {
                "protocolVersion": self.protocol_version,
                "capabilities": {
                    "roots": {"listChanged": False},
                    "sampling": {},
                },
                "clientInfo": {
                    "name": "ai-agent-runtime",
                    "version": "0.1.0",
                },
            },
        )
        self._server_info = result.get("serverInfo", {})
        self._notify("notifications/initialized", {})
        self._initialized = True

    def _parse_call_result(self, result: dict[str, Any]) -> MCPCallToolResult:
        content = result.get("content", [])
        if not isinstance(content, list):
            raise ValueError("MCP CallToolResult.content must be a list")
        for block in content:
            if not isinstance(block, dict):
                raise ValueError("MCP content blocks must be JSON objects")
            if not isinstance(block.get("type"), str):
                raise ValueError("MCP content blocks must include a string type")

        structured = result.get("structuredContent")
        if structured is not None and not isinstance(structured, dict):
            raise ValueError("MCP CallToolResult.structuredContent must be an object")

        is_error = bool(result.get("isError", False))
        meta = result.get("_meta", {})
        if not isinstance(meta, dict):
            raise ValueError("MCP CallToolResult._meta must be an object when present")

        return MCPCallToolResult(
            content=content,
            structured_content=structured,
            is_error=is_error,
            meta=meta,
        )

    def _extract_error_text(self, content: list[dict[str, Any]]) -> str:
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if text:
                    texts.append(text)
        if texts:
            return " | ".join(texts)
        return ""

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._request_id += 1
        message = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params

        response = self._send_message(message)
        if not isinstance(response, dict):
            raise ValueError("MCP response must be a JSON object")

        if "error" in response:
            error = response["error"] or {}
            message = error.get("message", "Unknown MCP error")
            raise ValueError(message)

        result = response.get("result")
        if not isinstance(result, dict):
            raise ValueError("MCP result payload must be an object")
        return result

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        message = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            message["params"] = params
        self._send_message(message)

    def _send_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        if self.base_url:
            return self._send_http_message(message)

        if self.transport in {"", "local", "loopback"}:
            return self.local_server.handle_message(message)

        raise ValueError("MCP_BASE_URL is not configured")

    def _send_http_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = requests.post(
            self.base_url,
            json=message,
            headers=headers,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

        if not response.content:
            return None
        payload = response.json()
        if payload is None:
            return None
        if not isinstance(payload, dict):
            raise ValueError("MCP HTTP response must be a JSON object")
        return payload
