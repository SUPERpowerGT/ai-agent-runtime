from state.state import TaskState
from infra.llm_client import call_llm


class ResearchAgent:

    name = "research"

    def __init__(self, tool_registry):
        self.tool_registry = tool_registry

    def run(self, state: TaskState) -> TaskState:

        print("Running research agent")

        query = state.user_request

        # 调用 web_search tool
        web_search_tool = self.tool_registry.get("web_search")

        results = web_search_tool.run(query=query)

        # 保存原始搜索结果
        if "research_raw" not in state.artifacts:
            state.artifacts["research_raw"] = []

        state.artifacts["research_raw"].extend(results)

        prompt = f"""
You are a research assistant.

Summarize the following information into useful context.

User request:
{state.user_request}

Search results:
{results}

Return a concise summary.
"""

        summary = call_llm(prompt)

        state.working_memory["research"] = summary

        # 更新 next agent
        if "research" in state.plan:

            index = state.plan.index("research")

            if index + 1 < len(state.plan):
                state.next_agent = state.plan[index + 1]
            else:
                state.finished = True

        print("Research summary:", summary)

        print("Research results count:", len(results))

        return state