from tools.tools_registry import ToolRegistry
from tools.web_search_tool import WebSearchTool


def init_tools():

    registry = ToolRegistry()

    registry.register(WebSearchTool())

    return registry