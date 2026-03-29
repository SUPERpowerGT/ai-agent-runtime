from capabilities.tools.rag_retrieve_tool import RagRetrieveTool
from capabilities.tools.sandbox_execute_tool import SandboxExecuteTool
from capabilities.tools.tools_registry import ToolRegistry
from capabilities.tools.web_search_tool import WebSearchTool


def init_tools() -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(RagRetrieveTool())
    registry.register(SandboxExecuteTool())
    registry.register(WebSearchTool())

    return registry
