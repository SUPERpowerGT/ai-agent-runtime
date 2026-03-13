# test_research_agent.py

from agents.research_agent import ResearchAgent
from state.state import TaskState

from tools.tools_registry import ToolRegistry
from tools.web_search_tool import WebSearchTool


def main():

    print("=== Init Tool Registry ===")

    # 初始化工具注册表
    registry = ToolRegistry()

    # 注册 web_search 工具
    registry.register(WebSearchTool())

    print("Available tools:", registry.list_tools())

    print("\n=== Create Agent ===")

    # 创建 research agent
    agent = ResearchAgent(registry)

    print("\n=== Create TaskState ===")

    state = TaskState(
        task_id="task_001",
        user_request="how to implement quicksort in python",
        plan=["research", "coder"]
    )

    print("Initial state:", state)

    print("\n=== Run ResearchAgent ===")

    state = agent.run(state)

    print("\n=== After Agent Run ===")

    print("Next agent:", state.next_agent)

    print("\nWorking memory:")
    print(state.working_memory)

    print("\nArtifacts:")
    print(state.artifacts)


if __name__ == "__main__":
    main()