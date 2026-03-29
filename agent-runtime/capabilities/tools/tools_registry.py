from __future__ import annotations


class ToolRegistry:
    """
    统一管理系统中的所有工具
    """

    def __init__(self):
        self.tools = {}

    def register(self, tool):
        """
        注册一个工具
        """
        self.tools[tool.name] = tool

    def get(self, name):
        """
        根据名字获取工具
        """
        if name not in self.tools:
            raise ValueError(f"Tool '{name}' not found")

        return self.tools[name]

    def list_tools(self):
        """
        返回当前系统所有工具
        """
        return list(self.tools.keys())

    def describe_tool(self, name):
        tool = self.get(name)
        return tool.describe()

    def list_tool_descriptions(self):
        return {
            name: tool.describe()
            for name, tool in self.tools.items()
        }

    def list_tools_by_category(self, category: str):
        matched = []
        for name, tool in self.tools.items():
            if tool.capability.category == category:
                matched.append(name)
        return matched

    def execute(
        self,
        *,
        state=None,
        agent_name: str | None = None,
        tool_name: str,
        **kwargs,
    ):
        tool = self.get(tool_name)
        result = tool.execute(**kwargs)

        if state is not None and agent_name is not None:
            state.add_tool_call(
                agent_name=agent_name,
                tool_name=tool_name,
                tool_input=kwargs,
                tool_output=tool.summarize_result(result),
                success=result.success,
                error=result.error,
            )
            if tool_name == "sandbox_execute":
                duration_ms = 0.0
                execution_success = result.success
                if isinstance(result.data, dict):
                    duration_ms = float(result.data.get("duration_ms", 0.0) or 0.0)
                    timed_out = bool(result.data.get("timed_out", False))
                    exit_code = result.data.get("exit_code")
                    execution_success = result.success and (not timed_out) and exit_code == 0
                state.record_execution_call(duration_ms, success=execution_success)

        return result
